from datetime import datetime
import json
import os
import numpy as np
from scipy import stats
from collections import defaultdict
import glob

log_pattern = os.path.join('logs', 'random_payload_flood', 'iptables-[1-9]', 'log.json')


cpu_data_by_timestamp = defaultdict(list)


def parse_timestamp(ts):
    """
    Standardizes inconsistent timestamp formats into a float (Unix epoch).
    """
    if isinstance(ts, (int, float)):
        return float(ts)
    
    formats = [
        "%Y-%m-%d %H:%M:%S",    # 2026-04-22 00:02:09
        "%Y-%m-%d_%H:%M:%S"     # 2026-04-22_00:01:05
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(str(ts), fmt).timestamp()
        except ValueError:
            continue
    return None

def process_logs():
    log_files = glob.glob(log_pattern)
    cpu_values_during_attack = []
    
    if not log_files:
        print(f"No files found matching pattern: {log_pattern}")
        return
    for filepath in log_files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
                attack_start_time = parse_timestamp(data.get('execution_record', {}).get('timestamps',{}).get('attack'))
                cutoff_time = attack_start_time + 60
                if attack_start_time is None:
                    print(f"Warning: No attack timestamp found in {filepath}. Skipping.")
                    continue
            
                for entry in data.get('host_stats', []):
                    sample_ts = parse_timestamp(entry.get('timestamp'))
                    cpu_val = entry.get('host_cpu_percent')
                    print(f'{sample_ts} {attack_start_time}')
                    if sample_ts is not None and cpu_val is not None:
                        if sample_ts >= attack_start_time and sample_ts < cutoff_time:
                            cpu_values_during_attack.append(cpu_val)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Skipping {filepath} due to error: {e}")

    if not cpu_values_during_attack:
        print("No CPU data found in the provided logs.")
        return


    data_array = np.array(cpu_values_during_attack)
    n = len(data_array)
    mean_val = np.mean(data_array)
    sem = stats.sem(data_array)  # Standard Error of the Mean
    
    # 95% Confidence Interval using t-distribution
    confidence = 0.95
    h = sem * stats.t.ppf((1 + confidence) / 2., n - 1)
    
    ci_lower = mean_val - h
    ci_upper = mean_val + h

    print(f"--- Global Performance Summary ---")
    print(f"Total Samples (n): {n}")
    print(f"Mean CPU Load:     {mean_val:.4f}%")
    print(f"95% CI Lower:      {ci_lower:.4f}%")
    print(f"95% CI Upper:      {ci_upper:.4f}%")
    print(f"Standard Dev:      {np.std(data_array, ddof=1):.4f}%")

if __name__ == "__main__":
    process_logs()