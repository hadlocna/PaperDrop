import socket
import json

def listen():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('', 50000))
    print("Listening for PaperDrop devices on port 50000...")
    while True:
        data, addr = s.recvfrom(1024)
        try:
            msg = json.loads(data)
            print(f"Found device: {msg}")
        except:
            print(f"Received raw data from {addr}: {data}")

if __name__ == "__main__":
    listen()
