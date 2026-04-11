import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
payload = b"A"
sock.sendto(payload, ("192.168.13.14", 14550))