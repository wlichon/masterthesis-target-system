#!/usr/bin/env python3

import re
import sys
import threading
import time
import os
import subprocess
import json
import requests
import datetime
import argparse




    
    
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from attacker import hping_udp_flood
from attacker.mavlink_flood import heartbeat_flood, mission_flood, nav_flood, param_flood, ping_flood, terrain_flood, socket_flood
from attacker.plots.cpu_usage import generate_fw_cpu_chart, generate_gcs_cpu_chart
from attacker.plots.latency import generate_latency_trend_chart
from attacker.plots.jitter import generate_normalized_jitter_chart


# --- CONFIGURATION ---
CONTAINERS = [
    "ground-control-station-lite",
    "companion-computer-lite",
    "flight-controller-lite",
    "gcs-firewall"
]

def format_usec_to_iso(timestamp_usec):
    """Converts a microsecond timestamp to the ISO format: YYYY-MM-DDTHH:MM:SS.mmmZ."""
    # Convert usec to seconds (float)
    dt = datetime.datetime.fromtimestamp(timestamp_usec / 1e6)
    # Format to ISO 8601 with milliseconds precision and Zulu suffix
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# Provided function to be used unchanged
def calculate_latency(timeSyncMessageSent, timeSyncMessageReceived):
    latency = (timeSyncMessageReceived.timestamp-timeSyncMessageSent.timestamp)*1e-3
    print(f"{format_usec_to_iso(timeSyncMessageReceived.timestamp)} ping response: {(latency):.3f}ms from={timeSyncMessageReceived.srcSystem()}/{timeSyncMessageReceived.srcComponent()}")  # noqa
    return latency
# Simple helper class to mimic the object structure expected by calculate_latency
class TimesyncMsg:
    def __init__(self, timestamp, sys_id, comp_id):
        self.timestamp = timestamp
        self._sys = sys_id
        self._comp = comp_id
    def srcSystem(self): return self._sys
    def srcComponent(self): return self._comp

def parse_mavlog(content):
    # print("from parse_mavlog")
    # Regex to capture: Timestamp, tc value, ts value, srcSystem, and srcComponent
    # Pattern looks for: 2026-04-05 18:58:31.88: TIMESYNC {tc1 : 0, ts1 : 1775408311881843968} srcSystem=255 srcComponent=230
    pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+): TIMESYNC"
    )

    pending_pings = {} # Key: ts1 value, Value: TimesyncMsg object (sent)
    latency_stats = []

    log = content.splitlines()

    for line in log:
        match = pattern.search(line)
        if not match:
            continue
        
        print(line)
        # Extract data from the regex groups
        
        log_time_str = match.groups()[0]
        tc = re.search(r"tc1 : (\d+)", line)
        tc = int(tc.group(1)) if tc else None
        ts1 = re.search(r"ts1 : (\d+)", line)
        ts1 = int(ts1.group(1)) if ts1 else None
        src_sys = re.search(r"srcSystem=(\d+)", line)
        src_sys = int(src_sys.group(1)) if src_sys else None
        src_comp = re.search(r"srcComponent=(\d+)", line)
        src_comp = int(src_comp.group(1)) if src_comp else None
        # Convert log string timestamp to microseconds for calculation
        dt = datetime.datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S.%f")
        log_timestamp_usec = int(dt.timestamp() * 1e6)

        # Case 1: GCS Request (tc=0, System=255, Component=230)
        if tc == 0 and src_sys == 255 and src_comp == 230:
            pending_pings[ts1] = TimesyncMsg(log_timestamp_usec, src_sys, src_comp)

        # Case 2: Drone Response (tc!=0, System=1, Component=1)
        elif tc != 0 and src_sys == 1 and src_comp == 1:
            # The 'ack' links back to the original request via the ts1 field
            if ts1 in pending_pings:
                sent_msg = pending_pings.pop(ts1)
                received_msg = TimesyncMsg(log_timestamp_usec, src_sys, src_comp)
                latency = calculate_latency(sent_msg, received_msg)
                iso = format_usec_to_iso(sent_msg.timestamp)
                latency_stats.append({"sent_at": iso, "latency_ms": round(latency, 3)})

    return latency_stats

class DockerMonitor:
    def __init__(self):
        self.stats_history = []
        self.keep_running = True
        self.thread = None

    def _monitor_loop(self):
        """Internal loop to grab snapshots every second."""
        format_str = '{"name":"{{.Name}}","cpu":"{{.CPUPerc}}","m_perc":"{{.MemPerc}}","net":"{{.NetIO}}"}'
        cmd = ["docker", "stats"] + CONTAINERS + ["--no-stream", "--format", format_str]

        ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]') # remove ansi escape codes from docker stats output
        
        
        last_logged_time = None
        while self.keep_running:
            try:
            # Start a persistent process with a pipe for stdout
                self.process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                for line in iter(self.process.stdout.readline, ''):
                    if not self.keep_running:
                        break
                    
                    clean_line = ansi_escape.sub('', line).strip()

                    if not line.strip():
                        continue

                    try:
                        raw = json.loads(clean_line)
                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                        
                       
                                        
                                        # Throttle to 1 entry per second
                        

                        self.stats_history.append({
                            "timestamp": timestamp,
                            "container": raw["name"],
                            "cpu_percent": raw["cpu"],
                            "mem_percent": raw["m_perc"],
                            "net_io": raw["net"]
                        })
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                print(f"Monitor Error: {e}")
                break
            finally:
                if self.process:
                    self.process.terminate()

    def start(self):
        """Starts the monitor in a background thread."""
        self.keep_running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True # thread will die when main loop exits
        self.thread.start()

    def stop(self):
        """Stops the monitor and returns the collected data."""
        self.keep_running = False
        if self.thread:
            self.thread.join()
        return self.stats_history

# Ensure udp_flood is in the global namespace for loop_function
# If it's imported as 'from ... import udp_flood', it's already there.

import time

def loop_function(attack_time, attack_function_name=None):
    # Initialize the record object
    attack_function = {
        "attack_name": attack_function_name or "baseline",
        "arguments": {"duration": attack_time}
    }

    # Map names to actual function objects
    attack_map = {
        "socket_flood": socket_flood,
        "heartbeat_flood": heartbeat_flood,
        "ping_flood": ping_flood,
        "param_flood": param_flood,
        "mission_flood": mission_flood,
        "terrain_flood": terrain_flood,
        "nav_flood": nav_flood,
        "hping_udp_flood": hping_udp_flood,
    }

    # Handle Baseline/Sleep mode
    if attack_function_name is None:
        print(f"No attack provided. Baseline mode: Sleeping for {attack_time}s.")
        time.sleep(attack_time)
        return attack_function

    # Check if the function exists in our map
    if attack_function_name not in attack_map:
        print(f"Error: Function '{attack_function_name}' not found. Sleeping instead.")
        time.sleep(attack_time)
        attack_function["error"] = "Function not found"
        return attack_function

    # 1. Create the Stop Event
    stop_event = threading.Event()
    
    # 2. Prepare the thread
    # We pass the stop_event and execution_record to your function
    target_func = attack_map[attack_function_name]
    attack_thread = threading.Thread(
        target=target_func, 
        kwargs={
            "stop_event": stop_event, 
            "execution_record": attack_function
        }
    )

    # 3. Start the attack
    print(f"--- Starting {attack_function_name} thread for {attack_time}s ---")
    attack_thread.start()

    # 4. Wait for the duration in the main thread
    time.sleep(attack_time)

    # 5. Signal the thread to stop and wait for it to finish
    print(f"--- Stopping {attack_function_name}... ---")
    stop_event.set()
    attack_thread.join(timeout=2) # Wait for thread to clean up

    return attack_function

def OLD_loop_function(attack_time, attack_function_name=None):
    # Initialize the record object to store arguments
    attack_function = {
        "attack_name": attack_function_name,
        "arguments": {}
    }

    if attack_function_name is None:
        print(f"No attack function provided. Baseline mode: Sleeping for {attack_time}s.")
        time.sleep(attack_time)
        attack_function["attack_name"] = "baseline"
        attack_function["arguments"] = {"duration": attack_time}
        return attack_function

    # Explicit mapping and execution
    if attack_function_name == "socket_flood":
        socket_flood(duration=attack_time, execution_record=attack_function)
        
    elif attack_function_name == "heartbeat_flood":
        
        heartbeat_flood(duration=attack_time, execution_record=attack_function)
        
    elif attack_function_name == "ping_flood":
        
        ping_flood(duration=attack_time, execution_record=attack_function)

    elif attack_function_name == "param_flood":
        
        param_flood(duration=attack_time, execution_record=attack_function)

    elif attack_function_name == "mission_flood":   
        mission_flood(duration=attack_time, execution_record=attack_function)

    elif attack_function_name == "terrain_flood":   
        terrain_flood(duration=attack_time, execution_record=attack_function)
        
    elif attack_function_name == "hping_udp_flood":
        hping_udp_flood(duration=attack_time, execution_record=attack_function)
        

    else:
        print(f"Error: Function '{attack_function_name}' not found. Sleeping instead.")
        time.sleep(attack_time)
        attack_function["error"] = "Function not found"

    return attack_function

# def OLD_loop_function(attack_time, attack_function_name=None):
#     if attack_function_name is None:
#         print(f"No attack function provided. Baseline mode: Sleeping for {attack_time}s.")
#         time.sleep(attack_time)
#         return

#     func = globals().get(attack_function_name)
#     if callable(func):
#         print(f"Running attack function '{attack_function_name}' for {attack_time} seconds...")
#         func(duration=attack_time)
#     else:
#         print(f"Error: Function '{attack_function_name}' not found. Sleeping instead.")
#         time.sleep(attack_time)

def get_current_timestamp():
    """Returns the current system time in 'YYYY-MM-DD HH:MM:SS' format."""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d_%H:%M:%S")

def main(attack_function=None):
    # --- CONFIGURATION ---
    
    attack_label = attack_function if attack_function else "baseline"
    attack_time = 20
    flight_time = 10
    execution_record = {}
    
    working_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    timestamp = get_current_timestamp()
    execution_record["timestamps"] = {"start": timestamp}
    execution_record["configuration"] = {}  
    # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_log_path = os.path.join(working_directory, f"logs/{attack_label}/{timestamp}")
    flashlogs_dir = os.path.join(base_log_path, "flashlogs")
    tlogs_dir = os.path.join(base_log_path, "tlogs")

    os.makedirs(flashlogs_dir, exist_ok=True)
    os.makedirs(tlogs_dir, exist_ok=True)

   
    monitor = DockerMonitor()
    monitor.start()

    # Reset the simulation
    print("Resetting GCS logs and restarting MAVProxy...")
    requests.post("http://localhost:8000/reset")

    allow_unsigned = "False"
    execution_record["configuration"]["allow_unsigned"] = allow_unsigned

    commands = [
        "pkill -9 -f mavproxy.py || true;",
        "rm -f /home/user/Documents/mavproxy/*.tlog* || true;",
        # We wrap the command in a single string and let sh -c handle the pipe/redirect
        "export TZ='Etc/GMT-2'; /usr/bin/python3 /usr/local/bin/mavproxy.py "
        "--master=udp:0.0.0.0:14550 "
        "--logfile=/home/user/Documents/mavproxy/telemetry.tlog "
        f"--cmd='signing key password;set allow_unsigned {allow_unsigned};repeat add 1 ping' | ts '[%Y-%m-%d %H:%M:%S]' > /home/user/Documents/mavproxy/latency.log 2>&1"
    ]

    for cmd in commands:
        subprocess.run(["docker", "exec", "-dt", "ground-control-station-lite", "sh", "-c", cmd])
        time.sleep(1)

    time.sleep(5)
    # Start stages
    for stage in ["stage1", "stage2", "stage3"]:
        print(f"Starting {stage}...")
        requests.post(f"http://localhost:8000/{stage}")
        time.sleep(3)

    print(f"Flying normally for {flight_time} seconds before attack...")
    execution_record["timestamps"]["first_normal_flight"] = get_current_timestamp()
    time.sleep(flight_time)

    # Trigger attack or baseline sleep
    execution_record["timestamps"]["attack"] = get_current_timestamp()
    print(f"Executing attack function: {attack_function} for {attack_time} seconds...")
    execution_record["attack_function"] = loop_function(attack_time, attack_function)
    
    
    # execution_record["timestamps"]["second_normal_flight"] = get_current_timestamp()
    # print(f"Flying normally for another {flight_time} seconds after attack...")
    # time.sleep(flight_time)

    print(f"Saving logs to {base_log_path}")

    # Download flight logs
    print("Downloading flight logs...")
    subprocess.run(["docker", "cp", "flight-controller-lite:/ardupilot/logs/.", flashlogs_dir])

    # Download tlogs
    print("Downloading tlogs...")
    subprocess.run(["docker", "cp", "ground-control-station-lite:/home/user/Documents/mavproxy/telemetry.tlog", tlogs_dir])
    
    if os.path.exists(tlogs_dir):
        tlog_file_path = os.path.join(tlogs_dir, "telemetry.tlog")
        print(f"Processing logs in {tlogs_dir}...")
        print("Running mavlogdump...")
        dump_cmd = f"mavlogdump.py --robust --show-seq --show-source '{tlog_file_path}' > '{base_log_path}/mavlogdump_output.txt'"
        subprocess.run(dump_cmd, shell=True)


        print("Running mavloss...")
        loss_cmd = f"python {working_directory}/logs/mav-packet-loss.py {base_log_path}/mavlogdump_output.txt"
        loss_result = subprocess.check_output(loss_cmd, shell=True, text=True, stderr=subprocess.STDOUT)
        
        loss_data = {}
        # Regex to find: [digits] packets, [digits] lost [float]%
        loss_match = re.search(r"(\d+) packets, (\d+) lost ([\d.]+)%", loss_result)
        if loss_match:
            loss_data = {
                "received_packets": int(loss_match.group(1)),
                "lost_packets": int(loss_match.group(2)),
                "loss_percentage": float(loss_match.group(3))
            }

        dist_command = f"cat {base_log_path}/mavlogdump_output.txt | awk '{{print $3}}' | sed 's/{{//g' | sort | uniq -c | sort -nr"
        msg_data = {}
        try:
            # Run the command and capture output
            dist_result = subprocess.check_output(dist_command, shell=True, text=True)
            for line in dist_result.strip().split('\n'):
                parts = line.split()
                if len(parts) == 2:
                    count = int(parts[0])
                    msg_type = parts[1]
                    msg_data[msg_type] = count

        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e}")
        finally:
            docker_stats = monitor.stop()
        
        # latency_stats = []
        # mavlogdump_content = subprocess.check_output(f"cat {base_log_path}/mavlogdump_output.txt", shell=True, text=True, stderr=subprocess.STDOUT)

        # try:
        #     print("Parsing MAV log for latency stats...")
        #     # path = os.path.join(base_log_path, 'mavlogdump_output.txt')
        #     # print("LATENCY PATH" + path)
        #     latency_stats = parse_mavlog(mavlogdump_content)
        # except Exception as e:
        #     print(f"Error occurred while parsing MAV log: {e}")


        latency_stats = []

        try:
            print("Parsing MAV log for latency stats...")
            # path = os.path.join(base_log_path, 'mavlogdump_output.txt')
            # print("LATENCY PATH" + path)
            latency_stats = subprocess.run(["docker", "exec", "ground-control-station-lite", "cat", "/home/user/Documents/mavproxy/latency.log"], capture_output=True, text=True, check=True).stdout.strip().splitlines()
            
            lines = [line for line in latency_stats if "ping response" in line]
            latency_data = []
            for line in lines:
            
                try:
                    # 1. Extract Timestamp: string between first '[' and ']'
                    ts_str = line[line.find("[")+1 : line.find("]")]
                    timestamp = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()*1e6

                    # 2. Extract Latency: split after the colon, before 'ms'
                    # Format: "...ping response: 5.759ms..."
                    lat_part = line.split("ping response: ")[1].split("ms")[0]
                    latency_ms = float(lat_part)

                    latency_data.append({
                        "timestamp": format_usec_to_iso(timestamp),
                        "latency": latency_ms
                    })
                except (IndexError, ValueError) as e:
                    # Skips malformed lines if the log was interrupted
                    continue
            
                
                # Now latency_values contains [3.658, ...]
                print(f"Extracted {len(latency_data)} latency data points.")
        except Exception as e:
            print(f"Error occurred while parsing MAV log: {e}")
        
        combined_log = {
            "execution_record": execution_record,
            "mavloss": loss_data,
            "message_types": msg_data,
            "docker_stats": docker_stats,
            "latency_stats": latency_data
        }

        
        print(f"combined logs: {combined_log}")

        with open(os.path.join(base_log_path, 'log.json'), 'w') as f:
            json.dump(combined_log, f, indent=4)

        generate_gcs_cpu_chart(os.path.join(base_log_path, 'log.json'), os.path.join(base_log_path, 'gcs_cpu_usage.png'))
        generate_fw_cpu_chart(os.path.join(base_log_path, 'log.json'), os.path.join(base_log_path, 'fw_cpu_usage.png'))
        generate_latency_trend_chart(os.path.join(base_log_path, 'log.json'), os.path.join(base_log_path, 'latency_trend.png'))
        
        baseline_tlog_path = os.path.join(working_directory, "logs", "baseline", "comparison", "tlogs", "telemetry.tlog")
        baseline_json_path = os.path.join(working_directory, "logs", "baseline", "comparison", "log.json")
        
        with open(baseline_json_path, 'r') as f:
            baseline_data = json.load(f)

        # 3. Extract the attack start timestamp from the dictionary
        # Note: Use bracket notation for standard dictionaries
        baseline_attack_start = baseline_data["execution_record"]["timestamps"]["attack"]

        generate_normalized_jitter_chart(baseline_tlog_path, baseline_attack_start, os.path.join(tlogs_dir, 'telemetry.tlog'), execution_record["timestamps"]["attack"], attack_time, os.path.join(base_log_path, 'jitter_graph.png'))

        print(f"Analysis complete. Results saved in {base_log_path}")
    else:
        print(f"Error: {tlog_file_path} not found. Skipping analysis.")
    execution_record["timestamps"]["end"] = get_current_timestamp()
    print("Done.")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test pipeline for drone attack scenarios.")
    parser.add_argument("--attack", type=str, default="None", help="Name of the attack function to run: udp_flood or None for baseline.")
    args = parser.parse_args()
    current_attack = None if args.attack == "None" else args.attack
    main(current_attack)
    # main("mavlink_flood")