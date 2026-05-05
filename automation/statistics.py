from datetime import datetime
import json
import os
import numpy as np
from scipy import stats
from collections import defaultdict
import glob
from pymavlink import mavutil


cpu_data_by_timestamp = defaultdict(list)

def parse_timestamp(ts):
    """
    formats inconsistent timestamps into a float (Unix epoch).
    """
    if isinstance(ts, (int, float)):
        return float(ts)
    
    try:
        return datetime.fromisoformat(str(ts)).timestamp()
    except ValueError:
        pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d_%H:%M:%S"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(str(ts), fmt).timestamp()
        except ValueError:
            continue
    return None

def process_logs(log_pattern):
    log_files = glob.glob(log_pattern)
    cpu_values_during_attack = []
    attack_duration = 300.0
    
    if not log_files:
        print(f"No files found matching pattern: {log_pattern}")
        return
    for filepath in log_files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
                attack_start_time = parse_timestamp(data.get('execution_record', {}).get('timestamps',{}).get('attack'))
                cutoff_time = attack_start_time + attack_duration
                if attack_start_time is None:
                    print(f"Warning: No attack timestamp found in {filepath}. Skipping.")
                    continue
            
                for entry in data.get('host_stats', []):
                    sample_ts = parse_timestamp(entry.get('timestamp'))
                    cpu_val = entry.get('host_cpu_percent')
                    # print(f'{sample_ts} {attack_start_time}')
                    if sample_ts is not None and cpu_val is not None:
                        if attack_start_time <= sample_ts < cutoff_time:
                            cpu_values_during_attack.append(cpu_val)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Skipping {filepath} due to error: {e}")

    if not cpu_values_during_attack:
        print("No CPU data found in the provided logs.")
        return


    data_array = np.array(cpu_values_during_attack)
    n = len(data_array)
    mean_val = np.mean(data_array)
    median_val = np.median(data_array)

    print(f"--- Performance Summary ---")
    print(f"Total Samples (n): {n}")
    print(f"Mean CPU Load:     {mean_val:.4f}%")
    print(f"Median CPU Load:   {median_val:.4f}%")
    print(f"Standard Dev:      {np.std(data_array, ddof=1):.4f}%")

def get_cpu_stats(log_pattern, attack_duration=300.0):
    cpu_values = []
    log_files = glob.glob(log_pattern)
    
    for filepath in log_files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                attack_start_time = parse_timestamp(data.get('execution_record', {}).get('timestamps',{}).get('attack'))
                if attack_start_time is None: continue
                
                cutoff_time = attack_start_time + attack_duration
                
                for entry in data.get('host_stats', []):
                    sample_ts = parse_timestamp(entry.get('timestamp'))
                    cpu_val = entry.get('host_cpu_percent')
                    if sample_ts is not None and cpu_val is not None:
                        if attack_start_time <= sample_ts < cutoff_time:
                            cpu_values.append(cpu_val)
        except Exception:
            continue
    return np.array(cpu_values)

def compare_performance(ebpf_pattern, iptables_pattern):
    ebpf_data = get_cpu_stats(ebpf_pattern)
    iptables_data = get_cpu_stats(iptables_pattern)

    if len(ebpf_data) == 0 or len(iptables_data) == 0:
        print("Error: Missing data in one or both categories.")
        return

    # Mann-Whitney U Test (Non-parametric)
    # alternative='less' tests hypothesis that ebpf_data is significantly SMALLER than iptables_data
    p_value = stats.mannwhitneyu(ebpf_data, iptables_data, alternative='less')

    mean_ebpf = np.mean(ebpf_data)
    mean_iptables = np.mean(iptables_data)

    print(f"--- Significance Test Results ---")
    print(f"eBPF Mean CPU:    {mean_ebpf:.4f}% (n={len(ebpf_data)})")
    print(f"iptables Mean CPU: {mean_iptables:.4f}% (n={len(iptables_data)})")
    print(f"p-value:           {p_value:.6f}")

    if p_value < 0.05:
        print("Result: Statistically significant. eBPF results in lower CPU usage.")
    else:
        print("Result: Not statistically significant.")


def calculate_aggregate_jitter(log_pattern):
    # Find all matching directories (e.g., logs/baseline/run_1, logs/baseline/run_2)
    directories = glob.glob(log_pattern)
    
    if not directories:
        return {"error": "No directories found matching the provided pattern."}

    all_jitter_samples = []
    processed_count = 0

    for directory in directories:
        if not os.path.isdir(directory):
            continue
            
        log_json_path = os.path.join(directory, 'log.json')
        tlog_path = os.path.join(directory, 'tlogs', 'telemetry.tlog')
        
        if not os.path.exists(log_json_path) or not os.path.exists(tlog_path):
            continue

        try:
            with open(log_json_path, 'r') as f:
                metadata = json.load(f)
            
            exec_rec = metadata.get("execution_record", {})
            start_time_str = exec_rec.get("timestamps", {}).get("attack")
            duration_sec = exec_rec.get("configuration", {}).get("attack_time", 60)

            if not start_time_str:
                continue

            fmt = "%Y-%m-%d_%H:%M:%S" if "_" in start_time_str else "%Y-%m-%d %H:%M:%S"
            start_ts = datetime.strptime(start_time_str, fmt).timestamp()
            end_ts = start_ts + duration_sec

            mavlog = mavutil.mavlink_connection(tlog_path)
            arrival_times = []
            
            while True:
                msg = mavlog.recv_match(type='ATTITUDE', blocking=False)
                if msg is None: break
                
                curr_ts = getattr(msg, '_timestamp', 0)
                if start_ts <= curr_ts <= end_ts:
                    arrival_times.append(curr_ts)

            if len(arrival_times) >= 2:
                file_jitter = np.diff(arrival_times) * 1000
                all_jitter_samples.extend(file_jitter)
                processed_count += 1
                
        except Exception as e:
            continue

    if not all_jitter_samples:
        return {"error": "No valid telemetry data was found within the attack windows."}

    data = np.array(all_jitter_samples)
    mean_val = np.mean(data)
    std_val = np.std(data)
    n = len(data)

    return {
        "mean_ms": round(float(mean_val), 4),
        "std_dev": round(float(std_val), 4),
        "total_samples": n,
        "runs_processed": processed_count
    }


def calculate_aggregate_host_cpu_load(log_pattern):
    directories = glob.glob(log_pattern)
    
    all_cpu_samples = []
    processed_runs = 0

    for directory in directories:
        if not os.path.isdir(directory):
            continue
            
        log_json_path = os.path.join(directory, 'log.json')
        
        if not os.path.exists(log_json_path):
            print(f"Skipping {directory}: No log.json found.")
            continue

        try:
            with open(log_json_path, 'r') as f:
                data = json.load(f)
            
            # Extract attack window
            exec_rec = data.get("execution_record", {})
            start_str = exec_rec.get("timestamps", {}).get("attack")
            duration_sec = exec_rec.get("configuration", {}).get("attack_time", 60)

            if not start_str:
                print(f"Skipping {directory}: No attack timestamp in log.json.")
                continue

            fmt = "%Y-%m-%d_%H:%M:%S" if "_" in start_str else "%Y-%m-%d %H:%M:%S"
            start_ts = datetime.strptime(start_str, fmt).timestamp()
            end_ts = start_ts + duration_sec

            host_stats = data.get("host_stats", [])
            run_samples = []
            
            for sample in host_stats:
                raw_ts = sample.get("timestamp")
                cpu_val = sample.get("host_cpu_percent")

                if raw_ts and cpu_val is not None:
                    clean_ts = raw_ts.replace('Z', '')
                    sample_ts = datetime.fromisoformat(clean_ts).timestamp()

                    if start_ts <= sample_ts <= end_ts:
                        run_samples.append(float(cpu_val))
            
            if run_samples:
                all_cpu_samples.extend(run_samples)
                processed_runs += 1
            else:
                print(f"Warning: No CPU samples found within attack window for {directory}")
                
        except Exception as e:
            print(f"Error processing {log_json_path}: {e}")
            continue

    if not all_cpu_samples:
        return "No CPU data found in the provided logs."

    data_arr = np.array(all_cpu_samples)
    mean_val = np.mean(data_arr)
    std_val = np.std(data_arr)
    n = len(data_arr)

    return {
        "mean_cpu_percent": round(float(mean_val), 2),
        "std_dev": round(float(std_val), 2),
        "total_samples": n,
        "runs_processed": processed_runs
    }

def calculate_aggregate_gcs_cpu_load(log_pattern, container_name='ground-control-station-lite'):
    directories = glob.glob(log_pattern)
    if not directories:
        return {"error": "No directories found matching the provided pattern."}

    all_cpu_samples = []
    processed_runs = 0

    for directory in directories:
        if not os.path.isdir(directory):
            continue
            
        log_json_path = os.path.join(directory, 'log.json')
        if not os.path.exists(log_json_path):
            continue

        try:
            with open(log_json_path, 'r') as f:
                data = json.load(f)
            
            exec_rec = data.get("execution_record", {})
            start_str = exec_rec.get("timestamps", {}).get("attack")
            duration_sec = exec_rec.get("configuration", {}).get("attack_time", 60)

            if not start_str:
                continue

            fmt = "%Y-%m-%d_%H:%M:%S" if "_" in start_str else "%Y-%m-%d %H:%M:%S"
            start_ts = datetime.strptime(start_str, fmt).timestamp()
            end_ts = start_ts + duration_sec

            docker_stats = data.get("docker_stats", [])
            run_samples = []
            
            for sample in docker_stats:
                if sample.get("container") != container_name:
                    continue

                raw_ts = sample.get("timestamp")
                cpu_str = sample.get("cpu_percent")

                if raw_ts and cpu_str:
                    clean_ts = raw_ts.replace('T', ' ').replace('Z', '')
                    sample_ts = datetime.fromisoformat(clean_ts).timestamp()

                    if start_ts <= sample_ts <= end_ts:
                        cpu_val = float(cpu_str.replace('%', '').strip())
                        run_samples.append(cpu_val)
            
            if run_samples:
                all_cpu_samples.extend(run_samples)
                processed_runs += 1
                
        except Exception as e:
            print(f"Error processing {log_json_path}: {e}")
            continue

    if not all_cpu_samples:
        return {"error": f"No CPU data found for container '{container_name}' in attack windows."}

    data_arr = np.array(all_cpu_samples)
    mean_val = np.mean(data_arr)
    std_val = np.std(data_arr)
    n = len(data_arr)


    return {
        "container": container_name,
        "mean_cpu_percent": round(float(mean_val), 2),
        "std_dev": round(float(std_val), 2),
        "total_samples": n,
        "runs_processed": processed_runs
    }


def calculate_aggregate_net_rx_stats(log_pattern):
    directories = glob.glob(log_pattern)
    if not directories:
        return {"error": "No directories found matching the provided pattern."}

    all_rx_samples = []
    processed_runs = 0

    for directory in directories:
        if not os.path.isdir(directory):
            continue
            
        log_json_path = os.path.join(directory, 'log.json')
        if not os.path.exists(log_json_path):
            continue

        try:
            with open(log_json_path, 'r') as f:
                data = json.load(f)
            
            exec_rec = data.get("execution_record", {})
            start_str = exec_rec.get("timestamps", {}).get("attack")
            duration_sec = exec_rec.get("configuration", {}).get("attack_time", 60)

            if not start_str:
                continue

            fmt = "%Y-%m-%d_%H:%M:%S" if "_" in start_str else "%Y-%m-%d %H:%M:%S"
            start_ts = datetime.strptime(start_str, fmt).timestamp()
            end_ts = start_ts + duration_sec

            net_stats = data.get("net_stats", [])
            run_samples = []
            
            for sample in net_stats:
                raw_ts = sample.get("timestamp")
                rx_val = sample.get("rx_mbps")

                if raw_ts and rx_val is not None:
                    # Normalize timestamp format (handles ' ' or 'T')
                    clean_ts = raw_ts.replace(' ', 'T').replace('Z', '')
                    sample_ts = datetime.fromisoformat(clean_ts).timestamp()

                    if start_ts <= sample_ts <= end_ts:
                        run_samples.append(float(rx_val))
            
            if run_samples:
                all_rx_samples.extend(run_samples)
                processed_runs += 1
                
        except Exception as e:
            print(f"Error processing {log_json_path}: {e}")
            continue

    if not all_rx_samples:
        return {"error": "No network throughput data found in attack windows."}

    data_arr = np.array(all_rx_samples)
    mean_val = np.mean(data_arr)
    std_val = np.std(data_arr)
    max_val = np.max(data_arr)
    n = len(data_arr)
    

    return {
        "metric": "rx_mbps",
        "mean_mbps": round(float(mean_val), 4),
        "std_dev": round(float(std_val), 4),
        "max_mbps": round(float(max_val), 4),
        "total_samples": n,
        "runs_processed": processed_runs
    }


log_pattern = os.path.join('logs', 'baseline', '2026*')


# jitter_stats = calculate_aggregate_jitter(log_pattern)
# print(jitter_stats)
host_stats = calculate_aggregate_host_cpu_load(log_pattern)
print(host_stats)
# gcs_stats = calculate_aggregate_gcs_cpu_load(log_pattern)
# print(gcs_stats)
# net_stats = calculate_aggregate_net_rx_stats(log_pattern)
# print(net_stats)

# process_logs(log_pattern)


# compare_performance(os.path.join('logs', 'stress_test_random_payload_flood', 'ebpf-final-[1-5]', 'log.json'), os.path.join('logs', 'stress_test_random_payload_flood', 'iptables-final-[1-5]', 'log.json'))

# if __name__ == "__main__":
#     process_logs()