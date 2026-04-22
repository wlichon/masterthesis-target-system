import subprocess
import os
import sys
import time


PIPELINE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_pipeline.py")

# The parameters to test
ATTACK_FUNCTIONS = [None]  # None represents the baseline (no attack)

# ATTACK_FUNCTIONS = ["empty_payload_flood", "random_payload_flood", "stx_header_flood"]  # None represents the baseline (no attack)
ITERATIONS = 5

def run_benchmarks():
    """
    Orchestrates the execution of the pipeline multiple times
    with different attack parameters.
    """
    
    if not os.path.exists(PIPELINE_SCRIPT):
        print(f"Error: Could not find pipeline script at {PIPELINE_SCRIPT}")
        return

    for attack in ATTACK_FUNCTIONS:
        attack_arg = "None" if attack is None else attack
        attack_time = "60"
        idle_time = "60"
        
        print(f"\n{'='*60}")
        print(f"STARTING BATCH: Attack = {attack_arg}")
        print(f"{'='*60}")

        for i in range(1, ITERATIONS + 1):
            print(f"\n[Iteration {i}/{ITERATIONS}] Running {attack_arg}...")
            
          
            cmd = [sys.executable, PIPELINE_SCRIPT, "--attack", attack_arg, "--idle", idle_time, "--attack-time", attack_time]
            
            try:
                subprocess.run(cmd, check=True)
                print(f"[SUCCESS] Iteration {i} complete.")
                time.sleep(2) 
                
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Pipeline failed during {attack_arg} on iteration {i}: {e}")
                continue

    print("\n" + "="*60)
    print("ALL BENCHMARKS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    run_benchmarks()