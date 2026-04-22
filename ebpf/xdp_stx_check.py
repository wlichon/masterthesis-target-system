from bcc import BPF
import time

device = "enp2s0" # ethernet interface

ebpf_code = """
#include <uapi/linux/bpf.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/udp.h>

int drop_non_mavlink(struct xdp_md *ctx) {
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
    if ((void*)(payload + 1) > data_end) return XDP_PASS;

    if (payload[0] != 0xFD) {
        return XDP_DROP;
    }

    return XDP_PASS;
}
"""

print(f"Loading XDP program on {device}... Press Ctrl+C to stop.")

try:
    b = BPF(text=ebpf_code)
    fn = b.load_func("drop_non_mavlink", BPF.XDP)
    
    # Attach to the interface
    # BPF.XDP_FLAGS_SKB_MODE is used for generic/veth testing
    # Use 0 for "Native" mode if driver allows
    b.attach_xdp(device, fn, flags=BPF.XDP_FLAGS_SKB_MODE)

    print("Success! Monitoring MAVLink traffic...")
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nRemoving XDP program...")
finally:
    if 'b' in locals():
        b.remove_xdp(device, flags=0)