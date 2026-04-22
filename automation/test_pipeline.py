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
import psutil

    
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'plots')))
from linecharts import generate_combined_system_stress_chart, generate_combined_socket_chart
from latency import generate_latency_trend_chart
from jitter import generate_normalized_jitter_chart


# --- CONFIGURATION ---
CONTAINERS = [
    "ground-control-station-lite",
    "companion-computer-lite",
    "flight-controller-lite"
]

ATTACKER_URL = "http://10.0.0.2:5000/trigger_attack"

def format_usec_to_iso(timestamp_usec):
    """Converts a microsecond timestamp to the ISO format: YYYY-MM-DDTHH:MM:SS.mmmZ."""
    dt = datetime.datetime.fromtimestamp(timestamp_usec / 1e6)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def calculate_latency(timeSyncMessageSent, timeSyncMessageReceived):
    latency = (timeSyncMessageReceived.timestamp-timeSyncMessageSent.timestamp)*1e-3
    print(f"{format_usec_to_iso(timeSyncMessageReceived.timestamp)} ping response: {(latency):.3f}ms from={timeSyncMessageReceived.srcSystem()}/{timeSyncMessageReceived.srcComponent()}")  # noqa
    return latency

class TimesyncMsg:
    def __init__(self, timestamp, sys_id, comp_id):
        self.timestamp = timestamp
        self._sys = sys_id
        self._comp = comp_id
    def srcSystem(self): return self._sys
    def srcComponent(self): return self._comp

def parse_mavlog(content):
    # Pattern looks for: 2026-04-05 18:58:31.88: TIMESYNC {tc1 : 0, ts1 : 1775408311881843968} srcSystem=255 srcComponent=230
    pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+): TIMESYNC"
    )

    pending_pings = {} 
    latency_stats = []

    log = content.splitlines()

    for line in log:
        match = pattern.search(line)
        if not match:
            continue
        
        print(line)

        
        log_time_str = match.groups()[0]
        tc = re.search(r"tc1 : (\d+)", line)
        tc = int(tc.group(1)) if tc else None
        ts1 = re.search(r"ts1 : (\d+)", line)
        ts1 = int(ts1.group(1)) if ts1 else None
        src_sys = re.search(r"srcSystem=(\d+)", line)
        src_sys = int(src_sys.group(1)) if src_sys else None
        src_comp = re.search(r"srcComponent=(\d+)", line)
        src_comp = int(src_comp.group(1)) if src_comp else None
        dt = datetime.datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S.%f")
        log_timestamp_usec = int(dt.timestamp() * 1e6)

      
        if tc == 0 and src_sys == 255 and src_comp == 230:
            pending_pings[ts1] = TimesyncMsg(log_timestamp_usec, src_sys, src_comp)

        elif tc != 0 and src_sys == 1 and src_comp == 1:
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
        
        while self.keep_running:
            try:
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


class HostMonitor:
    def __init__(self):
        self.host_history = []
        self.keep_running = True
        self.thread = None

    def _monitor_loop(self):
        """Monitors the Host CPU usage."""
        # First call to cpu_percent initializes the comparison
        psutil.cpu_percent(interval=None)
        
        while self.keep_running:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            # Get CPU load across all cores as a percentage
            cpu_usage = psutil.cpu_percent(interval=1) 
            
            self.host_history.append({
                "timestamp": timestamp,
                "host_cpu_percent": cpu_usage
            })

    def start(self):
        self.keep_running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.keep_running = False
        if self.thread:
            self.thread.join()
        return self.host_history

class NetworkMonitor:
    def __init__(self, interface="enp2s0"):
        self.interface = interface
        self.history = []
        self.keep_running = True
        self.thread = None
        self.path = f"/sys/class/net/{interface}/statistics/rx_bytes"

    def _get_rx_bytes(self):
        with open(self.path, 'r') as f:
            return int(f.read().strip())

    def _monitor_loop(self):
        last_bytes = self._get_rx_bytes()
        last_time = time.perf_counter() 

        while self.keep_running:
            time.sleep(1) 
            
            current_bytes = self._get_rx_bytes()
            current_time = time.perf_counter()
            
       
            delta_bytes = current_bytes - last_bytes
            delta_time = current_time - last_time
            
      
            bps = (delta_bytes * 8) / delta_time
            mbps = bps / 1e6 # Megabits per second
            
            self.history.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "rx_mbps": round(mbps, 2)
            })
            
            last_bytes = current_bytes
            last_time = current_time

    def start(self):
        self.keep_running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.keep_running = False
        if self.thread:
            self.thread.join()
        return self.history

class SocketMonitor:
    def __init__(self, container_name="ground-control-station-lite", port_hex="38D6"):
        self.container = container_name
        self.port_hex = port_hex
        self.history = []
        self.keep_running = True
        self.thread = None

    def _monitor_loop(self):
        while self.keep_running:
            try:
                cmd = ["docker", "exec", self.container, "cat", "/proc/net/udp"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if self.port_hex in line:
                            parts = line.split()
                            # rx_queue is index 4
                            rx_queue_hex = parts[4].split(':')[1]
                            rx_bytes = int(rx_queue_hex, 16)
                            
                            # drops is index 12
                            drops = int(parts[12])
                            
                            now = datetime.datetime.now()
                            human_timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            
                            self.history.append({
                                "timestamp": human_timestamp,
                                "rx_queue_bytes": rx_bytes,
                                "drops": drops # New field
                            })
                            break
                time.sleep(0.01)
            except Exception as e:
                continue

    def start(self):
        self.keep_running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.keep_running = False
        if self.thread:
            self.thread.join()
        return self.history

def get_current_timestamp():
    """Returns the current system time in 'YYYY-MM-DD HH:MM:SS' format."""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d_%H:%M:%S")

def main(attack_function, drone_reset, idle_flight_time, attack_flight_time):
    # --- CONFIGURATION ---
    python_venv_path = "/home/lichon/Desktop/python-venv/bin"  # Adjust if your virtual environment is located elsewhere
    attack_label = attack_function if attack_function else "baseline"
    execution_record = {}
    
    working_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    timestamp = get_current_timestamp()
    execution_record["timestamps"] = {"start": timestamp}
    execution_record["configuration"] = { "attack_function": attack_function, "attack_time": attack_flight_time, "flight_time": idle_flight_time, "drone_reset": drone_reset}  
    # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_log_path = os.path.join(working_directory, f"logs/{attack_label}/{timestamp}")
    flashlogs_dir = os.path.join(base_log_path, "flashlogs")
    tlogs_dir = os.path.join(base_log_path, "tlogs")

    os.makedirs(flashlogs_dir, exist_ok=True)
    os.makedirs(tlogs_dir, exist_ok=True)

   
    docker_monitor = DockerMonitor()
    host_monitor = HostMonitor()
    net_monitor = NetworkMonitor()
    socket_monitor = SocketMonitor()

    if drone_reset:
        # Reset the simulation
        print("Resetting GCS logs and restarting MAVProxy...")
        requests.post(f"http://localhost:8000/reset")

    allow_unsigned = "False"
    execution_record["configuration"]["allow_unsigned"] = allow_unsigned

    commands = [
        "pkill -9 -f mavproxy.py || true;",
        "rm -f /home/user/Documents/mavproxy/*.tlog* || true;",

        f"export TZ='Etc/GMT-2'; /usr/bin/python3 /usr/local/bin/mavproxy.py --master=udp:0.0.0.0:14550 --logfile=/home/user/Documents/mavproxy/telemetry.tlog --cmd='signing key password;set allow_unsigned {allow_unsigned};repeat add 1 ping' | ts '[%Y-%m-%d %H:%M:%S]' > /home/user/Documents/mavproxy/latency.log 2>&1"
    ]

    for cmd in commands:
        subprocess.run(["docker", "exec", "-dt", "ground-control-station-lite", "sh", "-c", cmd])
        time.sleep(1)


    docker_monitor.start()
    host_monitor.start()
    net_monitor.start()
    socket_monitor.start()
    time.sleep(1)
    if drone_reset:
        # Start stages
        for stage in ["stage1", "stage2", "stage3"]:
            print(f"Starting {stage}...")
            requests.post(f"http://localhost:8000/{stage}")
            time.sleep(3)

    print(f"Flying normally for {idle_flight_time} seconds before attack...")
    execution_record["timestamps"]["first_normal_flight"] = get_current_timestamp()
    time.sleep(idle_flight_time)

    
    def start_remote_attack(name, sec):
        payload = {
            "attack_name": name,
            "duration": sec
        }

        try:
            response = requests.post(ATTACKER_URL, json=payload)
            if response.status_code == 200:
                print(f"[TARGET] Successfully triggered {name} on Attacker.")
                return 0
            else:
                print(f"[TARGET] Attacker rejected request: {response.text}")
                return -1
        except Exception as e:
            print(f"[TARGET] Connection error: {e}")
            return -1

    response = start_remote_attack(attack_function, attack_flight_time)
    execution_record["timestamps"]["attack"] = get_current_timestamp()
    if(response == 0):
        print(f"Executing attack function: {attack_function} for {attack_flight_time} seconds...")
    else:
        print(f"Failed to trigger attack function: {attack_function}. Proceeding with baseline sleep for {attack_flight_time} seconds...")
    
    time.sleep(attack_flight_time)
        
    # execution_record["attack_function"] = loop_function(attack_time, attack_function)
    
    # execution_record["timestamps"]["second_normal_flight"] = get_current_timestamp()
    # print(f"Flying normally for another {flight_time} seconds after attack...")
    # time.sleep(flight_time)

    print(f"Saving logs to {base_log_path}")

   
    subprocess.run(["docker", "cp", "flight-controller-lite:/ardupilot/logs/.", flashlogs_dir])

    print("Downloading tlogs...")
    subprocess.run(["docker", "cp", "ground-control-station-lite:/home/user/Documents/mavproxy/telemetry.tlog", tlogs_dir])
    
    if os.path.exists(tlogs_dir):
        tlog_file_path = os.path.join(tlogs_dir, "telemetry.tlog")
        print(f"Processing logs in {tlogs_dir}...")
        print("Running mavlogdump...")
        dump_cmd = f"{os.path.join(python_venv_path, 'mavlogdump.py')} --robust --show-seq --show-source '{tlog_file_path}' > '{base_log_path}/mavlogdump_output.txt'"
        subprocess.run(dump_cmd, shell=True)


        print("Running mavloss...")
        loss_cmd = f"{os.path.join(python_venv_path, 'python')} {os.path.join(working_directory, 'logs', 'mav-packet-loss.py')} {base_log_path}/mavlogdump_output.txt"
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
            docker_stats = docker_monitor.stop()
            host_stats = host_monitor.stop()
            net_stats = net_monitor.stop() 
            sock_stats = socket_monitor.stop()


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
            "host_stats": host_stats,
            "latency_stats": latency_data,
            "net_stats": net_stats,
            "sock_stats": sock_stats
        }

        
        # print(f"combined logs: {combined_log}")

        with open(os.path.join(base_log_path, 'log.json'), 'w') as f:
            json.dump(combined_log, f, indent=4)


        generate_latency_trend_chart(os.path.join(base_log_path, 'log.json'), os.path.join(base_log_path, 'latency_trend.png'))
        generate_combined_socket_chart(os.path.join(base_log_path, 'log.json'), os.path.join(base_log_path, 'socket_chart.png'), attack_function)
        generate_combined_system_stress_chart(os.path.join(base_log_path, 'log.json'), os.path.join(base_log_path, 'system_stress.png'), attack_function)
        baseline_tlog_path = os.path.join(working_directory, "logs", "baseline", "comparison", "tlogs", "telemetry.tlog")
        baseline_json_path = os.path.join(working_directory, "logs", "baseline", "comparison", "log.json")
        
        with open(baseline_json_path, 'r') as f:
            baseline_data = json.load(f)

        baseline_attack_start = baseline_data["execution_record"]["timestamps"]["attack"]

        generate_normalized_jitter_chart(baseline_tlog_path, baseline_attack_start, os.path.join(tlogs_dir, 'telemetry.tlog'), execution_record["timestamps"]["attack"], attack_flight_time, attack_function, os.path.join(base_log_path, 'jitter_graph.png'))

        print(f"Analysis complete. Results saved in {base_log_path}")
    else:
        print(f"Error: {tlog_file_path} not found. Skipping analysis.")
    execution_record["timestamps"]["end"] = get_current_timestamp()
    print("Done.")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test pipeline for drone attack scenarios.")
    parser.add_argument(
        "--attack", 
        type=str, 
        default=None, 
        help="Name of the attack function to run: None for baseline."
    )
    parser.add_argument(
        "--idle", 
        type=int,
        dest="idle_flight_time",
        default=3, 
        help="Amount of idle flight time in seconds."
    )
    parser.add_argument(
        "--attack-time", 
        type=int,
        dest="attack_flight_time", 
        default=20, 
        help="Amount of attack time in seconds."
    )
    parser.add_argument(
        "--no-reset", 
        dest="drone_reset", 
        action="store_false",
        default=True, 
        help="Include this flag to skip resetting the flight controller"
    )
    args = parser.parse_args()
    current_attack = None if args.attack == "None" else args.attack
    drone_reset = args.drone_reset
    idle_flight_time = args.idle_flight_time
    attack_flight_time = args.attack_flight_time
    main(current_attack, drone_reset, idle_flight_time, attack_flight_time)