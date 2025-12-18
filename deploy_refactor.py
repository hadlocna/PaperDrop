import paramiko
import os
import sys

# Configuration
IPS = ['192.168.86.20', '192.168.86.249', 'paperdrop-20ea.lan']
USERNAME = 'pi'
PASSWORD = 'raspberry'

LOCAL_AGENT_DIR = '/Users/nathanhadlock/CascadeProjects/PaperDrop/agent/src'
REMOTE_SRC_DIR = '/home/paperdrop/agent/src' # Based on my previous successful write
REMOTE_BIN_DIR = '/usr/local/bin'

def deploy():
    connected_ip = None
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    for ip in IPS:
        print(f"Trying to connect to {ip}...")
        try:
            ssh.connect(ip, username=USERNAME, password=PASSWORD, timeout=5)
            connected_ip = ip
            print(f"Connected to {ip}")
            break
        except Exception as e:
            print(f"Failed to connect to {ip}: {e}")
            
    if not connected_ip:
        # Try paperdrop user too just in case
        for ip in IPS:
            print(f"Trying to connect to {ip} as paperdrop...")
            try:
                ssh.connect(ip, username='paperdrop', password='password', timeout=5)
                connected_ip = ip
                print(f"Connected to {ip} as paperdrop")
                break
            except Exception as e:
                print(f"Failed to connect to {ip} as paperdrop: {e}")

    if not connected_ip:
        print("Could not connect to any IP with known credentials.")
        sys.exit(1)
    
    try:
        sftp = ssh.open_sftp()
        
        print("Uploading ble_provisioning.py...")
        sftp.put(os.path.join(LOCAL_AGENT_DIR, 'ble_provisioning.py'), '/tmp/ble_provisioning.py')
        
        print("Uploading paperdrop-wifi.sh...")
        sftp.put(os.path.join(LOCAL_AGENT_DIR, 'paperdrop-wifi.sh'), '/tmp/paperdrop-wifi.sh')
        
        print("Installing files...")
        # We might need sudo for these
        ssh.exec_command('sudo mv /tmp/ble_provisioning.py ' + os.path.join(REMOTE_SRC_DIR, 'ble_provisioning.py'))
        ssh.exec_command('sudo mv /tmp/paperdrop-wifi.sh ' + os.path.join(REMOTE_BIN_DIR, 'paperdrop-wifi.sh'))
        ssh.exec_command('sudo chmod +x ' + os.path.join(REMOTE_BIN_DIR, 'paperdrop-wifi.sh'))
        
        print("Restarting services...")
        ssh.exec_command('sudo systemctl restart paperdrop-ble.service')
        ssh.exec_command('sudo systemctl restart paperdrop-wifi.service')
        
        print("Deployment complete!")
    finally:
        ssh.close()

if __name__ == '__main__':
    deploy()
