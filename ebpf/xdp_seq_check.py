from bcc import BPF
import time

device = "enp2s0"

ebpf_code = """
#include <uapi/linux/bpf.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/udp.h>

// Map to store the last seen sequence number
BPF_HASH(last_seq_map, u32, u8);

int drop_duplicate_mavlink(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void*)(eth + 1) > data_end) return XDP_PASS;
    if (eth->h_proto != __constant_htons(ETH_P_IP)) return XDP_PASS;

    struct iphdr *ip = data + sizeof(*eth);
    if ((void*)(ip + 1) > data_end) return XDP_PASS;
    if (ip->protocol != 17) return XDP_PASS;

    struct udphdr *udp = (void*)ip + sizeof(*ip);
    if ((void*)(udp + 1) > data_end) return XDP_PASS;
    if (udp->dest != __constant_htons(14550)) return XDP_PASS;

    unsigned char *payload = (unsigned char *)(udp + 1);
    
    // MAVLink 2 Frame: [STX][LEN][SEQ][SYSID][COMPID][MSGID]...
    // Ensure SEQ byte exists (index 2)
    if ((void*)(payload + 3) > data_end) return XDP_PASS;


    // 2. Extract SEQ byte
    u8 current_seq = payload[2];
    u32 key = 0;
    u8 *last_seq = last_seq_map.lookup(&key);

    if (last_seq) {
        // 3. Compare with previous. If identical, it's a duplicate or retransmission
        if (current_seq == *last_seq) {
            return XDP_DROP;
        }
    }

    // 4. Update map with new SEQ Byte
    last_seq_map.update(&key, &current_seq);

    return XDP_PASS;
}
"""

print(f"Loading XDP sequence filter on {device}...")

try:
    b = BPF(text=ebpf_code)
    fn = b.load_func("drop_duplicate_mavlink", BPF.XDP)
    b.attach_xdp(device, fn, flags=BPF.XDP_FLAGS_SKB_MODE)

    print("Filtering duplicate MAVLink sequence numbers. Press Ctrl+C to stop.")
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nDetaching...")
finally:
    if 'b' in locals():
        b.remove_xdp(device, flags=0)