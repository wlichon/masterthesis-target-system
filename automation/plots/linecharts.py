import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import ticker

def generate_gcs_cpu_chart(json_filepath, output_image):
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON: {e}")
        return


    docker_stats = data.get('docker_stats', [])
    if not docker_stats:
        print("No 'docker_stats' found in the JSON file.")
        return

    df = pd.DataFrame(docker_stats)
    
    gcs_name = next((n for n in df['container'].unique() if 'ground-control-station' in n), None)
    
    if not gcs_name:
        print("GCS container not found in the stats.")
        return

    gcs_df = df[df['container'] == gcs_name].copy()
    gcs_df['timestamp'] = pd.to_datetime(gcs_df['timestamp'])
    
    gcs_df['cpu_percent'] = gcs_df['cpu_percent'].apply(
        lambda x: float(x.replace('%', '')) if isinstance(x, str) else x
    )
    

    gcs_df = gcs_df.sort_values('timestamp')

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
    
    plt.savefig(output_image)
    print(f"Success! Chart saved as {output_image}")

def generate_fw_cpu_chart(json_filepath, output_image):
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON: {e}")
        return

    host_stats = data.get('host_stats', [])
    if not host_stats:
        print("No 'host_stats' found in the JSON file.")
        return

    fw_df = pd.DataFrame(host_stats).copy()
    
    fw_df['timestamp'] = pd.to_datetime(fw_df['timestamp'])
    
    fw_df = fw_df.sort_values('timestamp')

    plt.figure(figsize=(12, 6))
    plt.plot(
        fw_df['timestamp'], 
        fw_df['host_cpu_percent'], 
        label=f'Firewall CPU %', 
        color='tab:red', 
        linewidth=2, 
        marker='.'
    )
    
    plt.title(f'Firewall CPU Usage Over Time', fontsize=14)
    plt.xlabel('Time (UTC)', fontsize=12)
    plt.ylabel('CPU Usage (%)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    plt.savefig(output_image)
    print(f"Success! Chart saved as {output_image}")


def generate_network_throughput_chart(json_filepath, output_image):
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON: {e}")
        return
    
    net_stats = data.get('net_stats', [])
    if not net_stats:
        print("No 'net_stats' found in the JSON file.")
        return

    net_df = pd.DataFrame(net_stats).copy()
    
    net_df['timestamp'] = pd.to_datetime(net_df['timestamp'])
    
    net_df = net_df.sort_values('timestamp')
    plt.figure(figsize=(12, 6))
    plt.plot(
        net_df['timestamp'], 
        net_df['rx_mbps'], 
        label='Incoming Traffic (Mbps)', 
        color='tab:blue', 
        linewidth=2, 
        marker='o',
        markersize=4
    )
    
    plt.title('Firewall Network Ingress Throughput', fontsize=14)
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Throughput (Mbps)', fontsize=12)
    plt.legend(loc='upper right')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
    

    plt.savefig(output_image)
    plt.close()
    print(f"Success! Network Throughput chart saved as {output_image}")


def generate_socket_queue_chart(json_filepath, output_image):
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON: {e}")
        return

    socket_stats = data.get('sock_stats', [])
    if not socket_stats:
        print("No 'sock_stats' found in the JSON file.")
        return

    socket_df = pd.DataFrame(socket_stats).copy()
    
    socket_df['timestamp'] = pd.to_datetime(socket_df['timestamp'])
    
    socket_df = socket_df.sort_values('timestamp')

    plt.figure(figsize=(12, 6))
    plt.plot(
        socket_df['timestamp'], 
        socket_df['rx_queue_bytes'], 
        label='Socket Buffer (Recv-Q)', 
        color='tab:orange', 
        linewidth=1.5
    )

    plt.title('GCS Application: UDP Socket Buffer Occupancy', fontsize=14)
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Receive Queue (Bytes)', fontsize=12)
    plt.legend(loc='upper right')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    plt.savefig(output_image)
    plt.close()
    print(f"Success! Socket Queue chart saved as {output_image}")

def generate_combined_system_stress_chart(json_filepath, output_image, attack_function):
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON: {e}")
        return

    fw_df = pd.DataFrame(data.get('host_stats', []))
    net_df = pd.DataFrame(data.get('net_stats', []))
    d_df = pd.DataFrame(data.get('docker_stats', []))

    execution_record = data.get('execution_record')

    if fw_df.empty or net_df.empty or d_df.empty:
        print("Error: Missing one or more data keys in JSON.")
        return

    fw_df['timestamp'] = pd.to_datetime(fw_df['timestamp'])
    net_df['timestamp'] = pd.to_datetime(net_df['timestamp'])
    
    gcs_name = next((n for n in d_df['container'].unique() if 'ground-control-station' in n), "GCS")
    gcs_df = d_df[d_df['container'] == gcs_name].copy()
    gcs_df['timestamp'] = pd.to_datetime(gcs_df['timestamp'])
    
    gcs_df['cpu_percent'] = gcs_df['cpu_percent'].apply(
        lambda x: float(x.replace('%', '')) if isinstance(x, str) else x
    )

    attack_start = execution_record['timestamps']['attack']
    start_time = pd.to_datetime(attack_start.replace('_', ' '))

    fw_df['elapsed'] = (fw_df['timestamp'] - start_time).dt.total_seconds()
    net_df['elapsed'] = (net_df['timestamp'] - start_time).dt.total_seconds()
    gcs_df['elapsed'] = (gcs_df['timestamp'] - start_time).dt.total_seconds()
    max_elapsed = max(fw_df['elapsed'].max(), net_df['elapsed'].max(), gcs_df['elapsed'].max())

    fw_df = fw_df.sort_values('elapsed')
    net_df = net_df.sort_values('elapsed')
    gcs_df = gcs_df.sort_values('elapsed')

    fig, ax1 = plt.subplots(figsize=(14, 7))

    lns1 = ax1.plot(fw_df['elapsed'], fw_df['host_cpu_percent'], 
                    label='Firewall (Host) CPU %', color='tab:red', linewidth=2)
    lns2 = ax1.plot(gcs_df['elapsed'], gcs_df['cpu_percent'], 
                    label='GCS Container CPU %', color='tab:orange', linestyle='--', linewidth=2)
    
    ax1.set_xlabel('Elapsed Time (seconds)', fontsize=12)
    ax1.set_ylabel('CPU Usage (%)', fontsize=12)
    ax1.set_ylim(0, 200) 
    ax1.grid(True, linestyle='--', alpha=0.4)
    ax2 = ax1.twinx()
    lns3 = ax2.plot(net_df['elapsed'], net_df['rx_mbps'], 
                    label='Network Ingress (Mbps)', color='tab:blue', linewidth=2, alpha=0.6)
    
    ax2.set_ylabel('Network Throughput (Mbps)', color='tab:blue', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='tab:blue')

    ax1.set_xlabel('Elapsed Time (seconds)', fontsize=12)
    
    ax1.set_xlim(left=0, right=max_elapsed)
    lns = lns1 + lns2 + lns3
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc='upper left', frameon=True, shadow=True)

    plt.title(f'{attack_function} - Network Load vs. CPU Load', fontsize=14)
    plt.xticks(rotation=45)
    fig.tight_layout()
    
    plt.savefig(output_image)
    plt.close()
    print(f"Correlation chart saved: {output_image}")

def generate_combined_socket_chart(json_filepath, output_image, attack_function):
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON: {e}")
        return

    sock_stats = data.get('sock_stats', [])
    if not sock_stats:
        print("No 'socket_queue_stats' found in the JSON file.")
        return
    execution_record = data.get('execution_record')

    sock_df = pd.DataFrame(sock_stats).copy()
    sock_df['timestamp'] = pd.to_datetime(sock_df['timestamp'])
    sock_df = sock_df.sort_values('timestamp')

    attack_start = execution_record['timestamps']['attack']
    start_time = pd.to_datetime(attack_start.replace('_', ' '))
    
    sock_df['elapsed'] = (sock_df['timestamp'] - start_time).dt.total_seconds()
    
    max_elapsed = max(sock_df['elapsed'])

    fig, ax1 = plt.subplots(figsize=(12, 6))

    line1 = ax1.plot(sock_df['elapsed'], sock_df['rx_queue_bytes'], 
                     color='tab:orange', label='Current Receive Queue (Bytes)', 
                     linewidth=2, alpha=0.9)
    
    rmem_limit = 212992 

    ax1.set_xlabel('Elapsed Time (seconds)', fontsize=12)
    ax1.set_ylabel('Buffer Usage (Bytes)', color='tab:orange', fontsize=12)
    ax1.tick_params(axis='y', labelcolor='tab:orange')
    
    ax1.set_ylim(0, rmem_limit * 1.2)

    ax2 = ax1.twinx()
    line3 = ax2.step(sock_df['elapsed'], sock_df['drops'], 
                     color='tab:red', label='Cumulative Packet Drops', 
                     linewidth=2, where='post')
    
    ax2.set_ylabel('Total Packets Dropped', color='tab:red', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='tab:red')
    ax2.set_ylim(0, max(sock_df['drops']+10))

    lines = line1 + line3
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', frameon=True, shadow=True)
    ax1.set_xlim(left=0, right=max_elapsed)
    plt.title(f'{attack_function} - Buffer Saturation & Packet Loss', fontsize=14)
    ax1.grid(True, linestyle='--', alpha=0.4)
    
    fig.tight_layout()
    plt.savefig(output_image)
    plt.close()
    print(f"Socket Health chart saved: {output_image}")

if __name__ == "__main__":
    generate_combined_socket_chart('/home/lichon/Desktop/masterthesis/logs/baseline/comparison/log.json', './attacker/plots/pngs/combined_socket_chart.png' )
    generate_combined_system_stress_chart('/home/lichon/Desktop/masterthesis/logs/baseline/comparison/log.json', './attacker/plots/pngs/system_stress.png')
    # generate_gcs_cpu_chart('/home/wiktor/Desktop/Damn-Vulnerable-Drone/logs/udp_limited_flood/2026-04-12_23:02:31/log.json', './attacker/plots/pngs/gcs_cpu_chart.png')
    # generate_combined_network_chart('/home/lichon/Desktop/masterthesis/logs/stx_header_flood/2026-04-19_17:16:01/log.json', "./attacker/plots/pngs/combined_network_chart.png")
    # generate_socket_queue_chart('/home/lichon/Desktop/masterthesis/logs/stx_header_flood/2026-04-19_17:16:01/log.json', './attacker/plots/pngs/socket_buffer_chart.png')
    # generate_combined_cpu_chart('/home/lichon/Desktop/masterthesis/logs/stx_header_flood/2026-04-19_17:16:01/log.json', './attacker/plots/pngs/combined_cpu_chart.png')
    # generate_network_throughput_chart('/home/lichon/Desktop/masterthesis/logs/stx_header_flood/2026-04-19_16:49:23/log.json', './attacker/plots/pngs/network_throughput_chart.png')
    # generate_fw_cpu_chart('/home/lichon/Desktop/masterthesis/logs/random_payload_flood/2026-04-19_16:04:40/log.json', './attacker/plots/pngs/fw_cpu_chart.png')