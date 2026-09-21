#!/usr/bin/env python3
"""Laptop USB/display bridge only. All application and media work stays on the Pi."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import logging
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper

REMOTE_PORT = 18766
BASE = f'http://127.0.0.1:{REMOTE_PORT}'


def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Host': '127.0.0.1:8766', 'X-PaperDrop-Local': '1', 'Content-Type': 'application/json'}
    with urlopen(Request(BASE+path, data=data, headers=headers), timeout=2) as response:
        return response.read(), response.headers.get('Content-Type', 'application/json')


class Bridge:
    def __init__(self, host):
        self.host = host
        self.stop = threading.Event()
        self.events = queue.Queue(maxsize=100)
        self.device = None
        self.tunnel = None
        self.online = False
        self.last = [None]*6
        self.epoch = 0
        self.usb_lock = threading.RLock()

    def action(self, key, pressed):
        if self.online:
            try:
                self.events.put_nowait((self.epoch, {'key':key, 'pressed':bool(pressed)}))
            except queue.Full:
                self.online = False
                self.epoch += 1

    def actions(self):
        while not self.stop.is_set():
            try:
                epoch, event = self.events.get(timeout=.5)
            except queue.Empty:
                continue
            if epoch != self.epoch or not self.online:
                continue
            try:
                request('/action', event)
            except Exception:
                # Never replay an ambiguous key press after a network failure.
                self.online = False
                self.epoch += 1
                try:
                    request('/action', {'bridge_connected':False})
                except Exception:
                    pass

    def paint(self, images):
        with self.usb_lock:
            if not self.device:
                return
            for i, im in enumerate(images):
                native = PILHelper.to_native_key_format(self.device, PILHelper.create_scaled_key_image(self.device, im))
                if native != self.last[i]:
                    self.device.set_key_image(i, native)
                    self.last[i] = native

    def offline(self):
        im = Image.new('RGB',(240,240),'#faf5e9')
        draw = ImageDraw.Draw(im)
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf',28)
        draw.multiline_text((20,75),'Connecting\nto PaperDrop',font=font,fill='#373448',spacing=15)
        self.paint([im]*6)

    def run(self):
        threading.Thread(target=self.actions,daemon=True).start()
        while not self.stop.wait(.2):
            try:
                if not self.tunnel or self.tunnel.poll() is not None:
                    self.online=False
                    self.epoch+=1
                    self.tunnel=subprocess.Popen(['ssh','-N','-T','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes',
                        '-o','ConnectTimeout=5','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',
                        '-L',f'127.0.0.1:{REMOTE_PORT}:127.0.0.1:8766',self.host],
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                if not self.device:
                    decks=[d for d in DeviceManager().enumerate() if d.key_count()==6]
                    if decks:
                        with self.usb_lock:
                            self.device=decks[0]
                            self.device.open()
                            self.device.set_brightness(65)
                            self.device.set_key_callback(lambda _,key,state:self.action(key,state))
                            self.last=[None]*6
                        logging.info('Stream Deck connected; Pi owns application')
                if self.device and not self.device.connected():
                    with self.usb_lock:
                        self.device.close()
                        self.device=None
                    self.epoch+=1
                request('/action',{'bridge_connected':bool(self.device)})
                data,_=request('/frame')
                frame=json.loads(data)
                images=[Image.open(io.BytesIO(base64.b64decode(raw))).convert('RGB') for raw in frame['keys']]
                self.paint(images)
                self.online=True
            except Exception as exc:
                if self.online:
                    logging.warning('Pi bridge unavailable type=%s',type(exc).__name__)
                self.online=False
                self.epoch+=1
                try:self.offline()
                except Exception:
                    with self.usb_lock:
                        if self.device:
                            try:self.device.close()
                            except Exception:pass
                        self.device=None
                self.stop.wait(1)
        try:request('/action',{'bridge_connected':False})
        except Exception:pass
        if self.device:self.device.close()
        if self.tunnel:
            self.tunnel.terminate()
            try:self.tunnel.wait(timeout=5)
            except subprocess.TimeoutExpired:self.tunnel.kill()


def handler(port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def proxy(self, post=False):
            allowed=(f'127.0.0.1:{port}',f'localhost:{port}')
            if self.headers.get('Host') not in allowed:
                return self.send_error(403)
            origin=self.headers.get('Origin')
            if origin and origin not in tuple('http://'+h for h in allowed):
                return self.send_error(403)
            path=urlparse(self.path).path
            if path not in ['/','/state','/picture','/icon/Mail.svg']+[f'/key/{i}.png' for i in range(6)]+(['/action'] if post else []):
                return self.send_error(404)
            body=None
            if post:
                if path!='/action' or self.headers.get('X-PaperDrop-Local')!='1':return self.send_error(403)
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<1000:raise ValueError()
                    body=json.loads(self.rfile.read(length))
                    if 'bridge_connected' in body:raise ValueError()
                except (ValueError,TypeError):return self.send_error(400)
            try:
                result,kind=request(self.path,body)
                self.send_response(200)
                self.send_header('Content-Type',kind)
                self.send_header('Content-Length',str(len(result)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(result)
            except HTTPError as exc:self.send_error(exc.code)
            except Exception:self.send_error(503,'Pi unavailable')
        def do_GET(self):self.proxy()
        def do_POST(self):self.proxy(True)
    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='pi@paperdrop-fd8f.lan')
    parser.add_argument('--port',type=int,default=8766)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    bridge=Bridge(args.host)
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:bridge.stop.set())
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(args.port))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:bridge.run()
    finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
