import paramiko
import sys

# Configuration
IPS = ['192.168.86.20', '192.168.86.249', 'paperdrop-20ea.lan']
USERNAME = 'pi'
PASSWORD = 'raspberry'

def fetch_logs():
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
        print("--- Agent Logs (paperdrop-ble) ---")
        stdin, stdout, stderr = ssh.exec_command('sudo journalctl -u paperdrop-ble -n 50 --no-pager')
        print(stdout.read().decode())
        
        print("\n--- WiFi Logs (paperdrop-wifi) ---")
        stdin, stdout, stderr = ssh.exec_command('sudo journalctl -u paperdrop-wifi -n 50 --no-pager')
        print(stdout.read().decode())

        print("\n--- WS Agent Logs (paperdrop-ws-agent) ---")
        stdin, stdout, stderr = ssh.exec_command('sudo journalctl -u paperdrop-ws-agent -n 50 --no-pager')
        print(stdout.read().decode())
        
    finally:
        ssh.close()

if __name__ == '__main__':
    fetch_logs()
