import sys

from pymavlink import mavutil
import time
from signing import setup_packet_signing

log_path = '/opt/gcs/stages/af_debug.log'

# Use os.open to ensure we have raw access, then wrap it
sys.stdout = open(log_path, 'a', encoding='utf-8')
sys.stderr = sys.stdout

connection_string = "udp:0.0.0.0:14550"  # Replace with your connection string

def read_waypoints(filename):
    waypoints = []
    with open(filename, 'r') as file:
        for line in file:
            lat, lon, alt = map(float, line.strip().split(','))
            waypoints.append((lat, lon, alt))
    return waypoints

def connect_to_drone(connection_string, timeout=30, retries=5):
    for attempt in range(retries):
        try:
            print(f"Attempt {attempt+1} of {retries} to connect to drone")
            master = mavutil.mavlink_connection(connection_string, source_system=255)
            start_time = time.time()

            while True:
                if time.time() - start_time > timeout:
                    raise TimeoutError("Timed out waiting for heartbeat")

                msg = master.recv_match(type='HEARTBEAT', blocking=True, timeout=1)
                if msg:
                    print("Connected to drone")
                    return master
                else:
                    print("Waiting for heartbeat...")

        except TimeoutError as e:
            print(str(e))
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
        
        time.sleep(5)  # Wait before retrying

    raise ConnectionError("Failed to connect to the drone after multiple attempts")

# Read waypoints from file
waypoints = read_waypoints('/opt/gcs/missions/waypoints_circle.txt')

master = connect_to_drone(connection_string)
setup_packet_signing(master)
# Start mission upload
master.waypoint_clear_all_send()
ack = master.recv_match(type='MISSION_ACK', blocking=True, timeout=5)
if ack:
    print(f"Drone cleared mission. Result: {ack.type}")
else:
    print("FAILED: Drone did not acknowledge mission clear. Checking for heartbeat...")
    hb = master.recv_match(type='HEARTBEAT', blocking=True, timeout=2)
    print("Heartbeat present" if hb else "Heartbeat LOST")
    sys.exit(1)


master.mav.mission_count_send(master.target_system, master.target_component, len(waypoints))

# Upload waypoints
for i, (lat, lon, alt) in enumerate(waypoints):
    msg = master.recv_match(type=['MISSION_REQUEST', 'MISSION_ACK'], blocking=True, timeout=5)
    if msg and msg.get_type() == 'MISSION_ACK':
        print(f"Mission rejected by drone. ACK type: {msg.type}")
    if msg is not None and msg.seq == i:
        master.mav.mission_item_int_send(
            master.target_system,
            master.target_component,
            i,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            0, 0, 0, 0, 0, 0,
            int(lat * 1e7), int(lon * 1e7), alt
        )

# Check for mission acceptance
ack_msg = master.recv_match(type=['MISSION_ACK'], blocking=True)
if ack_msg is not None and ack_msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
    print("Mission uploaded successfully")
    # Proceed to set AUTO mode
else:
    print("Mission upload failed")

# Switch to AUTO mode
master.set_mode_auto()
print("AUTO mode set, mission started")

