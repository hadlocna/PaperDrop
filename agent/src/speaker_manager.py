#!/usr/bin/python3
"""Bounded BlueZ speaker operations. Run with the OS Python (python3-dbus)."""
import argparse
import base64
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import subprocess
import tempfile
import time
import wave

AUDIO_SINK = '0000110b-0000-1000-8000-00805f9b34fb'
HANDS_FREE = '0000111e-0000-1000-8000-00805f9b34fb'
HEADSET = '00001108-0000-1000-8000-00805f9b34fb'
DEVICE = 'org.bluez.Device1'
ADAPTER = 'org.bluez.Adapter1'
PROPS = 'org.freedesktop.DBus.Properties'
SETTINGS = Path('/etc/paperdrop/speaker.json')


def validate_address(address):
    if not isinstance(address, str) or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', address):
        raise ValueError('Select a valid Bluetooth speaker.')
    return address.upper()


def is_audio_device(props):
    return (bool({AUDIO_SINK, HANDS_FREE, HEADSET}.intersection(str(u).lower() for u in props.get('UUIDs', [])))
            or str(props.get('Icon', '')).startswith('audio-')
            or (int(props.get('Class', 0)) & 0x1f00) == 0x0400)


def load_settings():
    try:
        value = json.loads(SETTINGS.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(value):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=SETTINGS.parent, prefix='.speaker-')
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle)
        os.replace(name, SETTINGS)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Speakers:
    def __init__(self):
        import dbus
        self.dbus = dbus
        self.bus = dbus.SystemBus()

    def objects(self):
        return self.dbus.Interface(self.bus.get_object('org.bluez', '/'),
                                   'org.freedesktop.DBus.ObjectManager').GetManagedObjects()

    def adapter(self):
        for path, interfaces in self.objects().items():
            if ADAPTER in interfaces:
                return self.bus.get_object('org.bluez', path)
        raise RuntimeError('No Bluetooth adapter found on this PaperDrop.')

    def target(self, address):
        address = validate_address(address)
        for path, interfaces in self.objects().items():
            props = interfaces.get(DEVICE, {})
            if str(props.get('Address', '')).upper() == address:
                if not is_audio_device(props):
                    raise ValueError('This device does not advertise Bluetooth audio. Put the speaker in pairing mode and scan again.')
                return self.bus.get_object('org.bluez', path)
        raise ValueError('Speaker not found. Put it in pairing mode and scan again.')

    def properties(self, obj):
        return self.dbus.Interface(obj, PROPS).GetAll(DEVICE)

    def status(self):
        saved = load_settings()
        adapter = self.adapter()
        powered = bool(self.dbus.Interface(adapter, PROPS).Get(ADAPTER, 'Powered'))
        devices = []
        for interfaces in self.objects().values():
            props = interfaces.get(DEVICE, {})
            if not is_audio_device(props):
                continue
            address = str(props.get('Address', ''))
            devices.append({
                'address': address, 'name': str(props.get('Alias') or props.get('Name') or address),
                'paired': bool(props.get('Paired', False)), 'connected': bool(props.get('Connected', False)),
                'selected': address == saved.get('address'),
                'rssi': int(props['RSSI']) if 'RSSI' in props else None,
                'microphoneSupported': bool({HANDS_FREE, HEADSET}.intersection(str(u).lower() for u in props.get('UUIDs', []))),
            })
        ready = (shutil.which('aplay') is not None and
                 subprocess.run(['systemctl', 'is-active', '--quiet', 'bluealsa.service']).returncode == 0)
        return {'ok': True, 'powered': powered, 'audioReady': ready,
                'selectedAddress': saved.get('address'), 'autoConnect': bool(saved.get('autoConnect')),
                'devices': sorted(devices, key=lambda d: (not d['selected'], not d['connected'], d['name']))}

    def scan(self):
        adapter = self.adapter()
        self.dbus.Interface(adapter, PROPS).Set(ADAPTER, 'Powered', self.dbus.Boolean(True))
        interface = self.dbus.Interface(adapter, ADAPTER)
        # Discovery is owned by this D-Bus connection; never stop another client's session.
        interface.StartDiscovery()
        try:
            time.sleep(10)
            return self.status()
        finally:
            interface.StopDiscovery()

    def connect(self, address):
        address = validate_address(address)
        if not self.status()['audioReady']:
            raise RuntimeError('Speaker audio support is not installed yet. Update this PaperDrop first.')
        obj = self.target(address)
        props = self.properties(obj)
        if not props.get('Bonded', props.get('Paired')):
            # Register a temporary outgoing-pairing agent; never enable general discoverability.
            adapter_props = self.dbus.Interface(self.adapter(), PROPS)
            was_pairable = adapter_props.Get(ADAPTER, 'Pairable')
            adapter_props.Set(ADAPTER, 'Pairable', self.dbus.Boolean(True))
            try:
                subprocess.run(['bluetoothctl', '--agent', 'NoInputNoOutput', '--timeout', '25', 'pair', address],
                               capture_output=True, text=True, timeout=30)
            finally:
                adapter_props.Set(ADAPTER, 'Pairable', was_pairable)
            props = self.properties(obj)
            if not props.get('Bonded', props.get('Paired')):
                raise RuntimeError('Pairing failed. Put the speaker in pairing mode, disconnect it from other devices, and try again.')
        self.dbus.Interface(obj, PROPS).Set(DEVICE, 'Trusted', self.dbus.Boolean(True))
        if not self.properties(obj).get('Connected'):
            self.dbus.Interface(obj, DEVICE).ConnectProfile(AUDIO_SINK, timeout=15)
        self.prepare_playback(obj)
        if not self.properties(obj).get('Connected'):
            raise RuntimeError('Speaker did not connect. Check its power and pairing mode.')
        old = load_settings().get('address')
        save_settings({'address': address, 'autoConnect': True})
        if old and old != address:
            try:
                self.dbus.Interface(self.target(old), DEVICE).Disconnect(timeout=5)
            except Exception:
                pass
        return self.status()

    def disconnect(self, address):
        address = validate_address(address)
        obj = self.target(address)
        saved = load_settings()
        if saved.get('address') == address:
            save_settings({'address': address, 'autoConnect': False})
        if self.properties(obj).get('Connected'):
            self.dbus.Interface(obj, DEVICE).Disconnect(timeout=8)
        return self.status()

    def reconnect(self):
        saved = load_settings()
        if saved.get('autoConnect') and saved.get('address'):
            obj = self.target(saved['address'])
            if not self.properties(obj).get('Connected'):
                self.dbus.Interface(obj, DEVICE).ConnectProfile(AUDIO_SINK, timeout=12)
        return {'ok': True}

    def prepare_playback(self, obj):
        # Hands-free mode can mute music on combination speakerphones.
        interface = self.dbus.Interface(obj, DEVICE)
        uuids = {str(u).lower() for u in self.properties(obj).get('UUIDs', [])}
        for profile in (HANDS_FREE, HEADSET):
            if profile in uuids:
                try:
                    interface.DisconnectProfile(profile, timeout=5)
                except self.dbus.exceptions.DBusException as error:
                    if error.get_dbus_name() not in ('org.bluez.Error.NotConnected', 'org.bluez.Error.DoesNotExist'):
                        raise
        try:
            interface.ConnectProfile(AUDIO_SINK, timeout=12)
        except self.dbus.exceptions.DBusException as error:
            if error.get_dbus_name() != 'org.bluez.Error.AlreadyConnected':
                raise

    def test(self):
        address = validate_address(load_settings().get('address'))
        obj = self.target(address)
        if not self.properties(obj).get('Connected'):
            raise RuntimeError('Connect your selected speaker before playing a test sound.')
        self.prepare_playback(obj)
        # A soft, bouncing marimba flourish, with time for Bluetooth to wake up.
        with tempfile.TemporaryDirectory(prefix='paperdrop-chime-') as directory:
            filename = str(Path(directory) / 'chime.wav')
            with wave.open(filename, 'wb') as output:
                output.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
                frames = bytearray()
                notes = [(0.65, 523.25), (0.88, 659.25), (1.11, 783.99), (1.46, 1046.5)]
                for i in range(int(3.0 * 44100)):
                    t = i / 44100
                    value = 0.0
                    for onset, frequency in notes:
                        age = t - onset
                        if 0 <= age < 0.85:
                            envelope = min(age / 0.008, 1) * math.exp(-6 * age)
                            value += envelope * (math.sin(2 * math.pi * frequency * age)
                                                 + 0.22 * math.sin(2 * math.pi * frequency * 3 * age))
                    sample = int(4500 * value)
                    frames.extend(struct.pack('<hh', sample, sample))
                output.writeframes(frames)
            result = subprocess.run(['aplay', '-q', '-D', f'bluealsa:DEV={address},PROFILE=a2dp', filename],
                                    capture_output=True, text=True, timeout=12)
            if result.returncode:
                raise RuntimeError('Unable to play audio. Reconnect the speaker and try again.')
        return {**self.status(), 'message': 'Test sound played.'}

    def microphone_test(self):
        address = validate_address(load_settings().get('address'))
        obj = self.target(address)
        uuids = [str(u).lower() for u in self.properties(obj).get('UUIDs', [])]
        profile = HANDS_FREE if HANDS_FREE in uuids else HEADSET if HEADSET in uuids else None
        if not profile:
            raise RuntimeError('This speaker does not expose a Bluetooth microphone. A microphone-capable headset or speaker is needed.')
        try:
            self.dbus.Interface(obj, DEVICE).ConnectProfile(profile, timeout=12)
        except self.dbus.exceptions.DBusException as error:
            if error.get_dbus_name() != 'org.bluez.Error.AlreadyConnected':
                raise
        try:
            # Explicit user action only: five seconds, local playback, then delete.
            with tempfile.TemporaryDirectory(prefix='paperdrop-mic-') as directory:
                filename = str(Path(directory) / 'microphone.wav')
                pcm = f'bluealsa:DEV={address},PROFILE=sco'
                result = subprocess.run(['arecord', '-q', '-D', pcm, '-f', 'S16_LE', '-r', '8000', '-c', '1',
                                         '-d', '5', filename], capture_output=True, text=True, timeout=12)
                if result.returncode:
                    raise RuntimeError('The Bluetooth microphone could not record. Reconnect the speaker and try again.')
                result = subprocess.run(['aplay', '-q', '-D', pcm, filename], capture_output=True, text=True, timeout=12)
                if result.returncode:
                    raise RuntimeError('Microphone recorded, but playback failed. Reconnect the speaker and try again.')
        finally:
            self.prepare_playback(obj)
        return {**self.status(), 'message': 'Microphone test finished. The recording was played locally and deleted.'}

    def play(self):
        address = validate_address(load_settings().get('address'))
        obj = self.target(address)
        if not self.properties(obj).get('Connected'):
            raise RuntimeError('Connect the selected speaker first.')
        self.prepare_playback(obj)
        encoded = sys.stdin.read(2000001)
        if len(encoded) > 2000000:
            raise ValueError('Audio clip is too large.')
        audio = base64.b64decode(encoded, validate=True)
        with tempfile.TemporaryDirectory(prefix='paperdrop-voice-') as directory:
            filename = str(Path(directory) / 'voice.wav')
            Path(filename).write_bytes(audio)
            with wave.open(filename) as clip:
                if clip.getnframes() / clip.getframerate() > 20:
                    raise ValueError('Audio clips must be 20 seconds or shorter.')
            result = subprocess.run(['aplay', '-q', '-D', f'bluealsa:DEV={address},PROFILE=a2dp', filename],
                                    capture_output=True, text=True, timeout=25)
            if result.returncode:
                raise RuntimeError('Voice playback failed. Reconnect the speaker and try again.')
        return {'ok': True, 'message': 'Voice message played.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'scan', 'connect', 'disconnect', 'test', 'reconnect', 'microphone_test', 'play'])
    parser.add_argument('address', nargs='?')
    args = parser.parse_args()
    try:
        speakers = Speakers()
        result = getattr(speakers, args.action)(args.address) if args.action in ('connect', 'disconnect') else getattr(speakers, args.action)()
    except Exception as error:
        result = {'ok': False, 'error': str(error)}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
