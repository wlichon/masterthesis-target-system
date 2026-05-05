import json
import pandas as pd
import matplotlib.pyplot as plt

def generate_latency_trend_chart(json_filepath, output_image):
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON: {e}")
        return

    stats = data.get('latency_stats', data.get('latency', []))
    if not stats:
        print("No latency data found in log.json.")
        return

    df = pd.DataFrame(stats)
    
    df['sent_at'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('sent_at')

    plt.figure(figsize=(12, 6))
    
    plt.plot(
        df['sent_at'], 
        df['latency'], 
        marker='o', 
        color='tab:red', 
        linestyle='-', 
        markersize=4, 
        alpha=0.8,
        label='Round Trip Time (ms)'
    )
    
    plt.title('MAVLink TIMESYNC Latency Over Time', fontsize=14)
    plt.xlabel('Time (UTC)', fontsize=12)
    plt.ylabel('Latency (ms)', fontsize=12)
    
    plt.ylim(0, 100)
    
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig(output_image)
    print(f"Chart successfully saved as {output_image}")

if __name__ == "__main__":
    generate_latency_trend_chart('/home/wiktor/Desktop/Damn-Vulnerable-Drone/logs/mavlink_flood/20260406_003153/log.json', './plots/pngs/latency_stats_chart.png')