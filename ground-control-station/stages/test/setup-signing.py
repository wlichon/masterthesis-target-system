import time
from pymavlink import mavutil
import sys


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

def setup_signing_and_key(master, passphrase):
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

    # 4. Enable signing locally so pymavlink starts signing the NEXT messages
    # master.setup_signing(key, sign_outgoing=True, link_id=0, initial_timestamp=initial_timestamp)
    
    # Give the SITL a moment to process and save to eeprom.bin
    time.sleep(1)


connection_string = "udp:0.0.0.0:14550"
master = mavutil.mavlink_connection(connection_string)

# Must wait for first heartbeat to know target_system/target_component
master.wait_heartbeat()
print(f"Connected to System {master.target_system}")

setup_signing_and_key(master, "password")