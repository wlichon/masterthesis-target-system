import re
import matplotlib.pyplot as plt
from datetime import datetime


import re
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def generate_normalized_jitter_chart_mavlogdump(baseline_path, b_start_str, attack_path, a_start_str, duration_sec, output_image='normalized_jitter.png'):
    """
    Normalizes two logs so they both start counting from 0s at the attack start.
    b_start_str/a_start_str format: "YYYY-MM-DD HH:MM:SS.ms"
    """
    def get_normalized_data(filepath, start_time_str):
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d_%H:%M:%S")
        end_time = start_time + timedelta(seconds=duration_sec)
        
        times = []
        pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+): ATTITUDE")
        
        with open(filepath, 'r') as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S.%f")
                    # Only keep data within the window: [start_time, start_time + duration]
                    if start_time <= dt <= end_time:
                        # Normalize: current_time - start_time = seconds from 0
                        offset_sec = (dt - start_time).total_seconds()
                        times.append((offset_sec, dt))
        
        # Calculate jitter (ms) based on the original datetime objects
        jitter = []
        x_axis = []
        for i in range(1, len(times)):
            diff = (times[i][1] - times[i-1][1]).total_seconds() * 1000
            jitter.append(diff)
            x_axis.append(times[i][0]) # Use the normalized seconds for X
            
        return x_axis, jitter

    # Extract and normalize
    b_x, b_jitter = get_normalized_data(baseline_path, b_start_str)
    a_x, a_jitter = get_normalized_data(attack_path, a_start_str)

    # Plotting
    plt.figure(figsize=(12, 6))
    plt.plot(b_x, b_jitter, label='Baseline', color='#1f77b4', alpha=0.7, marker='^', markersize=6, linestyle='None')
    plt.plot(a_x, a_jitter, label='Attack', color='#d62728', alpha=0.8, marker='X', markersize=6, linestyle='None')

    # plt.plot(b_times, b_jitter, label='Baseline (Clean Link)', color='#1f77b4', alpha=0.8, marker='o', markersize=3, linestyle='None')
    # plt.plot(a_times, a_jitter, label='Attack (DoS Active)', color='#d62728', alpha=0.8, marker='x', markersize=3, linestyle='None')

    plt.title(f'Normalized Telemetry Jitter ({duration_sec}s Attack Window)', fontsize=14)
    plt.xlabel('Seconds from Attack Start (t=0)', fontweight='bold')
    plt.ylabel('Inter-message Interval (ms)', fontweight='bold')
    plt.legend()
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    
    # # Use log scale if your attack spikes are massive (like the 45s one found earlier)
    # if max(a_jitter + b_jitter) > 1000:
    #     plt.yscale('log')
    #     plt.ylabel('Interval (ms) [Log Scale]', fontweight='bold')

    plt.xlim(0, duration_sec)
    plt.tight_layout()
    plt.savefig(output_image)
    plt.show()

import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pymavlink import mavutil

def generate_normalized_jitter_chart(baseline_tlog, b_start_str, attack_tlog, a_start_str, duration_sec, attack_function, output_image='normalized_jitter.png'):
    """
    Extracts high-precision timestamps directly from TLOG files using pymavlink.
    Normalizes time to 0s at the start of the attack.
    """

    def get_normalized_data(tlog_path, start_time_str):
        # Handle the potential underscore in log.json timestamps
        fmt = "%Y-%m-%d_%H:%M:%S" if "_" in start_time_str else "%Y-%m-%d %H:%M:%S"
        start_time_dt = datetime.strptime(start_time_str, fmt)
        start_ts = start_time_dt.timestamp()
        end_ts = start_ts + duration_sec
        
        # Connect to the raw TLOG
        mavlog = mavutil.mavlink_connection(tlog_path)
        
        times = []
        while True:
            msg = mavlog.recv_match(type='ATTITUDE', blocking=False)
            if msg is None:
                break
            
            # Use the high-precision GCS reception timestamp (microsecond accuracy)
            curr_ts = getattr(msg, '_timestamp', 0)
            
            if start_ts <= curr_ts <= end_ts:
                offset_sec = curr_ts - start_ts
                times.append((offset_sec, curr_ts))
        
        jitter = []
        x_axis = []
        for i in range(1, len(times)):
            # diff is in seconds, convert to milliseconds (accurate to 1000ms+)
            diff_ms = (times[i][1] - times[i-1][1]) * 1000
            jitter.append(diff_ms)
            x_axis.append(times[i][0])
            
        return x_axis, jitter

    # Extract and normalize using pymavlink on the raw log files
    b_x, b_jitter = get_normalized_data(baseline_tlog, b_start_str)
    a_x, a_jitter = get_normalized_data(attack_tlog, a_start_str)

    plt.figure(figsize=(12, 6))
    plt.plot(b_x, b_jitter, label='Baseline', color='#1f77b4', 
             alpha=0.7, marker='^', markersize=6, linestyle='None')
    plt.plot(a_x, a_jitter, label='Attack', color='#d62728', 
             alpha=0.8, marker='x', markersize=6, linestyle='None')

    plt.title(f'{attack_function} - Telemetry Jitter', fontsize=14)
    plt.xlabel('Elapsed Time (seconds)', fontweight='bold')
    plt.ylabel('Inter-message Interval (ms)', fontweight='bold')
    total_max_jitter = max(a_jitter + b_jitter)

    # 2. Check the condition and set the limit with 250ms padding
    if total_max_jitter > 1000:
        plt.ylim(0, total_max_jitter + 250)
    else:
        plt.ylim(0, 1000)
    # plt.ylim(0, 500)
    plt.legend()
    print(total_max_jitter)
    plt.grid(True, which='both', linestyle='--', alpha=0.5)

    # # Log scale is recommended due to the massive blackout spikes (e.g. 45s) observed
    # if a_jitter and max(a_jitter) > 1000:
    #     plt.yscale('log')
    #     plt.ylabel('Interval (ms) [Log Scale]', fontweight='bold')

    plt.xlim(0, duration_sec)
    plt.tight_layout()
    plt.savefig(output_image)
    plt.show()

# Usage:

# target_tlog = '/home/lichon/Desktop/masterthesis/logs/empty_payload_flood/unfiltered/tlogs/telemetry.tlog'
# target_time = ""
# target_output = ""
# attack_function = ""
# generate_normalized_jitter_chart('/home/lichon/Desktop/masterthesis/logs/baseline/comparison/tlogs/telemetry.tlog', "2026-04-20_19:32:44", target_tlog, target_time, 60, attack_function, target_output)