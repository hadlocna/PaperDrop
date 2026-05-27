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
        self.DEVICE_CONFIG_FILE = self.CONFIG_DIR / "config.json"
        self._runtime_config = self._load_runtime_config()
        
        self.CLOUD_WS_URL = (
            os.environ.get("PAPERDROP_WS_URL")
            or self._runtime_config.get("cloud_ws_url")
            or "wss://api.paperdrop.me/api/device/connect"
        )
        self.FIRMWARE_VERSION = self._load_firmware_version()
        
        self._device_code = None
        self._device_secret = None
        self._load_device_info()
    
    def initialize(self):
        # Helper to ensure loaded
        if not self._device_code:
            self._load_device_info()

    def _load_runtime_config(self) -> dict:
        """Load mutable runtime config written by remote management commands."""
        if not self.DEVICE_CONFIG_FILE.exists():
            return {}

        try:
            data = json.loads(self.DEVICE_CONFIG_FILE.read_text())
            return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"Error reading runtime config: {e}")
            return {}

    def save_runtime_config(self, updates: dict):
        """Persist mutable runtime configuration."""
        self._runtime_config.update(updates)
        self.DEVICE_CONFIG_FILE.write_text(json.dumps(self._runtime_config, indent=2))
        try:
            os.chmod(self.DEVICE_CONFIG_FILE, 0o600)
        except:
            pass

        if "cloud_ws_url" in updates and not os.environ.get("PAPERDROP_WS_URL"):
            self.CLOUD_WS_URL = updates["cloud_ws_url"]

    def _load_firmware_version(self) -> str:
        version_file = self.CONFIG_DIR / "firmware-version"
        try:
            if version_file.exists():
                version = version_file.read_text().strip()
                if version:
                    return version
        except Exception as e:
            print(f"Error reading firmware version: {e}")

        return os.environ.get("PAPERDROP_FIRMWARE_VERSION", "1.0.0")

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
            # Try to read from system identity file (created by first-boot)
            try:
                device_id_path = Path("/etc/paperdrop/device-id")
                if device_id_path.exists():
                    self._device_code = device_id_path.read_text().strip()
            except Exception:
                pass

        if not self._device_code:
            # Generate a random code if missing (Development / First Boot)
            # In production, this might be pre-provisioned.
            self._device_code = str(uuid.uuid4()).split('-')[0].upper()
            
        if not self._device_secret:
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
