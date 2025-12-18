import paramiko
import os
import time

# Configuration
RPI_IP = '192.168.86.249'
USERNAME = 'pi'
PASSWORD = 'raspberry'

LOCAL_AGENT_DIR = '/Users/nathanhadlock/CascadeProjects/PaperDrop/agent/src'
REMOTE_DIR = '/opt/paperdrop'

def deploy_agent():
    print(f"Connecting to {RPI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(RPI_IP, username=USERNAME, password=PASSWORD)
    
    sftp = ssh.open_sftp()
    
    print("Uploading ws_agent.py...")
    sftp.put(os.path.join(LOCAL_AGENT_DIR, 'ws_agent.py'), '/tmp/ws_agent.py')
    
    print("Installing agent...")
    ssh.exec_command(f'sudo mv /tmp/ws_agent.py {REMOTE_DIR}/ws_agent.py')
    ssh.exec_command(f'sudo chown root:root {REMOTE_DIR}/ws_agent.py')
    ssh.exec_command(f'sudo chmod 755 {REMOTE_DIR}/ws_agent.py')
    
    print("Restarting agent service...")
    ssh.exec_command('sudo systemctl restart paperdrop-ws-agent.service')
    
    print("Checking status...")
    time.sleep(2)
    stdin, stdout, stderr = ssh.exec_command('systemctl status paperdrop-ws-agent.service')
    print(stdout.read().decode())
    
    print("Agent update deployed!")
    ssh.close()

if __name__ == '__main__':
    deploy_agent()
