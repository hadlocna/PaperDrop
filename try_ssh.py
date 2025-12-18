import paramiko
import sys

IPS = ['192.168.1.126', '192.168.1.127', 'paperdrop-20ea.local']
CREDS = [
    ('pi', 'raspberry'),
    ('paperdrop', 'password'),
    ('pi', 'paperdrop')
]

def try_connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    for ip in IPS:
        for user, pwd in CREDS:
            print(f"Trying {user}@{ip}...")
            try:
                ssh.connect(ip, username=user, password=pwd, timeout=5)
                print(f"SUCCESS: Connected to {ip} as {user}")
                
                # Run a simple command to verify
                stdin, stdout, stderr = ssh.exec_command('hostname -I')
                ips = stdout.read().decode().strip()
                print(f"Device IPs: {ips}")
                
                ssh.close()
                return ip, user, pwd
            except Exception as e:
                print(f"Failed {user}@{ip}: {e}")
    
    return None

if __name__ == "__main__":
    result = try_connect()
    if result:
        print(f"\n[!] SUCCESSFULLY CONNECTED TO DEVICE: {result}")
    else:
        print("\n[X] Could not connect to any IP with known credentials.")
