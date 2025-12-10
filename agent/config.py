import json
import os
import uuid

CONFIG_FILE = 'config.json'

class Config:
    def __init__(self):
        self.device_id = None
        self.device_code = None
        self.device_secret = None
        self.wifi_configured = False
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.device_id = data.get('device_id')
                    self.device_code = data.get('device_code')
                    self.device_secret = data.get('device_secret')
                    self.wifi_configured = data.get('wifi_configured', False)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        data = {
            'device_id': self.device_id,
            'device_code': self.device_code,
            'device_secret': self.device_secret,
            'wifi_configured': self.wifi_configured
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)

    def initialize(self):
        if not self.device_code:
            # Generate a new identity if none exists
            # In a real production unit, this might be pre-flashed or generated once.
            # Using 6 char code for user friendliness
            self.device_code = str(uuid.uuid4()).split('-')[0].upper()
            self.device_secret = str(uuid.uuid4())
            self.save()
            print(f"Initialized Device. Code: {self.device_code}")

config = Config()
