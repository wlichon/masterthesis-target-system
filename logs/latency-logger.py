import re
import json
import os
import datetime
import subprocess
import subprocess

# def log_to_json(latency_val, sent_timestamp, filename="log.json"):
#     """Logs the latency and original send timestamp to log.json."""
#     data = {"latency": []}
    
#     # Load existing data if file exists
#     if os.path.exists(filename):
#         try:
#             with open(filename, 'r') as f:
#                 data = json.load(f)
#                 if "latency" not in data:
#                     data["latency"] = []
#         except (json.JSONDecodeError, IOError):
#             pass

#     # Append new entry with both values
#     data["latency"].append({
#         "sent_at": sent_timestamp,
#         "value_ms": round(latency_val, 3)
#     })
    
#     # Write back to file
#     with open(filename, 'w') as f:
#         json.dump(data, f, indent=4)
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

def OLD_parse_mavlog(content):
    # Regex to capture: Timestamp, tc value, ts value, srcSystem, and srcComponent
    # Pattern looks for: 2026-04-05 18:58:31.88: TIMESYNC {tc1 : 0, ts1 : 1775408311881843968} srcSystem=255 srcComponent=230
    pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+): TIMESYNC"
    )

    pending_pings = {} # Key: ts1 value, Value: TimesyncMsg object (sent)
    latency_stats = []
    for line in content.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        
        log_timestamp = match.groups()[0]
        tc = re.search(r"tc1 : (\d+)", line)
        tc = tc.group(1) if tc else None
        ts1 = re.search(r"ts1 : (\d+)", line)
        ts1 = ts1.group(1) if ts1 else None
        src_sys = re.search(r"srcSystem=(\d+)", line)
        src_sys = src_sys.group(1) if src_sys else None
        src_comp = re.search(r"srcComponent=(\d+)", line)
        src_comp = src_comp.group(1) if src_comp else None

        if(src_sys == 1):
            print("here")

        # Convert log string timestamp to microseconds for calculation
        dt = datetime.strptime(log_timestamp, "%Y-%m-%d %H:%M:%S.%f")
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

def TEST_parse_mavlog(content):
    # print("from parse_mavlog")
    # Regex to capture: Timestamp, tc value, ts value, srcSystem, and srcComponent
    # Pattern looks for: 2026-04-05 18:58:31.88: TIMESYNC {tc1 : 0, ts1 : 1775408311881843968} srcSystem=255 srcComponent=230
    pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+): TIMESYNC \{tc1 : (\d+), ts1 : (\d+)\} srcSystem=(\d+) srcComponent=(\d+)"
    )

    pending_pings = {} # Key: ts1 value, Value: TimesyncMsg object (sent)
    latency_stats = []

    for line in content.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        
        print(line)
        # Extract data from the regex groups
        log_time_str, tc, ts1, src_sys, src_comp = match.groups()
        
        # Convert values to correct types
        tc = int(tc)
        ts1 = int(ts1)
        src_sys = int(src_sys)
        src_comp = int(src_comp)

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

if __name__ == "__main__":
    mavlogdump_content = subprocess.check_output(f"cat /home/wiktor/Desktop/Damn-Vulnerable-Drone/logs/mavlink_flood/20260405_224640/mavlogdump_output.txt", shell=True, text=True, stderr=subprocess.STDOUT)

    print(parse_mavlog(mavlogdump_content))