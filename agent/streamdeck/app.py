#!/usr/bin/env python3
"""Connected Stream Deck + loopback-only companion for the Cousins bench."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import signal
import threading
import time
from urllib.parse import urlparse


from controller import Controller
from media import Media
from render import Renderer, png
from store import Mailbox

ROOT = Path(__file__).resolve().parent


class Bench:
    def __init__(self, root, no_device=False, pi=False):
        self.root = Path(root)
        self.family = json.loads((ROOT/'family.json').read_text())
        station = Path('/etc/paperdrop/station')
        if pi and station.exists():
            value = station.read_text().strip()
            if value not in {h['id'] for h in self.family['houses']}:
                raise ValueError('Unknown house configuration')
            self.family['station'] = value
        self.mailbox = Mailbox(self.root)
        self.pi = pi
        self.bridge_seen = 0
        self.bridge_connected = False
        if pi:
            from pi_media import PiMedia
            self.media = PiMedia(self.root)
        else:
            self.media = Media(self.root)
        if pi:
            self.media.attach_mailbox(self.mailbox, self.family)
        self.controller = Controller(self.family,self.mailbox,self.media)
        self.renderer = Renderer(self.family)
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.device = None
        self.no_device = no_device
        self.snapshot = None
        self.images = []
        self.frame = 0
        self.last_usb = [None]*6
        self.last_saved = 0
        self.refresh()

    def refresh(self):
        snapshot = self.controller.snapshot()
        keys = self.renderer.keys(snapshot)
        with self.lock:
            self.snapshot = snapshot
            self.images = [png(key) for key in keys]
            self.frame += 1
            if self.device:
                from StreamDeck.ImageHelpers import PILHelper
                for i,key in enumerate(keys):
                    scaled=PILHelper.create_scaled_key_image(self.device,key)
                    native=PILHelper.to_native_key_format(self.device,scaled)
                    if native!=self.last_usb[i]:
                        self.device.set_key_image(i,native)
                        self.last_usb[i]=native
            if time.monotonic()-self.last_saved>1:
                self.renderer.contact_sheet(keys).save(self.root/'deck-preview.png')
                self.last_saved=time.monotonic()
            state=self.public_state()
            temp=self.root/'state.tmp'
            temp.write_text(json.dumps(state))
            temp.replace(self.root/'state.json')

    def public_state(self):
        with self.lock:
            s=dict(self.snapshot)
            s['has_picture']=bool(s.pop('picture',None))
            s['tiles']=[{k:v for k,v in t.items() if k not in ('image','mosaic')} for t in s['tiles']]
            s['device_connected']=bool(self.device and self.device.connected()) or (self.pi and self.bridge_connected and time.monotonic()-self.bridge_seen<3)
            s['runtime']='pi' if self.pi else 'laptop'
            s['button_transport']='usb' if not self.no_device else 'laptop-bridge'
            s['cloud_connected']=self.media.cloud.connected.is_set() if self.pi else None
            s['frame']=self.frame
            return s

    def bridge_heartbeat(self, connected):
        if not self.no_device:
            return  # A laptop reconnect must never interrupt the Pi USB controller.
        self.bridge_seen = time.monotonic()
        self.bridge_connected = connected
        if not connected:
            self.bridge_lost()

    def bridge_lost(self):
        self.bridge_connected = False
        with self.controller.lock:
            self.controller.down.clear()
            if self.controller.mode in ('arming', 'recording'):
                self.controller.finish_recording(discard=True)

    def run(self):
        self.controller.speak('Choose a house to send a postcard, or tap the pencil to draw and print.')
        previous=None
        while not self.stop.wait(.15):
            try:
                if self.pi and self.no_device and self.bridge_connected and time.monotonic()-self.bridge_seen>3:
                    self.bridge_lost()
                if not self.no_device and not self.device:
                    from StreamDeck.DeviceManager import DeviceManager
                    devices=[d for d in DeviceManager().enumerate() if d.key_count()==6]
                    if devices:
                        d=devices[0]
                        d.open()
                        d.set_brightness(65)
                        d.set_key_callback(lambda _,key,state:self.controller.press(key,state))
                        with self.lock:
                            self.device=d
                            self.last_usb=[None]*6
                        logging.info('CONNECTED %s, six keys',d.deck_type())
                        previous=None
                if self.device and not self.device.connected():
                    raise OSError('USB disconnected')
                snap=self.controller.snapshot()
                marker=(snap['revision'],snap['heading'],snap['hint'],json.dumps(snap['tiles'],sort_keys=True),int(time.monotonic()*5) if self.renderer.animated(snap) else 0)
                if marker!=previous:
                    self.refresh()
                    previous=marker
            except Exception as exc:
                logging.warning('render_or_usb_error type=%s',type(exc).__name__)
                with self.lock:
                    if self.device:
                        try:self.device.close()
                        except Exception:pass
                    self.device=None
                with self.controller.lock:
                    self.controller.down.clear()
                    if self.controller.mode in ('arming','recording'):
                        self.controller.finish_recording(discard=True)
                self.stop.wait(1)
        self.controller.close()
        if self.device:
            self.device.close()


def handler(bench, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):
            pass

        def reply(self,code,body,kind='application/json'):
            if isinstance(body,dict):body=json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            try:self.wfile.write(body)
            except BrokenPipeError:pass

        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')

        def do_GET(self):
            if not self.valid_host():return self.reply(403,{'error':'Local requests only'})
            path=urlparse(self.path).path
            if path=='/':return self.reply(200,(ROOT/'companion.html').read_bytes(),'text/html; charset=utf-8')
            if path=='/state':return self.reply(200,bench.public_state())
            if path=='/frame':
                with bench.lock:
                    return self.reply(200,{'state':bench.public_state(),'keys':[base64.b64encode(im).decode() for im in bench.images]})
            if path=='/picture':
                with bench.lock:p=bench.snapshot.get('picture')
                if p and Path(p).is_file():return self.reply(200,Path(p).read_bytes(),'image/png')
            if path.startswith('/key/') and path.endswith('.png'):
                try:
                    i=int(path[5:-4])
                    if i not in range(6):raise ValueError()
                    with bench.lock:body=bench.images[i]
                    return self.reply(200,body,'image/png')
                except (ValueError,IndexError):pass
            if path=='/icon/Mail.svg':return self.reply(200,(ROOT/'assets/icons/Mail.svg').read_bytes(),'image/svg+xml')
            return self.reply(404,{'error':'Not found'})

        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-PaperDrop-Local')!='1':
                return self.reply(403,{'error':'Local requests only'})
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://localhost:{port}',f'http://127.0.0.1:{port}'):
                return self.reply(403,{'error':'Local requests only'})
            if urlparse(self.path).path!='/action':return self.reply(404,{'error':'Not found'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<1000:raise ValueError('Invalid request')
                body=json.loads(self.rfile.read(length))
                if 'bridge_connected' in body:
                    if type(body['bridge_connected']) is not bool:raise ValueError()
                    bench.bridge_heartbeat(body['bridge_connected'])
                elif body.get('demo')=='reset':
                    with bench.controller.lock:
                        if bench.controller.mode not in ('home','personal'):
                            raise ValueError('Return Home before resetting examples')
                        from demo import reset_examples
                        reset_examples(bench.mailbox)
                        bench.controller.switch_station('portugal')
                elif 'deliver_saved' in body:bench.controller.deliver_saved(body['deliver_saved'])
                elif 'station' in body:bench.controller.switch_station(body['station'])
                else:
                    if type(body.get('key')) is not int or type(body.get('pressed')) is not bool:raise ValueError('Invalid key event')
                    bench.controller.press(body['key'],body['pressed'])
                return self.reply(200,{'ok':True})
            except (ValueError,KeyError,TypeError):return self.reply(400,{'error':'Finish or delete this postcard before switching houses.'})
    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-dir',default=str(ROOT/'.state'))
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--no-device',action='store_true')
    parser.add_argument('--pi',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    bench=Bench(args.state_dir,args.no_device,args.pi)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(bench,args.port))
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:bench.stop.set())
    threading.Thread(target=server.serve_forever,daemon=True).start()
    logging.info('READY local-bench companion port=%d',args.port)
    try:bench.run()
    finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
