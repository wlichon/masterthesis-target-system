import re
import sys
from collections import defaultdict

class MavLossCalculator:
    def __init__(self):
        # Stores the last seen sequence number for each (sysID, compID) tuple
        self.last_seq = {}
        self.mav_count = 0
        self.mav_loss = 0
        
        # Regex to extract: Message Type, srcSystem, srcComponent, and seq
        # Matches: HEARTBEAT ... srcSystem=255 srcComponent=230 seq=0
        self.line_re = re.compile(r':\s+(\w+)\s+.*srcSystem=(\d+)\s+srcComponent=(\d+)\s+seq=(\d+)')

    def process_line(self, line):
        # Skip lines like "lost 461 messages" produced by mavlogdump itself
        if line.startswith("lost "):
            return

        match = self.line_re.search(line)
        if not match:
            return

        msg_type = match.group(1)
        src_system = int(match.group(2))
        src_component = int(match.group(3))
        seq2 = int(match.group(4))
        
        src_tuple = (src_system, src_component)

        if src_component == 190: # ignore messages PARAM_VALUE messages which have the same sequence number, leading to wrong packet loss calculation
            return
        
        if src_system == 2: # ignore heartbeat messages from mavlink flood attacker, as the loss of these message is not relevant to the analysis of the drone's packet loss under attack
            return

        # Ignore BAD_DATA and Radio status messages (3DR Radio) as per your logic
        # '3' and 'D' in ASCII are 51 and 68
        radio_tuple = (51, 68)
        if src_tuple == radio_tuple or msg_type == 'BAD_DATA':
            return

        if src_tuple not in self.last_seq:
            # First time seeing this system/component
            last_seq = -1
        else:
            last_seq = self.last_seq[src_tuple]

        # Calculate expected sequence (wrapping at 256)
        expected_seq = (last_seq + 1) % 256

        if last_seq != -1 and seq2 != expected_seq:
            # Calculate gap, handling the 8-bit wrap-around
            diff = (seq2 - expected_seq) % 256
            self.mav_loss += diff
            print(f"{msg_type} system:{src_system} component:{src_component} seq:{seq2}")
        
        self.last_seq[src_tuple] = seq2
        self.mav_count += 1

    def print_stats(self):
        total = self.mav_count + self.mav_loss
        loss_pct = (self.mav_loss / total * 100) if total > 0 else 0
        print(f"{self.mav_count} packets, {self.mav_loss} lost {loss_pct:.1f}%")

def main(filename):
    calc = MavLossCalculator()
    try:
        with open(filename, 'r') as f:
            for line in f:
                calc.process_line(line)
        calc.print_stats()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mav-packet-loss.py <mavlogdump_output_file>")
    else:
        main(sys.argv[1])