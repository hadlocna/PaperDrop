import paramiko
import sys

# Configuration
IPS = ['192.168.86.20', '192.168.86.249', 'paperdrop-20ea.lan']
USERNAME = 'pi'
PASSWORD = 'raspberry'

def check_network():
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
        print("--- Network Interfaces ---")
        stdin, stdout, stderr = ssh.exec_command('ip addr')
        print(stdout.read().decode())
        
        print("\n--- Hostname ---")
        stdin, stdout, stderr = ssh.exec_command('hostname')
        print(stdout.read().decode())
        
        print("\n--- Avahi Services ---")
        stdin, stdout, stderr = ssh.exec_command('ls /etc/avahi/services/')
        print(stdout.read().decode())
        
        print("\n--- Running Processes (python) ---")
        stdin, stdout, stderr = ssh.exec_command('ps aux | grep python')
        print(stdout.read().decode())
    finally:
        ssh.close()

if __name__ == '__main__':
    check_network()
