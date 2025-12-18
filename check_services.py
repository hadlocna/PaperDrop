import paramiko
import sys

# Configuration
IPS = ['192.168.86.20', '192.168.86.249', 'paperdrop-20ea.lan']
USERNAME = 'pi'
PASSWORD = 'raspberry'

def check_services():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    connected_ip = None
    for ip in IPS:
        try:
            ssh.connect(ip, username=USERNAME, password=PASSWORD, timeout=5)
            connected_ip = ip
            break
        except Exception:
            continue
            
    if not connected_ip:
        print("Could not connect.")
        sys.exit(1)
        
    try:
        for service in ['paperdrop-ble.service', 'paperdrop-wifi.service', 'paperdrop-ws-agent.service']:
            print(f"--- {service} ---")
            stdin, stdout, stderr = ssh.exec_command(f'cat /etc/systemd/system/{service}')
            print(stdout.read().decode())
            print("\n")
    finally:
        ssh.close()

if __name__ == '__main__':
    check_services()
