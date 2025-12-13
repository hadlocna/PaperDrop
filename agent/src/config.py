import json
import os
from pathlib import Path
from typing import Optional
import uuid

class Config:
    """Manages device configuration and credentials"""
    
    def __init__(self):
        # Allow overriding config dir for dev
        self.CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/etc/paperdrop"))
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        self.DEVICE_INFO_FILE = self.CONFIG_DIR / "device.json"
        self.WIFI_CREDENTIALS_FILE = self.CONFIG_DIR / "wifi.json"
        
        self.CLOUD_WS_URL = os.environ.get(
            "PAPERDROP_WS_URL", 
            "wss://paperdrop-backend.onrender.com/api/device/connect" 
            # Defaulting to Cloud URL for production
        )
        self.FIRMWARE_VERSION = "1.0.0"
        
        self._device_code = None
        self._device_secret = None
        self._load_device_info()
    
    def initialize(self):
        # Helper to ensure loaded
        if not self._device_code:
            self._load_device_info()

    def _load_device_info(self):
        """Load device code and secret from file"""
        if self.DEVICE_INFO_FILE.exists():
            try:
                data = json.loads(self.DEVICE_INFO_FILE.read_text())
                self._device_code = data.get("device_code")
                self._device_secret = data.get("device_secret")
            except Exception as e:
                print(f"Error reading device info: {e}")

        if not self._device_code:
            # Generate a random code if missing (Development / First Boot)
            # In production, this might be pre-provisioned.
            self._device_code = str(uuid.uuid4()).split('-')[0].upper()
            self._device_secret = str(uuid.uuid4())
            self._save_device_info()
    
    def _save_device_info(self):
        """Save device info to file"""
        self.DEVICE_INFO_FILE.write_text(json.dumps({
            "device_code": self._device_code,
            "device_secret": self._device_secret,
        }, indent=2))
    
    @property
    def device_code(self) -> str:
        return self._device_code
    
    @property
    def device_secret(self) -> str:
        return self._device_secret
    
    @property
    def cloud_ws_url(self) -> str:
        return self.CLOUD_WS_URL
    
    @property
    def firmware_version(self) -> str:
        return self.FIRMWARE_VERSION
    
    # ─────────────────────────────────────────────────────────────────
    # WiFi Credentials Management
    # ─────────────────────────────────────────────────────────────────
    
    def has_wifi_credentials(self) -> bool:
        """Check if WiFi credentials are saved"""
        return self.WIFI_CREDENTIALS_FILE.exists()
    
    def get_wifi_credentials(self) -> Optional[tuple[str, str]]:
        """Get saved WiFi credentials (ssid, password)"""
        if not self.WIFI_CREDENTIALS_FILE.exists():
            return None
        data = json.loads(self.WIFI_CREDENTIALS_FILE.read_text())
        return data.get("ssid"), data.get("password")
    
    def save_wifi_credentials(self, ssid: str, password: str):
        """Save WiFi credentials"""
        self.WIFI_CREDENTIALS_FILE.write_text(json.dumps({
            "ssid": ssid,
            "password": password,
        }, indent=2))
        # Secure the file
        try:
            os.chmod(self.WIFI_CREDENTIALS_FILE, 0o600)
        except:
            pass # Might fail on Windows/some filesystems
    
    def clear_wifi_credentials(self):
        """Remove saved WiFi credentials"""
        if self.WIFI_CREDENTIALS_FILE.exists():
            self.WIFI_CREDENTIALS_FILE.unlink()

config = Config()
