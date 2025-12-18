import paramiko
import sys

# Configuration from fetch_logs.py
IPS = ['192.168.86.20', '192.168.86.249', 'paperdrop-20ea.lan']
USERNAME = 'pi'
PASSWORD = 'raspberry'

def run_command(cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    connected_ip = None
    for ip in IPS:
        try:
            ssh.connect(ip, username=USERNAME, password=PASSWORD, timeout=5)
            connected_ip = ip
            print(f"Connected to {ip}")
            break
        except Exception:
            continue
            
    if not connected_ip:
        print("Could not connect to any IP.")
        sys.exit(1)
        
    try:
        print(f"Running: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print("STDOUT:")
        print(stdout.read().decode())
        print("STDERR:")
        print(stderr.read().decode())
        
    finally:
        ssh.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python run_on_device.py <command>")
        sys.exit(1)
    run_command(sys.argv[1])
