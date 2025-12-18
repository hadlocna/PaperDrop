import paramiko
import os
import time

# Configuration
RPI_IP = '192.168.86.249'
USERNAME = 'pi'
PASSWORD = 'raspberry'

LOCAL_AGENT_DIR = '/Users/nathanhadlock/CascadeProjects/PaperDrop/agent/src'
REMOTE_DIR = '/opt/paperdrop'

def reset():
    print(f"Connecting to {RPI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(RPI_IP, username=USERNAME, password=PASSWORD)
    
    sftp = ssh.open_sftp()
    
    print("Updating code (config.py)...")
    sftp.put(os.path.join(LOCAL_AGENT_DIR, 'config.py'), '/tmp/config.py')
    ssh.exec_command(f'sudo mv /tmp/config.py {REMOTE_DIR}/config.py')
    ssh.exec_command(f'sudo chown root:root {REMOTE_DIR}/config.py')
    
    print("Stopping services...")
    ssh.exec_command('sudo systemctl stop paperdrop-ws-agent.service')
    ssh.exec_command('sudo systemctl stop paperdrop-wifi.service')
    
    print("Clearing configuration...")
    # Remove agent config (credentials)
    ssh.exec_command('sudo rm -f /etc/paperdrop/device.json')
    ssh.exec_command('sudo rm -f /etc/paperdrop/wifi.json')
    
    # Remove provisioning flag to trigger AP mode
    ssh.exec_command('sudo rm -f /etc/paperdrop/wifi-provisioned')
    
    print("Restarting services...")
    # Restart wifi service to start AP
    ssh.exec_command('sudo systemctl restart paperdrop-wifi.service')
    # Restart agent
    ssh.exec_command('sudo systemctl restart paperdrop-ws-agent.service')
    
    print("Reset complete! Device should now be in AP mode.")
    ssh.close()

if __name__ == '__main__':
    reset()
