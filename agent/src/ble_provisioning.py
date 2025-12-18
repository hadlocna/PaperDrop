#!/usr/bin/env python3
"""
BLE Provisioning GATT Server using official BlueZ Python pattern.
"""

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
import json
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import os
import time
import threading
from gi.repository import GLib

# Logging setup
LOG_FILE = '/var/log/paperdrop/ble.log'
try:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
except:
    pass

log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
try:
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5)
    file_handler.setFormatter(log_formatter)
    handlers = [file_handler, logging.StreamHandler()]
except:
    handlers = [logging.StreamHandler()]

logging.basicConfig(
    level=logging.INFO,
    handlers=handlers
)
logger = logging.getLogger("BLEProvisioning")

BLUEZ_SERVICE_NAME = "org.bluez"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

# UUIDs
SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
DEVICE_ID_CHRC_UUID = "12345678-1234-5678-1234-56789abcdef1"
WIFI_CONFIG_CHRC_UUID = "12345678-1234-5678-1234-56789abcdef2"
WIFI_NETWORKS_CHRC_UUID = "12345678-1234-5678-1234-56789abcdef3"
WIFI_STATUS_CHRC_UUID = "12345678-1234-5678-1234-56789abcdef4"

# Global status
wifi_status = "idle"  # idle, connecting, connected, failed
wifi_error = ""
wifi_status_obj = None

def update_wifi_status(new_status, error=""):
    global wifi_status, wifi_error
    wifi_status = new_status
    wifi_error = error
    logger.info(f"WiFi Status updated: {wifi_status} {f'({error})' if error else ''}")
    if wifi_status_obj:
        status_data = json.dumps({"status": wifi_status, "error": wifi_error})
        wifi_status_obj.PropertiesChanged(
            GATT_CHRC_IFACE,
            {'Value': [dbus.Byte(b) for b in status_data.encode('utf-8')]},
            []
        )

def connect_wifi_task(ssid, password):
    update_wifi_status("connecting")
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Connecting to WiFi: {ssid} (Attempt {attempt}/{max_retries})")
            
            # Delete any existing connection for this SSID first
            subprocess.run(['sudo', 'nmcli', 'connection', 'delete', ssid], 
                           capture_output=True, text=True)
            
            # Create new connection
            result = subprocess.run([
                'sudo', 'nmcli', 'connection', 'add',
                'type', 'wifi',
                'con-name', ssid,
                'ssid', ssid,
                'wifi-sec.key-mgmt', 'wpa-psk',
                'wifi-sec.psk', password
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"Failed to create connection: {result.stderr}")
                if attempt == max_retries:
                    update_wifi_status("failed", f"Failed to create connection: {result.stderr}")
                    return
                time.sleep(2)
                continue
            
            # Now activate the connection
            result = subprocess.run(
                ['sudo', 'nmcli', 'connection', 'up', ssid],
                capture_output=True, text=True, timeout=45
            )
            
            if result.returncode == 0:
                logger.info("WiFi connected successfully!")
                try:
                    os.makedirs('/etc/paperdrop', exist_ok=True)
                    with open('/etc/paperdrop/wifi-provisioned', 'w') as f:
                        f.write('1')
                    # Save credentials for reuse
                    with open('/etc/paperdrop/wifi.json', 'w') as f:
                        json.dump({"ssid": ssid, "password": password}, f)
                except Exception as e:
                    logger.warning(f"Failed to save provisioned flag: {e}")
                
                update_wifi_status("connected")
                return
            else:
                logger.error(f"WiFi connection failed: {result.stderr}")
                if attempt == max_retries:
                    error_msg = result.stderr
                    if "Secrets were required, but not provided" in error_msg:
                        error_msg = "Invalid password"
                    elif "No network with SSID" in error_msg:
                        error_msg = "Network not found"
                    update_wifi_status("failed", error_msg)
                    return
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"Error in WiFi connection task: {e}")
            if attempt == max_retries:
                update_wifi_status("failed", str(e))
                return
            time.sleep(2)

def get_device_id():
    try:
        with open('/etc/paperdrop/device-id', 'r') as f:
            return f.read().strip()
    except:
        return "PD-UNKNOWN"

def scan_wifi_networks():
    """Scan for nearby WiFi networks and return as JSON list."""
    try:
        # Rescan for networks
        subprocess.run(['sudo', 'nmcli', 'dev', 'wifi', 'rescan'], capture_output=True)
        # Get list of networks
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list'],
            capture_output=True, text=True
        )
        networks = []
        seen = set()
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split(':')
                if len(parts) >= 4:
                    in_use = parts[0] == '*'
                    ssid = parts[1]
                    if ssid and ssid not in seen:
                        seen.add(ssid)
                        networks.append({
                            'ssid': ssid,
                            'signal': int(parts[2]) if parts[2].isdigit() else 0,
                            'security': parts[3] if parts[3] else 'Open',
                            'connected': in_use
                        })
        networks.sort(key=lambda x: x['signal'], reverse=True)
        return networks[:15]
    except Exception as e:
        logger.error(f'Error scanning WiFi: {e}')
        return []

class InvalidArgsException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"

class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotSupported"

class Advertisement(dbus.service.Object):
    PATH_BASE = "/org/bluez/example/advertisement"
    def __init__(self, bus, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = None
        self.local_name = None
        self.include_tx_power = False
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = dict()
        properties["Type"] = self.ad_type
        if self.service_uuids is not None:
            properties["ServiceUUIDs"] = dbus.Array(self.service_uuids, signature='s')
        if self.local_name is not None:
            properties["LocalName"] = dbus.String(self.local_name)
        if self.include_tx_power:
            properties["Includes"] = dbus.Array(["tx-power"], signature='s')
        return {LE_ADVERTISEMENT_IFACE: properties}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != LE_ADVERTISEMENT_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[LE_ADVERTISEMENT_IFACE]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE, in_signature='', out_signature='')
    def Release(self):
        logger.info('%s: Released!' % self.path)

class ProvisioningAdvertisement(Advertisement):
    def __init__(self, bus, index):
        Advertisement.__init__(self, bus, index, "peripheral")
        self.service_uuids = [SERVICE_UUID]
        self.local_name = "PaperDrop"
        self.include_tx_power = True

class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = "/"
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
        return response

class Service(dbus.service.Object):
    PATH_BASE = "/org/bluez/example/service"
    def __init__(self, bus, index, uuid, primary):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                'UUID': self.uuid,
                'Primary': self.primary,
                'Characteristics': dbus.Array(self.get_characteristic_paths(), signature='o')
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_characteristic_paths(self):
        return [chrc.get_path() for chrc in self.characteristics]

    def get_characteristics(self):
        return self.characteristics

    @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_SERVICE_IFACE]

class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + '/char' + str(index)
        self.bus = bus
        self.uuid = uuid
        self.service = service
        self.flags = flags
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                'Service': self.service.get_path(),
                'UUID': self.uuid,
                'Flags': self.flags,
                'Descriptors': dbus.Array([], signature='o')
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='a{sv}', out_signature='ay')
    def ReadValue(self, options):
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        raise NotSupportedException()

    @dbus.service.signal(DBUS_PROP_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

class ProvisioningService(Service):
    def __init__(self, bus, index):
        global wifi_status_obj
        Service.__init__(self, bus, index, SERVICE_UUID, True)
        self.add_characteristic(DeviceIdCharacteristic(bus, 0, self))
        self.add_characteristic(WifiConfigCharacteristic(bus, 1, self))
        self.add_characteristic(WifiNetworksCharacteristic(bus, 2, self))
        wifi_status_obj = WifiStatusCharacteristic(bus, 3, self)
        self.add_characteristic(wifi_status_obj)

class DeviceIdCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, DEVICE_ID_CHRC_UUID, ['read'], service)
    def ReadValue(self, options):
        device_id = get_device_id()
        return [dbus.Byte(b) for b in device_id.encode('utf-8')]

class WifiConfigCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, WIFI_CONFIG_CHRC_UUID, ['write'], service)
    def WriteValue(self, value, options):
        try:
            text = bytes(value).decode('utf-8')
            data = json.loads(text)
            ssid = data.get('ssid')
            password = data.get('password')
            if ssid and password:
                thread = threading.Thread(target=connect_wifi_task, args=(ssid, password))
                thread.daemon = True
                thread.start()
            else:
                update_wifi_status("failed", "Missing SSID or password")
        except Exception as e:
            update_wifi_status("failed", str(e))

class WifiNetworksCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, WIFI_NETWORKS_CHRC_UUID, ['read'], service)
    def ReadValue(self, options):
        networks = scan_wifi_networks()
        return [dbus.Byte(b) for b in json.dumps(networks).encode('utf-8')]

class WifiStatusCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, WIFI_STATUS_CHRC_UUID, ['read', 'notify'], service)
        self.notifying = False
    def ReadValue(self, options):
        status_data = json.dumps({"status": wifi_status, "error": wifi_error})
        return [dbus.Byte(b) for b in status_data.encode('utf-8')]
    def StartNotify(self):
        self.notifying = True
    def StopNotify(self):
        self.notifying = False

def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'), DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()
    for o, props in objects.items():
        if GATT_MANAGER_IFACE in props.keys():
            return o
    return None

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter = find_adapter(bus)
    if not adapter:
        logger.error('GattManager1 interface not found')
        return

    service_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter), GATT_MANAGER_IFACE)
    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter), LE_ADVERTISING_MANAGER_IFACE)
    
    app = Application(bus)
    app.add_service(ProvisioningService(bus, 0))
    adv = ProvisioningAdvertisement(bus, 0)
    
    mainloop = GLib.MainLoop()
    service_manager.RegisterApplication(app.get_path(), {}, 
                                       reply_handler=lambda: logger.info('GATT application registered'),
                                       error_handler=lambda e: logger.error(f'Failed to register application: {e}'))
    ad_manager.RegisterAdvertisement(adv.get_path(), {},
                                    reply_handler=lambda: logger.info('Advertisement registered'),
                                    error_handler=lambda e: logger.error(f'Failed to register advertisement: {e}'))
    
    logger.info(f'BLE Provisioning started. Device ID: {get_device_id()}')
    mainloop.run()

if __name__ == '__main__':
    main()
