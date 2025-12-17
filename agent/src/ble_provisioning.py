#!/usr/bin/env python3
"""
BLE Provisioning using BlueZ DBus API directly.
Works with Python 3.13 and standard dbus-next.
"""

import asyncio
import logging
import json
import subprocess
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, dbus_property
from dbus_next import Variant, DBusError, BusType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BLEProvisioning")

BLUEZ_SERVICE = "org.bluez"
ADAPTER_PATH = "/org/bluez/hci0"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
ADAPTER_IFACE = "org.bluez.Adapter1"

SERVICE_UUID = "a07498ca-ad5b-474e-940d-16f1fbe7e8cd"
DEVICE_ID_UUID = "a07498ca-ad5b-474e-940d-16f1fbe7e8ce"
WIFI_CONFIG_UUID = "a07498ca-ad5b-474e-940d-16f1fbe7e8cf"

APP_PATH = "/com/paperdrop/ble"
SERVICE_PATH = f"{APP_PATH}/service0"
CHAR_DEVICE_ID_PATH = f"{SERVICE_PATH}/char0"
CHAR_WIFI_CONFIG_PATH = f"{SERVICE_PATH}/char1"
ADVERT_PATH = f"{APP_PATH}/advertisement0"

def get_device_id():
    try:
        with open('/etc/paperdrop/device-id', 'r') as f:
            return f.read().strip()
    except:
        return "PD-UNKNOWN"

# --- GATT Service ---
class GattService(ServiceInterface):
    def __init__(self):
        super().__init__("org.bluez.GattService1")
    
    @dbus_property()
    def UUID(self) -> 's':
        return SERVICE_UUID
    
    @UUID.setter
    def UUID(self, value: 's'):
        pass
    
    @dbus_property()
    def Primary(self) -> 'b':
        return True
    
    @Primary.setter
    def Primary(self, value: 'b'):
        pass

# --- GATT Characteristics ---
class GattCharacteristicDeviceId(ServiceInterface):
    def __init__(self):
        super().__init__("org.bluez.GattCharacteristic1")
        self._uuid = DEVICE_ID_UUID
        self._service = SERVICE_PATH
        self._flags = ["read"]
    
    @dbus_property()
    def UUID(self) -> 's':
        return self._uuid
    
    @UUID.setter
    def UUID(self, value: 's'):
        pass
    
    @dbus_property()
    def Service(self) -> 'o':
        return self._service
    
    @Service.setter
    def Service(self, value: 'o'):
        pass
    
    @dbus_property()
    def Flags(self) -> 'as':
        return self._flags
    
    @Flags.setter
    def Flags(self, value: 'as'):
        pass
    
    @method()
    def ReadValue(self, options: 'a{sv}') -> 'ay':
        device_id = get_device_id()
        logger.info(f"ReadValue DeviceID: {device_id}")
        return list(device_id.encode('utf-8'))

class GattCharacteristicWifiConfig(ServiceInterface):
    def __init__(self):
        super().__init__("org.bluez.GattCharacteristic1")
        self._uuid = WIFI_CONFIG_UUID
        self._service = SERVICE_PATH
        self._flags = ["write"]
    
    @dbus_property()
    def UUID(self) -> 's':
        return self._uuid
    
    @UUID.setter
    def UUID(self, value: 's'):
        pass
    
    @dbus_property()
    def Service(self) -> 'o':
        return self._service
    
    @Service.setter
    def Service(self, value: 'o'):
        pass
    
    @dbus_property()
    def Flags(self) -> 'as':
        return self._flags
    
    @Flags.setter
    def Flags(self, value: 'as'):
        pass
    
    @method()
    def WriteValue(self, value: 'ay', options: 'a{sv}') -> None:
        try:
            text = bytes(value).decode('utf-8')
            logger.info(f"WriteValue WiFiConfig: {text}")
            data = json.loads(text)
            ssid = data.get("ssid")
            password = data.get("password")
            
            if ssid and password:
                logger.info(f"Connecting to WiFi: {ssid}")
                result = subprocess.run(
                    ["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    logger.info("WiFi connected successfully!")
                    # Mark as provisioned
                    with open('/etc/paperdrop/wifi-provisioned', 'w') as f:
                        f.write("1")
                else:
                    logger.error(f"WiFi connection failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error processing WiFi config: {e}")

# --- GATT Application (ObjectManager) ---
class GattApplication(ServiceInterface):
    def __init__(self):
        super().__init__("org.freedesktop.DBus.ObjectManager")
    
    @method()
    def GetManagedObjects(self) -> 'a{oa{sa{sv}}}':
        return {
            SERVICE_PATH: {
                "org.bluez.GattService1": {
                    "UUID": Variant('s', SERVICE_UUID),
                    "Primary": Variant('b', True),
                }
            },
            CHAR_DEVICE_ID_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": Variant('s', DEVICE_ID_UUID),
                    "Service": Variant('o', SERVICE_PATH),
                    "Flags": Variant('as', ["read"]),
                }
            },
            CHAR_WIFI_CONFIG_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": Variant('s', WIFI_CONFIG_UUID),
                    "Service": Variant('o', SERVICE_PATH),
                    "Flags": Variant('as', ["write"]),
                }
            }
        }

# --- Advertisement ---
class LEAdvertisement(ServiceInterface):
    def __init__(self):
        super().__init__("org.bluez.LEAdvertisement1")
        self._type = "peripheral"
        self._service_uuids = [SERVICE_UUID]
        self._local_name = "PaperDrop"
    
    @dbus_property()
    def Type(self) -> 's':
        return self._type
    
    @Type.setter
    def Type(self, value: 's'):
        self._type = value
    
    @dbus_property()
    def ServiceUUIDs(self) -> 'as':
        return self._service_uuids
    
    @ServiceUUIDs.setter
    def ServiceUUIDs(self, value: 'as'):
        self._service_uuids = value
    
    @dbus_property()
    def LocalName(self) -> 's':
        return self._local_name
    
    @LocalName.setter
    def LocalName(self, value: 's'):
        self._local_name = value
    
    @method()
    def Release(self) -> None:
        logger.info("Advertisement released")


async def main():
    logger.info("Starting BLE Provisioning...")
    
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    
    # Export GATT Application (ObjectManager)
    app = GattApplication()
    bus.export(APP_PATH, app)
    
    # Export Service
    service = GattService()
    bus.export(SERVICE_PATH, service)
    
    # Export Characteristics
    char_device_id = GattCharacteristicDeviceId()
    bus.export(CHAR_DEVICE_ID_PATH, char_device_id)
    
    char_wifi_config = GattCharacteristicWifiConfig()
    bus.export(CHAR_WIFI_CONFIG_PATH, char_wifi_config)
    
    # Export Advertisement
    advert = LEAdvertisement()
    bus.export(ADVERT_PATH, advert)
    
    # Get BlueZ adapter
    introspection = await bus.introspect(BLUEZ_SERVICE, ADAPTER_PATH)
    proxy = bus.get_proxy_object(BLUEZ_SERVICE, ADAPTER_PATH, introspection)
    
    # Power on adapter
    adapter = proxy.get_interface(ADAPTER_IFACE)
    try:
        await adapter.set_powered(True)
        logger.info("Adapter powered on")
    except DBusError as e:
        logger.warning(f"Set powered: {e}")
    
    # Register GATT Application
    gatt_manager = proxy.get_interface(GATT_MANAGER_IFACE)
    try:
        await gatt_manager.call_register_application(APP_PATH, {})
        logger.info("GATT Application registered successfully!")
    except DBusError as e:
        logger.error(f"Failed to register GATT app: {e}")
    
    # Register Advertisement
    advert_manager = proxy.get_interface(LE_ADVERTISING_MANAGER_IFACE)
    try:
        await advert_manager.call_register_advertisement(ADVERT_PATH, {})
        logger.info("Advertisement registered successfully!")
    except DBusError as e:
        logger.error(f"Failed to register advertisement: {e}")
    
    logger.info("BLE Provisioning started. Device ID: " + get_device_id())
    logger.info("Waiting for connections...")
    
    # Keep running
    await asyncio.get_running_loop().create_future()

if __name__ == "__main__":
    asyncio.run(main())
