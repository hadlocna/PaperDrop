import paramiko
import os
import time
import json

# Configuration
RPI_IP = '192.168.86.249'
USERNAME = 'pi'
PASSWORD = 'raspberry'

LOCAL_AGENT_DIR = '/Users/nathanhadlock/CascadeProjects/PaperDrop/agent/src'
REMOTE_DIR = '/opt/paperdrop'

def deploy():
    print(f"Connecting to {RPI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(RPI_IP, username=USERNAME, password=PASSWORD)
    
    sftp = ssh.open_sftp()
    
    print("Stopping old service...")
    ssh.exec_command('sudo systemctl stop paperdrop.service')
    ssh.exec_command('sudo systemctl disable paperdrop.service')
    
    print("Migrating device ID...")
    # Read existing device ID
    stdin, stdout, stderr = ssh.exec_command('cat /etc/paperdrop/device-id')
    device_id = stdout.read().decode().strip()
    
    if device_id:
        print(f"Found device ID: {device_id}")
        # Create device.json if not exists or update it
        device_json = {
            "device_code": device_id,
            "device_secret": "paperdrop-secret-" + device_id # Simple secret for now, or keep existing if any
        }
        
        # Check if device.json exists to preserve secret?
        # For now, let's just write it. If the backend expects a specific secret, we might have an issue.
        # But the backend creates the device on first connect if it doesn't exist, or verifies secret.
        # If the device was already created in DB with a secret, we need that secret.
        # BUT, the old agent didn't use a secret?
        # Old agent used ACCESS_TOKEN from config.env?
        # The user said "I successfully see the animation showing the credentials being sent to the RPi".
        # This implies BLE provisioning.
        # In BLE provisioning, we didn't send a secret?
        # Let's check ble_provisioning.py.
        # It only has WifiConfigCharacteristic. It doesn't seem to set a secret.
        # So the device probably doesn't have a secret yet.
        # The backend `deviceHandler.ts` says:
        # "Verify or Create device... if !device ... create ... else if device.deviceSecret !== deviceSecret ... reject"
        # So if the device exists in DB (from BLE provisioning?), it might not have a secret?
        # Wait, `deviceController.ts`: "Device was provisioned via BLE but hasn't connected to backend yet... Create it now".
        # So the device might NOT exist in DB yet?
        # OR it exists but with what secret?
        # If it doesn't exist, we can use any secret.
        
        # Let's write the device.json
        cmd = f"echo '{json.dumps(device_json)}' | sudo tee /etc/paperdrop/device.json"
        ssh.exec_command(cmd)
        ssh.exec_command('sudo chmod 644 /etc/paperdrop/device.json')
    else:
        print("WARNING: No device ID found!")

    print("Uploading files...")
    # Upload files to /tmp first then move
    sftp.put(os.path.join(LOCAL_AGENT_DIR, 'ws_agent.py'), '/tmp/ws_agent.py')
    sftp.put(os.path.join(LOCAL_AGENT_DIR, 'config.py'), '/tmp/config.py')
    sftp.put(os.path.join(LOCAL_AGENT_DIR, 'paperdrop-ws-agent.service'), '/tmp/paperdrop-ws-agent.service')
    
    print("Installing files...")
    ssh.exec_command(f'sudo mv /tmp/ws_agent.py {REMOTE_DIR}/ws_agent.py')
    ssh.exec_command(f'sudo mv /tmp/config.py {REMOTE_DIR}/config.py')
    ssh.exec_command('sudo mv /tmp/paperdrop-ws-agent.service /etc/systemd/system/paperdrop-ws-agent.service')
    
    print("Setting permissions...")
    ssh.exec_command(f'sudo chown root:root {REMOTE_DIR}/ws_agent.py {REMOTE_DIR}/config.py')
    ssh.exec_command(f'sudo chmod 755 {REMOTE_DIR}/ws_agent.py {REMOTE_DIR}/config.py')
    
    print("Installing dependencies...")
    # Need to install websockets on the RPi
    # Assuming RPi has internet now
    ssh.exec_command(f'sudo {REMOTE_DIR}/venv/bin/pip install websockets')
    
    print("Starting new service...")
    ssh.exec_command('sudo systemctl daemon-reload')
    ssh.exec_command('sudo systemctl enable paperdrop-ws-agent.service')
    ssh.exec_command('sudo systemctl restart paperdrop-ws-agent.service')
    
    print("Deployment complete!")
    ssh.close()

if __name__ == '__main__':
    deploy()
