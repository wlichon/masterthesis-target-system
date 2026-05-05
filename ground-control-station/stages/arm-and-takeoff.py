from pymavlink import mavutil
import time
import sys
from signing import upload_signing_key_to_drone, setup_packet_signing

log_path = '/opt/gcs/stages/aat_debug.log'

sys.stdout = open(log_path, 'a', encoding='utf-8')
sys.stderr = sys.stdout

def wait_for_mode(master, mode):
    while True:
        msgs = master.recv_match(blocking=True)
        if msgs is not None and msgs.get_type() == 'HEARTBEAT' and msgs.custom_mode == mode:
            break
        time.sleep(0.1)

def is_armed(heartbeat):
    return (heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0

def wait_for_gps_fix(master, timeout=60):
    start_time = time.time()
    print("Waiting for GPS fix...")
    while time.time() - start_time < timeout:
        msg = master.recv_match(type='GPS_RAW_INT', blocking=True, timeout=1)
        if msg is not None and msg.fix_type >= 3:
            print("GPS fix acquired")
            return True
        time.sleep(0.5)
    return True

def wait_for_ekf_status(master):
    print("Waiting for EKF status to be OK...")
    while True:
        msg = master.recv_match(type='EKF_STATUS_REPORT', blocking=True)
        if msg is not None and msg.flags & mavutil.mavlink.EKF_POS_HORIZ_ABS:
            print("EKF status OK")
            break
        time.sleep(0.5)

# Create connection (UDP for SITL/Docker)
connection_string = "udp:0.0.0.0:14550"
master = mavutil.mavlink_connection(connection_string, source_system=255)

# Must wait for first heartbeat to know target_system/target_component
master.wait_heartbeat()
print(f"Connected to System {master.target_system}")

# UPLOAD KEY AND ENABLE SIGNING
upload_signing_key_to_drone(master, "password")
setup_packet_signing(master)

master.waypoint_clear_all_send()
print("Clearing waypoints...")

if not wait_for_gps_fix(master):
    print("Failed to acquire GPS fix...")
    exit(1)

# Set Mode (Signed)
master.mav.set_mode_send(
    master.target_system, 
    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 
    mavutil.mavlink.COPTER_MODE_GUIDED
)
wait_for_mode(master, mavutil.mavlink.COPTER_MODE_GUIDED)
print("GUIDED mode set")

wait_for_ekf_status(master)

def print_statustext(master):
    msg = master.recv_match(type='STATUSTEXT', blocking=False)
    if msg:
        print(f"Autopilot Status: {msg.text}")



master.arducopter_arm()
print("Arming motors...")

# Immediately check if the drone REJECTED the command

ack = master.recv_match(type='COMMAND_ACK', blocking=True, timeout=2)
if ack:
    if ack.result != mavutil.mavlink.MAV_RESULT_ACCEPTED:
        print(f"Arming command REJECTED. Result code: {ack.result}")
        # you'd want to see the STATUSTEXT for debugging
        msg = master.recv_match(type='STATUSTEXT', blocking=True, timeout=1)
        if msg:
            print(f"Reason: {msg.text}")


# If it wasn't rejected, THEN wait for the state to change to ARMED
arming_timeout = 5
start_time = time.time()
while time.time() - start_time < arming_timeout:
    heartbeat = master.recv_match(type='HEARTBEAT', blocking=True, timeout=1)
    
    # Check for any background status messages
    print_statustext(master) 
    
    if heartbeat and is_armed(heartbeat):
        print("Drone is armed")
        break
    else:
        print("Failed to arm motors... retrying")

if is_armed(heartbeat):
    # Takeoff command
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0, 2.75)
    print("Takeoff command sent")
    time.sleep(1)
    print("Takeoff complete")
else:
    print("Takeoff failed")