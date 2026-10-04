"""Reuse the existing authenticated recorded-voice backend.

No OpenAI credential or API client is used on the device. The backend's ordinary
new_message images are printed through the same guarded Pi printer path used by
the button UI.
"""
import base64
import os
import subprocess
import sys
import io
import json
import logging
from pathlib import Path
import threading
import time
import uuid
from urllib.parse import urlencode
from PIL import Image
from websockets.sync.client import connect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


class Cloud:
    def __init__(self, root, printer=None):
        self.root = Path(root)
        self.printer = printer
        self.lock = threading.RLock()
        self.speaker_lock = threading.Lock()
        self.connected = threading.Event()
        self.stop = threading.Event()
        self.ws = None
        self.printer_ready_ack = False
        self.request = None
        self.deliveries = {}
        self.delivery_dir = self.root / 'deliveries'
        self.delivery_dir.mkdir(exist_ok=True)
        for path in self.delivery_dir.glob('*.json'):
            self.deliveries[path.stem] = json.loads(path.read_text())
        self.delivery_event = threading.Event()
        self.ack_dir = self.root / 'cloud-status'
        self.ack_dir.mkdir(exist_ok=True)
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def send(self, value):
        with self.lock:
            if not self.ws:
                raise RuntimeError('PaperDrop backend offline')
            self.ws.send(json.dumps(value))

    def status(self, ident, status, error=None):
        value = {'type': 'print_status', 'message_id': ident, 'status': status}
        if error:
            value['error'] = error
        path = self.ack_dir / (ident + '.json')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(value))
        temp.replace(path)
        try:
            self.send(value)
            path.unlink(missing_ok=True)
        except Exception:
            pass  # Queue while offline; the legacy backend has no receipt-of-status event.

    def run(self):
        device = json.loads(Path('/etc/paperdrop/device.json').read_text())
        config_path = Path('/etc/paperdrop/config.json')
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        base = config.get('cloud_ws_url', 'wss://api.paperdrop.me/api/device/connect')
        url = base + '?' + urlencode({'deviceCode': device['device_code'], 'deviceSecret': device['device_secret']})
        while not self.stop.is_set():
            try:
                with connect(url, max_size=16*1024*1024, open_timeout=15, close_timeout=3) as ws:
                    with self.lock:
                        self.ws = ws
                    self.send({'type': 'device_hello', 'firmware_version': os.environ.get('PAPERDROP_FIRMWARE_VERSION', 'streamdeck-pi-demo'), 'metrics': {}})
                    heartbeat = 0
                    while not self.stop.is_set():
                        if time.monotonic()-heartbeat > 20:
                            self.send({'type': 'heartbeat', 'firmware_version': os.environ.get('PAPERDROP_FIRMWARE_VERSION', 'streamdeck-pi-demo'), 'metrics': {}})
                            self.send({'type': 'mail_sync'})
                            self.send({'type': 'printer_notice_sync'})
                            heartbeat = time.monotonic()
                            for ident, delivery in list(self.deliveries.items()):
                                if delivery.get('status') not in ('printed','read','failed','not_found'):
                                    self.send({'type': 'mail_status' if delivery.get('type') == 'mail_result' else 'postcard_status', 'id':ident})
                        try:
                            event = json.loads(ws.recv(timeout=1))
                        except TimeoutError:
                            continue
                        kind = event.get('type')
                        if kind == 'ping':
                            self.send({'type': 'pong'})
                        elif kind == 'voice_control':
                            self.connected.set()
                            from release_health import mark_healthy
                            mark_healthy()
                            if event.get('request_id'):
                                self.send({'type': 'voice_result', 'request_id': event['request_id'], 'ok': True,
                                           'enabled': event.get('enabled'), 'state': 'button-demo'})
                            for path in self.ack_dir.glob('*.json'):
                                self.send(json.loads(path.read_text()))
                                path.unlink(missing_ok=True)
                        elif kind == 'speaker':
                            threading.Thread(target=self.speaker_command, args=(event,), daemon=True).start()
                        elif kind == 'fetch_logs':
                            self.fetch_logs(event)
                        elif kind == 'update':
                            subprocess.run(['systemctl', 'start', '--no-block', 'paperdrop-update.service'], check=False)
                            self.send({'type': 'update_status', 'request_id': event.get('request_id'), 'status': 'checking_stable'})
                        elif kind == 'test_connection':
                            self.send({'type': 'test_response', 'status': 'ok'})
                        else:
                            self.event(event)
            except Exception as exc:
                logging.warning('cloud_disconnected type=%s', type(exc).__name__)
            finally:
                self.connected.clear()
                with self.lock:
                    self.ws = None
                    if self.request:
                        self.request['error'] = 'Backend connection interrupted. Please try again.'
                        self.request['ready'].set()
                        self.request['done'].set()
            self.stop.wait(3)

    def speaker_command(self, event):
        import asyncio
        from speaker_control import run_speaker
        try:
            action = event.get('action')
            if action not in ('status', 'scan', 'connect', 'disconnect', 'test', 'microphone_test', 'play', 'volume'):
                raise ValueError('Unsupported action in button mode')
            with self.speaker_lock:
                result = asyncio.run(run_speaker(action, event.get('address'), event.get('audio'), event.get('volume')))
            self.send({**result, 'type': 'speaker_result', 'request_id': event.get('request_id')})
        except Exception:
            self.send({'ok': False, 'type': 'speaker_result', 'request_id': event.get('request_id'), 'error': 'Speaker command failed. Please try again.'})

    def fetch_logs(self, event):
        request_id = event.get('request_id')
        log_type = event.get('log_type', 'agent')
        try:
            lines = max(1, min(int(event.get('lines', 100)), 2000))
        except (TypeError, ValueError):
            lines = 100
        commands = {
            'agent': ['journalctl', '-u', 'paperdrop-runtime.service', '-n', str(lines), '--no-pager'],
            'system': ['journalctl', '-n', str(lines), '--no-pager'],
            'wifi': ['journalctl', '-u', 'NetworkManager.service', '-u', 'wpa_supplicant.service',
                     '-u', 'paperdrop-setup.service', '-n', str(lines), '--no-pager'],
            'provisioning': ['journalctl', '-u', 'paperdrop-enroll.service', '-u', 'paperdrop-setup.service',
                             '-n', str(lines), '--no-pager'],
        }
        command = commands.get(log_type, commands['agent'])
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            content = result.stdout
            if result.stderr:
                content += '\n[stderr]\n' + result.stderr
            self.send({'type': 'log_bundle', 'request_id': request_id, 'log_type': log_type,
                       'content': content[-60000:]})
        except Exception as exc:
            self.send({'type': 'error', 'request_id': request_id,
                       'message': f'Failed to fetch logs: {exc}'})

    def ordinary_message(self, event):
        message = event.get('message', {})
        ident = message.get('id') or uuid.uuid4().hex
        if not self.printer or message.get('contentType') != 'image':
            inbox = self.root / 'pending-cloud-mail'
            inbox.mkdir(exist_ok=True)
            (inbox / (uuid.uuid4().hex + '.json')).write_text(json.dumps(event))
            return
        target = self.root / 'app-messages' / (ident + '.png')
        target.parent.mkdir(exist_ok=True)
        try:
            content = message.get('content')
            if not isinstance(content, str):
                raise ValueError('image content is missing')
            if ',' in content:
                content = content.split(',', 1)[1]
            raw = base64.b64decode(content, validate=True)
            with Image.open(io.BytesIO(raw)) as img:
                img.convert('RGB').save(target)
            target.with_suffix('.cloud.json').write_text(json.dumps({'message_id': ident}))
            self.status(ident, 'printing')
            result = self.printer.print_image(target, ident)
            if getattr(self.printer, 'cloud', None) is not self and isinstance(result, dict) and result.get('status') == 'printed':
                self.status(ident, 'printed')
            logging.info('cloud_message_printed id=%s', ident)
        except Exception as exc:
            logging.warning('cloud_message_print_failed id=%s type=%s', ident, type(exc).__name__)
            self.status(ident, 'failed', str(exc))

    def event(self, event):
        if event.get('type') == 'printer_ready_ack':
            self.printer_ready_ack = True
            return
        if event.get('type') in ('cousin_mail', 'printer_notice'):
            message = event.get('message', {})
            ident = message.get('id', '')
            import re
            if re.fullmatch('[a-f0-9]{64}', ident):
                from cousin_mail import atomic_write
                folder = self.root / ('printer-notices' if event['type'] == 'printer_notice' else 'incoming-mail')
                folder.mkdir(exist_ok=True)
                atomic_write(folder / (ident + '.json'), json.dumps(message).encode())
            return
        if event.get('type') in ('postcard_result', 'mail_result'):
            ident = event.get('id','')
            if len(ident)==32 and all(c in '0123456789abcdef' for c in ident):
                with self.lock:
                    self.deliveries[ident] = event
                    path = self.delivery_dir / (ident+'.json')
                    temp = path.with_suffix('.tmp')
                    temp.write_text(json.dumps(event))
                    temp.replace(path)
                    self.delivery_event.set()
            return
        with self.lock:
            req = self.request
            if not req or event.get('session_id') != req['session']:
                if event.get('type') == 'new_message':
                    threading.Thread(target=self.ordinary_message, args=(event,), daemon=True).start()
                return
            kind = event.get('type')
            if kind == 'voice_ready':
                req['ready'].set()
            elif kind == 'voice_heard':
                req['prompt'] = event.get('text', '')
                # Progress callback runs outside the transport lock.
                threading.Thread(target=req['progress'], args=('Drawing your picture…',), daemon=True).start()
            elif kind == 'voice_print_pending':
                req['message_id'] = event['message_id']
            elif kind == 'new_message':
                message = event.get('message', {})
                if message.get('id') != req.get('message_id') or message.get('contentType') != 'image':
                    return
                req['content'] = message['content']
                req['done'].set()
            elif kind == 'voice_error':
                req['error'] = event.get('error', 'Drawing failed')
                req['ready'].set()
                req['done'].set()

    def draw(self, audio, target, progress):
        if not self.connected.wait(8):
            raise RuntimeError('PaperDrop backend is unavailable')
        req = dict(session=uuid.uuid4().hex, ready=threading.Event(), done=threading.Event(), progress=progress)
        with self.lock:
            if self.request:
                raise RuntimeError('A drawing is already in progress')
            self.request = req
        started = time.monotonic()
        try:
            progress('Listening to your idea…')
            self.send({'type': 'voice_start', 'mode': 'recorded', 'quality': 'low', 'session_id': req['session']})
            if not req['ready'].wait(20):
                raise RuntimeError('Backend did not become ready')
            if req.get('error'):
                raise RuntimeError(req['error'])
            self.send({'type': 'voice_request', 'session_id': req['session'], 'audio': base64.b64encode(Path(audio).read_bytes()).decode()})
            if not req['done'].wait(155):
                raise RuntimeError('Drawing timed out')
            if req.get('error'):
                raise RuntimeError(req['error'])
            with Image.open(io.BytesIO(base64.b64decode(req['content'], validate=True))) as img:
                from print_layout import fit_width
                fit_width(img, trim_white=True).save(target)
            Path(target).with_suffix('.cloud.json').write_text(json.dumps({'message_id': req['message_id']}))
            logging.info('cloud_drawing_ready elapsed=%.2f', time.monotonic()-started)
            return req.get('prompt', '')
        finally:
            try:
                # End the generation session so its timer cannot cancel a child's review.
                self.send({'type': 'voice_stop', 'mode': 'recorded', 'quality': 'low', 'session_id': req['session']})
            except Exception:
                pass
            with self.lock:
                self.request = None

    def send_postcard(self, draft, image):
        ident = draft['id']
        if not self.connected.wait(8):
            raise RuntimeError('PaperDrop backend is unavailable')
        with self.lock:
            existing = self.deliveries.get(ident)
            if existing and existing.get('status') in ('queued','sent','printing','printed','dispatching'):
                return existing
            self.deliveries.pop(ident, None)
            self.delivery_event.clear()
        self.send({'type':'postcard_send','id':ident,'house':draft['house'],
                   'recipient':draft['recipient'],'image':base64.b64encode(Path(image).read_bytes()).decode()})
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            self.delivery_event.wait(1)
            with self.lock:
                result=self.deliveries.get(ident)
                if result:
                    if result.get('error'):
                        raise RuntimeError(result['error'])
                    return result
                self.delivery_event.clear()
        raise RuntimeError('Delivery not confirmed. Retry checks this same postcard; it does not create a duplicate.')

    def mail_receipt(self, ident, status, notice=False):
        from cousin_mail import atomic_write
        value = {'type': 'printer_notice_receipt' if notice else 'mail_receipt', 'id': ident, 'status': status}
        path = self.ack_dir / (ident + '.json')
        atomic_write(path, json.dumps(value).encode())
        try:
            self.send(value)
            path.unlink(missing_ok=True)
        except Exception:
            pass

    def send_mail(self, draft):
        ident = draft['id']
        if not self.connected.wait(8):
            raise RuntimeError('PaperDrop backend is unavailable. Retry when online.')
        with self.lock:
            existing = self.deliveries.get(ident)
            if existing and not existing.get('error') and existing.get('status') not in ('not_found',):
                return existing
            self.deliveries.pop(ident, None)
            self.delivery_event.clear()
        path = draft['audio' if draft['kind'] == 'voice' else 'image']
        self.send({'type': 'mail_send', 'id': ident, 'house': draft['house'], 'sender': draft['sender'],
                   'recipient': draft['recipient'], 'kind': draft['kind'],
                   'media': base64.b64encode(Path(path).read_bytes()).decode()})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            self.delivery_event.wait(1)
            with self.lock:
                result = self.deliveries.get(ident)
                if result:
                    if result.get('error'):
                        raise RuntimeError(result['error'])
                    return result
                self.delivery_event.clear()
        raise RuntimeError('Delivery not confirmed. Retry reuses this message ID.')

    def close(self):
        self.stop.set()
        if self.ws:
            self.ws.close()
