import paramiko
import os
import time

# Configuration
RPI_IP = '192.168.86.249'
USERNAME = 'pi'
PASSWORD = 'raspberry'

LOCAL_AGENT_DIR = '/Users/nathanhadlock/CascadeProjects/PaperDrop/agent/src'
REMOTE_DIR = '/usr/local/bin'

def deploy_wifi():
    print(f"Connecting to {RPI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(RPI_IP, username=USERNAME, password=PASSWORD)
    
    sftp = ssh.open_sftp()
    
    print("Uploading paperdrop-wifi.sh...")
    sftp.put(os.path.join(LOCAL_AGENT_DIR, 'paperdrop-wifi.sh'), '/tmp/paperdrop-wifi.sh')
    
    print("Installing script...")
    ssh.exec_command(f'sudo mv /tmp/paperdrop-wifi.sh {REMOTE_DIR}/paperdrop-wifi.sh')
    ssh.exec_command(f'sudo chmod +x {REMOTE_DIR}/paperdrop-wifi.sh')
    
    print("Restarting WiFi service...")
    ssh.exec_command('sudo systemctl restart paperdrop-wifi.service')
    
    print("Checking status...")
    time.sleep(2)
    stdin, stdout, stderr = ssh.exec_command('ps aux | grep wifi-connect')
    print("wifi-connect processes:")
    print(stdout.read().decode())
    
    print("WiFi fix deployed!")
    ssh.close()

if __name__ == '__main__':
    deploy_wifi()
