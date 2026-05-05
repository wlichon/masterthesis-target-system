import os
import glob
import json
import numpy as np
import matplotlib.pyplot as plt

def get_loss_data(pattern):
    directories = glob.glob(pattern)
    losses = []
    for d in directories:
        if not os.path.isdir(d):
            continue
        json_path = os.path.join(d, 'log.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    val = data.get('mavloss', {}).get('loss_percentage')
                    if val is not None:
                        losses.append(float(val))
            except Exception as e:
                print(f"Error reading {json_path}: {e}")
    return losses

def generate_loss_comparison_chart(pattern_1, label_1, pattern_2, label_2, output_file='loss_comparison.png'):
    data_1 = get_loss_data(pattern_1)
    data_2 = get_loss_data(pattern_2)

    if not data_1 and not data_2:
        print("Error: No valid data found for the provided patterns.")
        return

    stats = [
        {'label': label_1, 'mean': np.mean(data_1) if data_1 else 0},
        {'label': label_2, 'mean': np.mean(data_2) if data_2 else 0}
    ]
    stats.sort(key=lambda x: x['mean'], reverse=True)

    labels = [s['label'] for s in stats]
    means = [s['mean'] for s in stats]
    plt.figure(figsize=(8, 6))
    
    bars = plt.bar(labels, means, color=['#d62728', '#1f77b4'], alpha=0.85, edgecolor='black')
    
    plt.title('Comparison of MAVLink Packet Loss Rates', fontsize=14, fontweight='bold')
    plt.ylabel('Mean Loss Percentage (%)', fontweight='bold')
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    
    plt.ylim(0, max(means) * 1.15 if max(means) > 0 else 10)
    
    for i, v in enumerate(means):
        plt.text(i, v + 0.1, f"{v:.2f}%", ha='center', fontsize=11, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_file)
    print(f"Successfully generated comparison chart (no sigma bars): {output_file}")

generate_loss_comparison_chart('logs/stx_header_flood/unfiltered*', 'No Filter', 'logs/stx_header_flood/filtered*', 'XDP Filter')