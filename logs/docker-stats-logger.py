import os
import subprocess
import json
import time
import signal
import threading

# --- CONFIGURATION ---
CONTAINERS = [
    "ground-control-station-lite",
    "companion-computer-lite",
    "flight-controller-lite"
]

class DockerMonitor:
    def __init__(self):
        self.stats_history = []
        self.keep_running = True
        self.thread = None

    def _monitor_loop(self):
        """Internal loop to grab snapshots every second."""
        format_str = '{"name":"{{.Name}}","cpu":"{{.CPUPerc}}","m_perc":"{{.MemPerc}}","net":"{{.NetIO}}"}'
        cmd = ["docker", "stats"] + CONTAINERS + ["--format", format_str, "--no-stream"]
        
        while self.keep_running:
            try:
                result = subprocess.check_output(cmd, text=True)
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                
                for line in result.strip().split('\n'):
                    if not line: continue
                    raw = json.loads(line)
                    self.stats_history.append({
                        "timestamp": timestamp,
                        "container": raw["name"],
                        "cpu_percent": raw["cpu"],
                        "mem_percent": raw["m_perc"],
                        "net_io": raw["net"]
                    })
                time.sleep(1)
            except Exception as e:
                print(f"Monitor Error: {e}")
                break

    def start(self):
        """Starts the monitor in a background thread."""
        self.keep_running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.start()

    def stop(self):
        """Stops the monitor and returns the collected data."""
        self.keep_running = False
        if self.thread:
            self.thread.join()
        return self.stats_history