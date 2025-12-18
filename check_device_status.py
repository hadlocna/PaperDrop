import paramiko
import sys

IP = '192.168.1.126'
USER = 'pi'
PWD = 'raspberry'

def check_status():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(IP, username=USER, password=PWD, timeout=5)
        print(f"Connected to {IP}")
        
        services = [
            'paperdrop-ble.service',
            'paperdrop-ws-agent.service',
            'paperdrop-wifi.service'
        ]
        
        print("\n--- Service Status ---")
        for service in services:
            stdin, stdout, stderr = ssh.exec_command(f'systemctl is-active {service}')
            status = stdout.read().decode().strip()
            print(f"{service}: {status}")
            
        print("\n--- Recent Logs (WS Agent) ---")
        stdin, stdout, stderr = ssh.exec_command('sudo journalctl -u paperdrop-ws-agent -n 20 --no-pager')
        print(stdout.read().decode())
        
        print("\n--- Recent Logs (BLE) ---")
        stdin, stdout, stderr = ssh.exec_command('sudo journalctl -u paperdrop-ble -n 20 --no-pager')
        print(stdout.read().decode())

        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_status()
