"""NetworkManager fixtures plus real HTTP requests; no radio or device changes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler, urlopen

spec = importlib.util.spec_from_file_location('wifi_portal', Path(__file__).resolve().parents[1] / 'factory/wifi_portal.py')
wifi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wifi)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class NetworkTests(unittest.TestCase):
    def test_scan_preserves_escaped_names_and_deduplicates_strongest(self):
        networks = wifi.parse_networks('Home\\:West:30:WPA2\nHome\\:West:90:WPA2\n'
                                       'Back\\\\Room:70:WPA3\nCafe:65:--\n'
                                       'Office:60:WPA2 802.1X\n:90:WPA2\nPaperDrop-Setup:100:WPA2\n')
        self.assertEqual([n['ssid'] for n in networks], ['Home:West', 'Back\\Room', 'Cafe', 'Office'])
        self.assertFalse(networks[2]['secured'])
        self.assertFalse(networks[3]['supported'])

    def test_scan_timeout_keeps_previous_networks(self):
        portal = wifi.Portal()
        portal.networks = [{'ssid': 'Fixture'}]
        with patch.object(wifi, 'run', side_effect=subprocess.TimeoutExpired('nmcli', 35)):
            result = portal.scan(force=True)
        self.assertEqual(result['networks'], [{'ssid': 'Fixture'}])
        self.assertIn('could not refresh', result['message'])

    def test_ap_scan_falls_back_to_cached_networks(self):
        portal = wifi.Portal()
        with patch.object(wifi, 'run', side_effect=[Mock(returncode=1, stdout=''), Mock(returncode=0, stdout='Home:80:WPA2')]):
            result = portal.scan(force=True)
        self.assertEqual(result['networks'][0]['ssid'], 'Home')
        self.assertIn('last available scan', result['message'])

    def test_failed_activation_restores_ap_without_leaking_password(self):
        portal = wifi.Portal()
        portal.state['state'] = 'connecting'
        with patch.object(wifi.time, 'sleep'), patch.object(portal, 'stop_dns'), patch.object(portal, 'start_ap') as restore, \
                patch.object(wifi, 'run', side_effect=[Mock(returncode=0)] * 4 + [Mock(returncode=1, stderr='private fixture')]):
            portal.connect('Home', 'fixture-password', 'PT', 'secured')
        restore.assert_called_once()
        self.assertEqual(portal.state['state'], 'failed')
        self.assertNotIn('private fixture', json.dumps(portal.state))

    def test_timeout_restores_ap(self):
        portal = wifi.Portal()
        with patch.object(wifi.time, 'sleep'), patch.object(portal, 'start_ap') as restore, \
                patch.object(wifi, 'run', side_effect=subprocess.TimeoutExpired('nmcli', 35)):
            portal.connect('Home', 'fixture-password', 'PT', 'secured')
        restore.assert_called_once()
        self.assertEqual(portal.state['state'], 'failed')

    def test_open_network_omits_password_and_runtime_failure_keeps_wifi(self):
        portal = wifi.Portal()
        with patch.object(wifi.time, 'sleep'), patch.object(portal, 'stop_dns'), patch.object(portal, 'start_ap') as restore, \
                patch.object(wifi, 'connected', return_value=True), patch.object(wifi, 'run') as run:
            run.side_effect = [Mock(returncode=0)] * 5 + [subprocess.TimeoutExpired('systemctl', 35)]
            portal.connect('Cafe', '', 'PT', 'open')
        settings = run.call_args_list[2].args
        self.assertEqual(settings[settings.index('802-11-wireless-security.psk') + 1], '')
        self.assertEqual(settings[settings.index('802-11-wireless-security.key-mgmt') + 1], 'none')
        self.assertNotIn('password', run.call_args_list[4].args)
        self.assertEqual(portal.state['state'], 'connected')
        restore.assert_not_called()

    def test_manually_entered_hidden_network_is_probed(self):
        portal = wifi.Portal()
        with patch.object(wifi.time, 'sleep'), patch.object(portal, 'stop_dns'), \
                patch.object(wifi, 'connected', return_value=True), patch.object(wifi, 'run', return_value=Mock(returncode=0)) as run:
            portal.connect('Hidden Home', 'fixture-password', 'PT', 'secured', hidden=True)
        settings = run.call_args_list[2].args
        self.assertEqual(settings[settings.index('802-11-wireless.hidden') + 1], 'yes')
        self.assertEqual(portal.state['state'], 'connected')

    def test_hotspot_transition_configures_security_before_profile_activation(self):
        portal = wifi.Portal()
        with patch.object(wifi.time, 'sleep'), patch.object(portal, 'stop_dns'), \
                patch.object(wifi, 'connected', return_value=True), patch.object(wifi, 'run', return_value=Mock(returncode=0)) as run:
            portal.connect('Home', 'fixture-password', 'PT', 'secured')
        settings = run.call_args_list[2].args
        self.assertEqual(settings[settings.index('802-11-wireless-security.key-mgmt') + 1], 'wpa-psk')
        activation = run.call_args_list[4]
        self.assertEqual(activation.args[:3], ('nmcli', 'connection', 'up'))
        self.assertGreaterEqual(activation.kwargs['timeout'], 90)

    def test_captive_dns_is_scoped_to_setup_interface(self):
        portal = wifi.Portal()
        with patch.object(wifi, 'run', return_value=Mock(returncode=0)), patch.object(wifi.time, 'sleep'), \
                patch.object(wifi.subprocess, 'Popen') as spawn:
            spawn.return_value.poll.return_value = None
            portal.start_ap()
        command = spawn.call_args.args[0]
        self.assertIn('--interface=wlan0', command)
        self.assertIn('--listen-address=10.42.0.1', command)
        self.assertIn('--conf-file=/dev/null', command)
        self.assertIn('--address=/#/10.42.0.1', command)

    def test_double_submission_does_not_start_second_attempt(self):
        portal = wifi.Portal()
        with patch.object(wifi.threading, 'Thread') as worker:
            data = {'ssid': 'Home', 'password': 'fixture-password', 'country': 'PT'}
            self.assertTrue(portal.begin_connection(data))
            self.assertFalse(portal.begin_connection(data))
        self.assertEqual(worker.call_count, 1)

    def test_invalid_input_never_starts_worker(self):
        for data in ({'ssid': 'é' * 17, 'password': 'fixture-password'},
                     {'ssid': 'Home', 'password': 'short'},
                     {'ssid': 'Home', 'password': 'fixture-password', 'country': 'P1'},
                     {'ssid': wifi.PROFILE, 'password': 'fixture-password'},
                     {'ssid': 'Home', 'password': 'fixture-password', 'security': 'enterprise'}):
            with self.subTest(data=data), patch.object(wifi.threading, 'Thread') as worker:
                with self.assertRaises(ValueError):
                    wifi.Portal().begin_connection(data)
                worker.assert_not_called()


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.portal = wifi.Portal()
        self.portal.country = 'PT'
        self.server = wifi.ThreadingHTTPServer(('127.0.0.1', 0), wifi.Setup)
        self.server.portal = self.portal
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def post(self, data, **headers):
        return urlopen(Request(self.base + '/connect', data=urlencode(data).encode(), headers=headers))

    def test_mobile_page_is_offline_and_has_network_picker(self):
        with urlopen(self.base) as response:
            body = response.read().decode()
            self.assertIn('Nearby networks', body)
            self.assertIn('value="PT"', body)
            self.assertIn('viewport', body)
            self.assertNotIn('https://', body)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_all_probe_paths_and_external_hosts_redirect_to_local_portal(self):
        opener = build_opener(NoRedirect)
        for path, host in [('/generate_204', 'connectivitycheck.gstatic.com'),
                           ('/hotspot-detect.html', 'captive.apple.com'),
                           ('/connecttest.txt', 'www.msftconnecttest.com'),
                           ('/', 'example.com')]:
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                opener.open(Request(self.base + path, headers={'Host': host}))
            self.assertEqual(error.exception.code, 302)
            self.assertEqual(error.exception.headers['Location'], 'http://10.42.0.1/')

    def test_scan_and_status_api_return_data_without_password(self):
        with patch.object(self.portal, 'scan', return_value={'networks': [{'ssid': '<script>Fixture</script>'}], 'message': ''}):
            result = json.load(urlopen(self.base + '/api/networks'))
        self.assertEqual(result['networks'][0]['ssid'], '<script>Fixture</script>')
        self.assertNotIn('password', json.load(urlopen(self.base + '/api/status')))

    def test_connection_requires_token_and_same_origin(self):
        data = {'ssid': 'Home', 'password': 'fixture-password', 'country': 'PT'}
        with patch.object(self.portal, 'begin_connection') as begin:
            with self.assertRaises(HTTPError) as error:
                self.post(data)
            self.assertEqual(error.exception.code, 403)
            with self.assertRaises(HTTPError) as error:
                self.post(dict(data, token=wifi.TOKEN), Origin='http://untrusted.example')
            self.assertEqual(error.exception.code, 403)
            begin.assert_not_called()

    def test_valid_connection_is_accepted_and_conflict_is_reported(self):
        with patch.object(self.portal, 'begin_connection', side_effect=[True, False]):
            with self.post({'token': wifi.TOKEN, 'ssid': 'Fixture'}, Accept='application/json') as response:
                self.assertEqual(response.status, 202)
            with self.assertRaises(HTTPError) as error:
                self.post({'token': wifi.TOKEN, 'ssid': 'Fixture'})
            self.assertEqual(error.exception.code, 409)

    def test_malformed_length_returns_bad_request(self):
        request = Request(self.base + '/connect', data=b'x', headers={'Content-Length': 'invalid'})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
