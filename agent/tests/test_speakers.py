import sys
import tempfile
import unittest
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
        with tempfile.TemporaryDirectory() as directory, patch.object(speakers, 'SETTINGS', Path(directory) / 'speaker.json'):
            speakers.save_settings({'address': 'AA:BB:CC:DD:EE:FF', 'autoConnect': False})
            self.assertFalse(speakers.load_settings()['autoConnect'])
            self.assertEqual(speakers.SETTINGS.stat().st_mode & 0o777, 0o600)

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

    def test_microphone_not_captured_without_supported_profile(self):
        manager = speakers.Speakers.__new__(speakers.Speakers)
        manager.target = Mock()
        manager.properties = Mock(return_value={'UUIDs': [speakers.AUDIO_SINK]})
        with patch.object(speakers, 'load_settings', return_value={'address': 'AA:BB:CC:DD:EE:FF'}), patch.object(speakers.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'does not expose'):
                manager.microphone_test()
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
