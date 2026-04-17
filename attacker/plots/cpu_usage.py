import json
import pandas as pd
import matplotlib.pyplot as plt

def generate_gcs_cpu_chart(json_filepath, output_image):
    # 1. Load the log data
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON: {e}")
        return

    # 2. Extract docker stats
    docker_stats = data.get('docker_stats', [])
    if not docker_stats:
        print("No 'docker_stats' found in the JSON file.")
        return

    df = pd.DataFrame(docker_stats)
    
    # 3. Identify the GCS container 
    # (Matches any container name containing 'ground-control-station')
    gcs_name = next((n for n in df['container'].unique() if 'ground-control-station' in n), None)
    
    if not gcs_name:
        print("GCS container not found in the stats.")
        return

    # 4. Filter and Prepare Data
    gcs_df = df[df['container'] == gcs_name].copy()
    gcs_df['timestamp'] = pd.to_datetime(gcs_df['timestamp'])
    
    # Convert "0.50%" string to 0.50 float
    gcs_df['cpu_percent'] = gcs_df['cpu_percent'].apply(
        lambda x: float(x.replace('%', '')) if isinstance(x, str) else x
    )
    
    # Sort by time to ensure a continuous line
    gcs_df = gcs_df.sort_values('timestamp')

    # 5. Plotting
    plt.figure(figsize=(12, 6))
    plt.plot(
        gcs_df['timestamp'], 
        gcs_df['cpu_percent'], 
        label=f'{gcs_name} CPU %', 
        color='tab:red', 
        linewidth=2, 
        marker='.'
    )
    
    plt.title(f'GCS CPU Usage Over Time ({gcs_name})', fontsize=14)
    plt.xlabel('Time (UTC)', fontsize=12)
    plt.ylabel('CPU Usage (%)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # 6. Save result
    plt.savefig(output_image)
    print(f"Success! Chart saved as {output_image}")

def generate_fw_cpu_chart(json_filepath, output_image):
    # 1. Load the log data
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON: {e}")
        return

    # 2. Extract docker stats
    docker_stats = data.get('docker_stats', [])
    if not docker_stats:
        print("No 'docker_stats' found in the JSON file.")
        return

    df = pd.DataFrame(docker_stats)
    
    # 3. Identify the GCS container 
    # (Matches any container name containing 'ground-control-station')
    fw_name = next((n for n in df['container'].unique() if 'gcs-firewall' in n), None)
    
    if not fw_name:
        print("FW container not found in the stats.")
        return

    # 4. Filter and Prepare Data
    fw_df = df[df['container'] == fw_name].copy()
    fw_df['timestamp'] = pd.to_datetime(fw_df['timestamp'])
    
    # Convert "0.50%" string to 0.50 float
    fw_df['cpu_percent'] = fw_df['cpu_percent'].apply(
        lambda x: float(x.replace('%', '')) if isinstance(x, str) else x
    )
    
    # Sort by time to ensure a continuous line
    fw_df = fw_df.sort_values('timestamp')

    # 5. Plotting
    plt.figure(figsize=(12, 6))
    plt.plot(
        fw_df['timestamp'], 
        fw_df['cpu_percent'], 
        label=f'{fw_name} CPU %', 
        color='tab:red', 
        linewidth=2, 
        marker='.'
    )
    
    plt.title(f'FW CPU Usage Over Time ({fw_name})', fontsize=14)
    plt.xlabel('Time (UTC)', fontsize=12)
    plt.ylabel('CPU Usage (%)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # 6. Save result
    plt.savefig(output_image)
    print(f"Success! Chart saved as {output_image}")


if __name__ == "__main__":
    generate_gcs_cpu_chart('/home/wiktor/Desktop/Damn-Vulnerable-Drone/logs/udp_limited_flood/2026-04-12_23:02:31/log.json', './attacker/plots/pngs/gcs_cpu_chart.png')
    generate_fw_cpu_chart('/home/wiktor/Desktop/Damn-Vulnerable-Drone/logs/udp_limited_flood/2026-04-12_23:02:31/log.json', './attacker/plots/pngs/fw_cpu_chart.png')