#!/usr/bin/env python3
"""
BLE Provisioning GATT Server using official BlueZ Python pattern.
Based on BlueZ test/example-gatt-server.

Uses PyGObject (GLib/dbus) which is the canonical way BlueZ expects 
GATT servers to be structured.
"""

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
import json
import subprocess
import logging
from gi.repository import GLib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BLEProvisioning")

BLUEZ_SERVICE_NAME = "org.bluez"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

# UUIDs - using fresh UUID to avoid collision
SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
DEVICE_ID_CHRC_UUID = "12345678-1234-5678-1234-56789abcdef1"
WIFI_CONFIG_CHRC_UUID = "12345678-1234-5678-1234-56789abcdef2"


def get_device_id():
    try:
        with open('/etc/paperdrop/device-id', 'r') as f:
            return f.read().strip()
    except:
        return "PD-UNKNOWN"


class InvalidArgsException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotSupported"


class NotPermittedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotPermitted"


# ==============================
# Advertisement
# ==============================

class Advertisement(dbus.service.Object):
    PATH_BASE = "/org/bluez/example/advertisement"

    def __init__(self, bus, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = None
        self.manufacturer_data = None
        self.solicit_uuids = None
        self.service_data = None
        self.local_name = None
        self.include_tx_power = False
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = dict()
        properties["Type"] = self.ad_type
        if self.service_uuids is not None:
            properties["ServiceUUIDs"] = dbus.Array(self.service_uuids, signature='s')
        if self.solicit_uuids is not None:
            properties["SolicitUUIDs"] = dbus.Array(self.solicit_uuids, signature='s')
        if self.manufacturer_data is not None:
            properties["ManufacturerData"] = dbus.Dictionary(self.manufacturer_data, signature='qv')
        if self.service_data is not None:
            properties["ServiceData"] = dbus.Dictionary(self.service_data, signature='sv')
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


# ==============================
# GATT Application
# ==============================

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
                descs = chrc.get_descriptors()
                for desc in descs:
                    response[desc.get_path()] = desc.get_properties()
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
                'Characteristics': dbus.Array(
                    self.get_characteristic_paths(),
                    signature='o')
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_characteristic_paths(self):
        result = []
        for chrc in self.characteristics:
            result.append(chrc.get_path())
        return result

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
        self.descriptors = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                'Service': self.service.get_path(),
                'UUID': self.uuid,
                'Flags': self.flags,
                'Descriptors': dbus.Array(
                    self.get_descriptor_paths(),
                    signature='o')
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_descriptor(self, descriptor):
        self.descriptors.append(descriptor)

    def get_descriptor_paths(self):
        result = []
        for desc in self.descriptors:
            result.append(desc.get_path())
        return result

    def get_descriptors(self):
        return self.descriptors

    @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='a{sv}', out_signature='ay')
    def ReadValue(self, options):
        logger.info('Default ReadValue called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        logger.info('Default WriteValue called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        logger.info('Default StartNotify called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        logger.info('Default StopNotify called, returning error')
        raise NotSupportedException()

    @dbus.service.signal(DBUS_PROP_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


# ==============================
# PaperDrop Provisioning Service
# ==============================

class ProvisioningService(Service):
    def __init__(self, bus, index):
        Service.__init__(self, bus, index, SERVICE_UUID, True)
        self.add_characteristic(DeviceIdCharacteristic(bus, 0, self))
        self.add_characteristic(WifiConfigCharacteristic(bus, 1, self))


class DeviceIdCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index,
            DEVICE_ID_CHRC_UUID,
            ['read'],
            service)

    def ReadValue(self, options):
        device_id = get_device_id()
        logger.info(f'Reading Device ID: {device_id}')
        return [dbus.Byte(b) for b in device_id.encode('utf-8')]


class WifiConfigCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index,
            WIFI_CONFIG_CHRC_UUID,
            ['write'],
            service)

    def WriteValue(self, value, options):
        try:
            text = bytes(value).decode('utf-8')
            logger.info(f'Received WiFi config: {text}')
            
            data = json.loads(text)
            ssid = data.get('ssid')
            password = data.get('password')
            
            if ssid and password:
                logger.info(f'Connecting to WiFi: {ssid}')
                result = subprocess.run(
                    ['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    logger.info('WiFi connected successfully!')
                    try:
                        with open('/etc/paperdrop/wifi-provisioned', 'w') as f:
                            f.write('1')
                    except:
                        pass
                else:
                    logger.error(f'WiFi connection failed: {result.stderr}')
            else:
                logger.error('Missing ssid or password')
        except Exception as e:
            logger.error(f'Error processing WiFi config: {e}')


# ==============================
# Main
# ==============================

def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'),
                               DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()

    for o, props in objects.items():
        if GATT_MANAGER_IFACE in props.keys():
            return o
    return None


def register_ad_cb():
    logger.info('Advertisement registered')


def register_ad_error_cb(error):
    logger.error(f'Failed to register advertisement: {error}')
    mainloop.quit()


def register_app_cb():
    logger.info('GATT application registered')


def register_app_error_cb(error):
    logger.error(f'Failed to register application: {error}')
    mainloop.quit()


def main():
    global mainloop

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()

    adapter = find_adapter(bus)
    if not adapter:
        logger.error('GattManager1 interface not found')
        return

    logger.info(f'Found adapter: {adapter}')

    service_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter),
        GATT_MANAGER_IFACE)

    ad_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter),
        LE_ADVERTISING_MANAGER_IFACE)

    app = Application(bus)
    app.add_service(ProvisioningService(bus, 0))

    adv = ProvisioningAdvertisement(bus, 0)

    mainloop = GLib.MainLoop()

    logger.info('Registering GATT application...')
    service_manager.RegisterApplication(
        app.get_path(), {},
        reply_handler=register_app_cb,
        error_handler=register_app_error_cb)

    logger.info('Registering advertisement...')
    ad_manager.RegisterAdvertisement(
        adv.get_path(), {},
        reply_handler=register_ad_cb,
        error_handler=register_ad_error_cb)

    device_id = get_device_id()
    logger.info(f'BLE Provisioning started. Device ID: {device_id}')
    logger.info(f'Service UUID: {SERVICE_UUID}')
    logger.info('Waiting for connections...')

    mainloop.run()


if __name__ == '__main__':
    main()
