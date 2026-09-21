#!/usr/bin/python3
"""Temporary local Wi-Fi setup; no account credentials or shell input accepted."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import json
from pathlib import Path
import secrets
import subprocess
import threading
import time
from urllib.parse import parse_qs

TOKEN=secrets.token_urlsafe(24)
ADDRESS='10.42.0.1'

def run(*args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=35, **kwargs)

def connected():
    r=run('nmcli','-t','-f','TYPE,STATE,CONNECTION','device')
    return any(':connected:' in line and not line.endswith(':PaperDrop-Setup') and line.split(':')[0] in ('wifi','ethernet') for line in r.stdout.splitlines())

class Setup(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        code=Path('/etc/paperdrop/device-id')
        device=code.read_text().strip() if code.exists() else 'Preparing your device'
        page=f'''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Set up PaperDrop</title><body style="font:18px system-ui;max-width:420px;margin:40px auto;padding:20px"><h1>Connect PaperDrop</h1><p>Enter your home Wi-Fi details. Once connected, PaperDrop updates itself automatically.</p><form method="post"><input type="hidden" name="token" value="{TOKEN}"><label>Wi-Fi name<input name="ssid" maxlength="32" required style="display:block;margin:10px 0"></label><label>Wi-Fi password<input name="password" type="password" maxlength="64" style="display:block;margin:10px 0"></label><label>Country code (US, DE, PT…)<input name="country" value="US" maxlength="2" required style="display:block;margin:10px 0"></label><button>Connect PaperDrop</button></form><p>Device code: {html.escape(device)}</p></body></html>'''
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(page.encode())
    def do_POST(self):
        size=int(self.headers.get('Content-Length','0'))
        if not 0 < size <= 4096:
            self.send_error(400);return
        data={k:v[0] for k,v in parse_qs(self.rfile.read(size).decode(),keep_blank_values=True).items()}
        if data.get('token')!=TOKEN or not 1<=len(data.get('ssid','').encode())<=32:
            self.send_error(400);return
        country=data.get('country','').upper()
        if len(country)!=2 or not country.isascii() or not country.isalpha():
            self.send_error(400);return
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
        self.wfile.write(b'<h1>Connecting...</h1><p>The setup network will disappear. If the password is incorrect, it will return so you can try again.</p>')
        def connect():
            time.sleep(2)
            run('raspi-config','nonint','do_wifi_country',country)
            run('nmcli','connection','down','PaperDrop-Setup')
            result=run('nmcli','device','wifi','connect',data['ssid'],'password',data.get('password',''),'ifname','wlan0')
            if result.returncode:
                run('nmcli','connection','up','PaperDrop-Setup')
            else:
                run('systemctl','restart','paperdrop-enroll.service')
                run('systemctl','start','paperdrop-runtime.service','paperdrop-update.service')
        threading.Thread(target=connect,daemon=True).start()

if __name__=='__main__':
    time.sleep(30)
    if connected():
        raise SystemExit(0)
    run('rfkill','unblock','wifi')
    # Set an initial regulatory domain so an uncustomized factory image can start its AP.
    run('raspi-config','nonint','do_wifi_country','US')
    # Short-range, password-protected setup AP; credentials are only stored by NM.
    result=run('nmcli','device','wifi','hotspot','ifname','wlan0','con-name','PaperDrop-Setup','ssid','PaperDrop-Setup','password','paperdrop-setup')
    if result.returncode:
        run('nmcli','connection','up','PaperDrop-Setup')
    run('nmcli','connection','modify','PaperDrop-Setup','connection.autoconnect','no')
    HTTPServer((ADDRESS,8080),Setup).serve_forever()
