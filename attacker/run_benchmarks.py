import subprocess
import os
import sys
import time

# --- CONFIGURATION ---
# Path to your main pipeline script
# Assuming it is in the same directory as this runner
PIPELINE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_pipeline.py")

# The parameters to test
ATTACK_FUNCTIONS = ["socket_flood", "heartbeat_flood", "ping_flood", "param_flood", "mission_flood", "terrain_flood"]  # None represents the baseline (no attack)
ITERATIONS = 2

def run_benchmarks():
    """
    Orchestrates the execution of the pipeline multiple times
    with different attack parameters.
    """
    
    if not os.path.exists(PIPELINE_SCRIPT):
        print(f"Error: Could not find pipeline script at {PIPELINE_SCRIPT}")
        return

    for attack in ATTACK_FUNCTIONS:
        # Convert None to a string or handle it based on how your pipeline expects args
        attack_arg = "None" if attack is None else attack
        
        print(f"\n{'='*60}")
        print(f"STARTING BATCH: Attack = {attack_arg}")
        print(f"{'='*60}")

        for i in range(1, ITERATIONS + 1):
            print(f"\n[Iteration {i}/{ITERATIONS}] Running {attack_arg}...")
            
            # Construct the command
            # We pass the attack_function as a command line argument
            cmd = [sys.executable, PIPELINE_SCRIPT, "--attack", attack_arg]
            
            try:
                # subprocess.run waits for the script to finish before continuing
                # check=True will stop this runner if the pipeline crashes
                subprocess.run(cmd, check=True)
                print(f"[SUCCESS] Iteration {i} complete.")
                
                # Optional: Brief cooldown between runs to let Docker/Network settle
                time.sleep(2) 
                
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Pipeline failed during {attack_arg} on iteration {i}: {e}")
                # Decide if you want to continue or break the whole test
                continue

    print("\n" + "="*60)
    print("ALL BENCHMARKS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    run_benchmarks()