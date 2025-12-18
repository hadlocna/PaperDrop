import paramiko
import sys

# Configuration from fetch_logs.py
IPS = ['192.168.86.20', '192.168.86.249', 'paperdrop-20ea.lan']
USERNAME = 'pi'
PASSWORD = 'raspberry'

def check_processes():
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
        print("--- Python Processes ---")
        stdin, stdout, stderr = ssh.exec_command('ps aux | grep python')
        print(stdout.read().decode())
        
        print("\n--- USB Devices ---")
        stdin, stdout, stderr = ssh.exec_command('lsusb')
        print(stdout.read().decode())

        print("\n--- Kernel Modules (USB) ---")
        stdin, stdout, stderr = ssh.exec_command('lsmod | grep usb')
        print(stdout.read().decode())
        
    finally:
        ssh.close()

if __name__ == '__main__':
    check_processes()
