#!/usr/bin/env python3
"""
PaperDrop Device Agent
Connects to fleet management server after WiFi provisioning
All dependencies are pre-installed in /opt/paperdrop/venv
"""

import os
import sys
import json
import time
import socket
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# Third-party imports (pre-installed in venv)
import paho.mqtt.client as mqtt
import psutil
from dotenv import load_dotenv

# Load configuration
CONFIG_FILE = '/etc/paperdrop/config.env'
if os.path.exists(CONFIG_FILE):
    load_dotenv(CONFIG_FILE)

# Configuration with defaults
THINGSBOARD_HOST = os.getenv('THINGSBOARD_HOST', 'demo.thingsboard.io')
THINGSBOARD_PORT = int(os.getenv('THINGSBOARD_PORT', '1883'))
ACCESS_TOKEN = os.getenv('THINGSBOARD_ACCESS_TOKEN', '')
TELEMETRY_INTERVAL = int(os.getenv('TELEMETRY_INTERVAL', '60'))
DEVICE_TYPE = os.getenv('DEVICE_TYPE', 'paperdrop')

# MQTT Topics
TELEMETRY_TOPIC = 'v1/devices/me/telemetry'
ATTRIBUTES_TOPIC = 'v1/devices/me/attributes'
RPC_REQUEST_TOPIC = 'v1/devices/me/rpc/request/+'
RPC_RESPONSE_TOPIC = 'v1/devices/me/rpc/response/{}'

# Logging setup
LOG_DIR = '/var/log/paperdrop'
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{LOG_DIR}/agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('PaperDropAgent')


def get_device_id():
    """Read device ID from identity file"""
    try:
        with open('/etc/paperdrop/device-id', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return socket.gethostname()


def get_cpu_temperature():
    """Get CPU temperature in Celsius"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            return round(float(f.read().strip()) / 1000.0, 1)
    except Exception:
        return None


def get_wifi_info():
    """Get WiFi connection info"""
    info = {'ssid': None, 'signal_dbm': None, 'signal_percent': None}
    try:
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL', 'device', 'wifi', 'list'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split('\n'):
            parts = line.split(':')
            if len(parts) >= 3 and parts[0] == 'yes':
                info['ssid'] = parts[1]
                info['signal_percent'] = int(parts[2]) if parts[2].isdigit() else None
                break
    except Exception as e:
        logger.debug(f"Could not get WiFi info: {e}")
    return info


def get_ip_address():
    """Get primary IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def collect_telemetry():
    """Collect all telemetry data"""
    wifi = get_wifi_info()
    
    return {
        'ts': int(time.time() * 1000),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'cpu_temp': get_cpu_temperature(),
        'uptime_seconds': int(time.time() - psutil.boot_time()),
        'wifi_ssid': wifi['ssid'],
        'wifi_signal': wifi['signal_percent'],
        'ip_address': get_ip_address(),
    }


def collect_attributes():
    """Collect device attributes (sent once on connect)"""
    return {
        'device_id': get_device_id(),
        'device_type': DEVICE_TYPE,
        'hostname': socket.gethostname(),
        'os_version': get_os_version(),
        'agent_version': '1.0.0',
        'mac_address': get_mac_address(),
    }


def get_os_version():
    """Get OS version"""
    try:
        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('PRETTY_NAME='):
                    return line.split('=')[1].strip().strip('"')
    except Exception:
        pass
    return 'unknown'


def get_mac_address():
    """Get WiFi MAC address"""
    try:
        with open('/sys/class/net/wlan0/address', 'r') as f:
            return f.read().strip()
    except Exception:
        return 'unknown'


class DeviceAgent:
    def __init__(self):
        self.client = mqtt.Client()
        self.connected = False
        self.last_telemetry = 0
        
        if ACCESS_TOKEN:
            self.client.username_pw_set(ACCESS_TOKEN)
        
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to ThingsBoard at {THINGSBOARD_HOST}")
            self.connected = True
            
            # Subscribe to RPC
            client.subscribe(RPC_REQUEST_TOPIC)
            
            # Publish attributes
            attrs = collect_attributes()
            client.publish(ATTRIBUTES_TOPIC, json.dumps(attrs))
            logger.info(f"Published attributes: {attrs}")
        else:
            logger.error(f"Connection failed: rc={rc}")
            self.connected = False
    
    def on_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected: rc={rc}")
        self.connected = False
    
    def on_message(self, client, userdata, msg):
        """Handle RPC requests"""
        try:
            request_id = msg.topic.split('/')[-1]
            payload = json.loads(msg.payload)
            method = payload.get('method', '')
            params = payload.get('params', {})
            
            logger.info(f"RPC request: {method}")
            
            response = self.handle_rpc(method, params)
            
            client.publish(
                RPC_RESPONSE_TOPIC.format(request_id),
                json.dumps(response)
            )
        except Exception as e:
            logger.error(f"RPC error: {e}")
    
    def handle_rpc(self, method, params):
        """Process RPC commands"""
        if method == 'reboot':
            subprocess.Popen(['sudo', 'reboot'])
            return {'success': True, 'message': 'Rebooting...'}
        
        elif method == 'getStatus':
            return {'success': True, 'telemetry': collect_telemetry()}
        
        elif method == 'resetWifi':
            # Clear WiFi and return to AP mode
            subprocess.Popen(['/usr/local/bin/paperdrop-reset-wifi.sh'])
            return {'success': True, 'message': 'WiFi reset initiated'}
        
        elif method == 'runCommand':
            cmd = params.get('command', '')
            if cmd:
                try:
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True,
                        text=True, timeout=30
                    )
                    return {
                        'success': True,
                        'stdout': result.stdout[-1000:],  # Limit output
                        'stderr': result.stderr[-500:],
                        'returncode': result.returncode
                    }
                except subprocess.TimeoutExpired:
                    return {'success': False, 'error': 'Timeout'}
            return {'success': False, 'error': 'No command'}
        
        return {'success': False, 'error': f'Unknown method: {method}'}
    
    def wait_for_network(self, timeout=300):
        """Wait for network connectivity before connecting to server"""
        logger.info("Waiting for network connectivity...")
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=5)
                logger.info("Network is available")
                return True
            except OSError:
                time.sleep(5)
        
        logger.error("Network timeout")
        return False
    
    def run(self):
        """Main agent loop"""
        # Wait for network (wifi-connect should have set it up)
        if not self.wait_for_network():
            logger.error("No network. Agent cannot start.")
            sys.exit(1)
        
        # Connect to ThingsBoard
        while True:
            try:
                logger.info(f"Connecting to {THINGSBOARD_HOST}:{THINGSBOARD_PORT}")
                self.client.connect(THINGSBOARD_HOST, THINGSBOARD_PORT, 60)
                break
            except Exception as e:
                logger.error(f"Connection error: {e}. Retrying in 10s...")
                time.sleep(10)
        
        self.client.loop_start()
        
        try:
            while True:
                now = time.time()
                
                # Publish telemetry
                if self.connected and now - self.last_telemetry >= TELEMETRY_INTERVAL:
                    telemetry = collect_telemetry()
                    self.client.publish(TELEMETRY_TOPIC, json.dumps(telemetry))
                    logger.debug(f"Telemetry: {telemetry}")
                    self.last_telemetry = now
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == '__main__':
    if not ACCESS_TOKEN:
        logger.warning("No ACCESS_TOKEN configured. Running in demo mode.")
    
    agent = DeviceAgent()
    agent.run()
