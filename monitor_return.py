import os
import time
import subprocess

def check_device():
    targets = [
        "paperdrop-20ea.local",
        "raspberrypi.local",
        "192.168.1.126",
        "192.168.1.103"
    ]
    
    print("Monitoring for device return (Ctrl+C to stop)...")
    while True:
        for target in targets:
            try:
                # Use -t 1 for 1 second timeout
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1000", target],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if result.returncode == 0:
                    print(f"\n[!] DEVICE DETECTED: {target} is UP at {time.strftime('%H:%M:%S')}")
                    return target
            except Exception:
                pass
        print(".", end="", flush=True)
        time.sleep(2)

if __name__ == "__main__":
    check_device()
