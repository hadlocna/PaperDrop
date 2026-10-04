import sys
import shutil
import tempfile
import unittest
import uuid
import os
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import speaker_manager as speakers


class SpeakerTests(unittest.TestCase):
    def test_rejects_command_injection_and_missing_addresses(self):
        for value in (None, '', 'AA:BB:CC:DD:EE:FF;reboot', '--help', 'AA:BB:CC:DD:EE:FF\n'):
            with self.assertRaises(ValueError):
                speakers.validate_address(value)
        self.assertEqual(speakers.validate_address('aa:bb:cc:dd:ee:ff'), 'AA:BB:CC:DD:EE:FF')

    def test_audio_filter_excludes_unrelated_bluetooth_devices(self):
        self.assertFalse(speakers.is_audio_device({'Name': 'Phone', 'Class': 0x0200}))
        self.assertFalse(speakers.is_audio_device({'Name': 'Anker keyboard', 'Class': 0x0500}))
        self.assertTrue(speakers.is_audio_device({'UUIDs': [speakers.AUDIO_SINK]}))
        self.assertTrue(speakers.is_audio_device({'UUIDs': [speakers.HANDS_FREE]}))
        self.assertTrue(speakers.is_audio_device({'Class': 0x240404}))

    def test_settings_persist_without_world_readable_permissions(self):
        directory = Path(tempfile.gettempdir()) / ('paperdrop-speaker-test-' + uuid.uuid4().hex)
        directory.mkdir()
        try:
            with patch.object(speakers, 'SETTINGS', directory / 'speaker.json'):
                speakers.save_settings({'address': 'AA:BB:CC:DD:EE:FF', 'autoConnect': False})
                self.assertFalse(speakers.load_settings()['autoConnect'])
                if os.name == 'posix':
                    self.assertEqual(speakers.SETTINGS.stat().st_mode & 0o777, 0o600)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_discovery_stops_when_status_fails(self):
        manager = speakers.Speakers.__new__(speakers.Speakers)
        manager.adapter = Mock(return_value=object())
        interface = Mock()
        manager.dbus = Mock()
        manager.dbus.Interface.return_value = interface
        manager.status = Mock(side_effect=RuntimeError('unavailable'))
        with patch.object(speakers.time, 'sleep'), self.assertRaises(RuntimeError):
            manager.scan()
        interface.StartDiscovery.assert_called_once()
        interface.StopDiscovery.assert_called_once()

    def test_manual_disconnect_disables_background_reconnect(self):
        manager = speakers.Speakers.__new__(speakers.Speakers)
        manager.target = Mock()
        with patch.object(speakers, 'load_settings', return_value={'address': 'AA:BB:CC:DD:EE:FF', 'autoConnect': False}):
            manager.reconnect()
        manager.target.assert_not_called()

    def test_microphone_falls_back_to_usb_capture_without_supported_profile(self):
        manager = speakers.Speakers.__new__(speakers.Speakers)
        manager.target = Mock()
        manager.properties = Mock(return_value={'UUIDs': [speakers.AUDIO_SINK]})
        manager.prepare_playback = Mock()
        manager.status = Mock(return_value={'ok': True})
        def fake_run(args, **kwargs):
            if args[0] == 'arecord':
                import wave
                with wave.open(args[-1], 'wb') as wav:
                    wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                    wav.writeframes(b'\0\0' * 24000)
            result = Mock()
            result.returncode = 0
            return result
        with patch.object(speakers, 'load_settings', return_value={'address': 'AA:BB:CC:DD:EE:FF'}), \
             patch.object(speakers, 'capture_pcm', return_value='plughw:CARD=Microphone,DEV=0'), \
             patch.object(speakers.tempfile, 'TemporaryDirectory') as temporary, \
             patch.object(speakers.subprocess, 'run', side_effect=fake_run) as run:
            temporary.return_value.__enter__.return_value = str(Path(tempfile.gettempdir()))
            result = manager.microphone_test()
        self.assertIn('PaperDrop USB microphone', result['message'])
        self.assertEqual(run.call_args_list[0].args[0][3], 'plughw:CARD=Microphone,DEV=0')
        self.assertIn('bluealsa:DEV=AA:BB:CC:DD:EE:FF,PROFILE=a2dp', run.call_args_list[1].args[0])

    def test_music_playback_uses_generic_connect_instead_of_profile_switching(self):
        manager = speakers.Speakers.__new__(speakers.Speakers)
        manager.properties = Mock(return_value={'UUIDs': [speakers.HANDS_FREE, speakers.AUDIO_SINK],
                                                'Address': 'AA:BB:CC:DD:EE:FF',
                                                'Connected': False})
        manager.dbus = Mock()
        interface = manager.dbus.Interface.return_value
        manager.prepare_playback(object())
        interface.Connect.assert_called_once_with(timeout=12)
        interface.DisconnectProfile.assert_not_called()
        interface.ConnectProfile.assert_not_called()

    def test_generic_connect_falls_back_to_bluetoothctl(self):
        manager = speakers.Speakers.__new__(speakers.Speakers)
        manager.properties = Mock(return_value={'Connected': False})
        manager.dbus = Mock()
        manager.dbus.exceptions.DBusException = Exception
        interface = manager.dbus.Interface.return_value
        error = Exception('Invalid arguments')
        error.get_dbus_name = Mock(return_value='org.bluez.Error.InvalidArguments')
        interface.Connect.side_effect = error
        with patch.object(speakers.subprocess, 'run') as run:
            run.return_value.returncode = 0
            manager.connect_device(object(), 'AA:BB:CC:DD:EE:FF', timeout=12)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-2:], ['connect', 'AA:BB:CC:DD:EE:FF'])

    def test_pairable_setting_restored_if_pairing_times_out(self):
        manager = speakers.Speakers.__new__(speakers.Speakers)
        manager.status = Mock(return_value={'audioReady': True})
        manager.target = Mock()
        manager.adapter = Mock()
        manager.properties = Mock(return_value={'Paired': False})
        manager.dbus = Mock()
        adapter_props = manager.dbus.Interface.return_value
        adapter_props.Get.return_value = False
        manager.dbus.Boolean.side_effect = bool
        with patch.object(speakers.subprocess, 'run', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                manager.connect('AA:BB:CC:DD:EE:FF')
        self.assertEqual(adapter_props.Set.call_args_list[-1].args, (speakers.ADAPTER, 'Pairable', False))


if __name__ == '__main__':
    unittest.main()
