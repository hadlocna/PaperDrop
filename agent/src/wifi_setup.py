"""
Resilient WiFi Setup for PaperDrop
Implements the 'Old School' stack: hostapd + dnsmasq + wpa_supplicant
"""
import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Awaitable, Optional

from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from uvicorn import Config as UvicornConfig, Server

logger = logging.getLogger("paperdrop.wifi")

# Configuration
PORTAL_SSID = "PaperDrop_Setup"
PORTAL_GATEWAY = "192.168.4.1"
INTERFACE = "wlan0"

# ─────────────────────────────────────────────────────────────────────
# HTML TEMPLATES (Simplified for reliability)
# ─────────────────────────────────────────────────────────────────────

STYLE = """
<style>
    body { font-family: sans-serif; padding: 20px; max-width: 400px; margin: 0 auto; background: #f4f4f4; }
    .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    input { width: 100%; padding: 10px; margin: 5px 0 15px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 4px; }
    button { width: 100%; padding: 12px; background: #FF6B6B; color: white; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; }
    .network { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; }
    .network:hover { background: #f9f9f9; }
    .error { color: red; background: #fee; padding: 10px; border-radius: 4px; margin-bottom: 10px; }
</style>
"""

class WiFiSetupServer:
    def __init__(self, config, on_connected_callback: Callable[[], Awaitable[None]]):
        self.config = config
        self.on_connected = on_connected_callback
        self.server: Optional[Server] = None
        self.is_running = False
        self.connection_state = {"state": "IDLE", "status": "Ready"}
        self.app = FastAPI()
        self._setup_routes()
        
    def _setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def home():
            networks = await self._scan_networks()
            return self._render_home(networks)
            
        @self.app.get("/status")
        async def status():
            return JSONResponse(self.connection_state)
            
        @self.app.post("/connect", response_class=HTMLResponse)
        async def connect(
            ssid: str = Form(...),
            password: str = Form(...),
            background_tasks: BackgroundTasks = None
        ):
            self.connection_state = {"state": "CONNECTING", "status": f"Connecting to {ssid}..."}
            background_tasks.add_task(self._attempt_connection, ssid, password)
            return self._render_connecting(ssid)

        # Captive Portal Redirects
        @self.app.get("/generate_204")
        @self.app.get("/gen_204")
        @self.app.get("/hotspot-detect.html")
        async def captive_portal():
            return RedirectResponse("/")
            
        @self.app.get("/{path:path}")
        async def catch_all(path: str):
            return RedirectResponse("/")

    async def start(self):
        """Start AP Mode"""
        if self.is_running: return
        self.is_running = True
        
        logger.info("Starting WiFi Setup (AP Mode)...")
        await self._enable_ap_mode()
        
        # Start Web Server
        config = UvicornConfig(self.app, host="0.0.0.0", port=80, log_level="warning")
        self.server = Server(config)
        asyncio.create_task(self.server.serve())

    async def stop(self):
        """Stop AP Mode"""
        if self.server:
            self.server.should_exit = True
        self.is_running = False
        # We don't necessarily stop AP here, usually handled by connection success

    async def _enable_ap_mode(self):
        """Configure and start hostapd/dnsmasq"""
        try:
            # 1. Stop Client Services
            subprocess.run(["systemctl", "stop", "wpa_supplicant"], check=False)
            subprocess.run(["systemctl", "stop", "dhcpcd"], check=False)
            subprocess.run(["killall", "wpa_supplicant"], check=False)
            subprocess.run(["killall", "dhcpcd"], check=False)
            
            # 2. Configure Interface IP
            subprocess.run(["ip", "link", "set", INTERFACE, "down"], check=True)
            subprocess.run(["ip", "addr", "flush", "dev", INTERFACE], check=True)
            subprocess.run(["ip", "addr", "add", f"{PORTAL_GATEWAY}/24", "dev", INTERFACE], check=True)
            subprocess.run(["ip", "link", "set", INTERFACE, "up"], check=True)
            
            # 3. Configure dnsmasq
            dnsmasq_conf = f"""interface={INTERFACE}
bind-interfaces
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/#/{PORTAL_GATEWAY}
"""
            Path("/tmp/dnsmasq.conf").write_text(dnsmasq_conf)
            subprocess.run(["killall", "dnsmasq"], check=False)
            subprocess.Popen(["dnsmasq", "-C", "/tmp/dnsmasq.conf"])
            
            # 4. Configure hostapd
            hostapd_conf = f"""interface={INTERFACE}
driver=nl80211
ssid={PORTAL_SSID}
hw_mode=g
channel=7
auth_algs=1
wpa=0
"""
            Path("/tmp/hostapd.conf").write_text(hostapd_conf)
            subprocess.run(["killall", "hostapd"], check=False)
            subprocess.Popen(["hostapd", "/tmp/hostapd.conf"])
            
            logger.info("AP Mode Enabled")
            
        except Exception as e:
            logger.error(f"Failed to enable AP: {e}")

    async def _attempt_connection(self, ssid: str, password: str):
        """Stop AP, Try Connect, If Fail -> Restart AP"""
        logger.info(f"Attempting connection to {ssid}...")
        
        # 1. Stop AP
        subprocess.run(["killall", "hostapd"], check=False)
        subprocess.run(["killall", "dnsmasq"], check=False)
        subprocess.run(["ip", "addr", "flush", "dev", INTERFACE], check=False)
        
        # 2. Write wpa_supplicant.conf
        wpa_conf = f"""ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
"""
        Path("/etc/wpa_supplicant/wpa_supplicant.conf").write_text(wpa_conf)
        
        # 3. Start Client Services
        subprocess.run(["systemctl", "start", "wpa_supplicant"], check=False)
        # Or run manually if service is masked
        # subprocess.Popen(["wpa_supplicant", "-B", "-i", INTERFACE, "-c", "/etc/wpa_supplicant/wpa_supplicant.conf"])
        
        subprocess.run(["dhcpcd", "-n", INTERFACE], check=False)
        
        # 4. Poll for Connection
        success = False
        for _ in range(20): # Wait up to 20s
            await asyncio.sleep(1)
            # Check for IP
            res = subprocess.run(f"ip -4 addr show {INTERFACE} | grep inet", shell=True, capture_output=True)
            if res.returncode == 0:
                # Check Internet
                ping = subprocess.run("ping -c 1 -W 2 8.8.8.8", shell=True)
                if ping.returncode == 0:
                    success = True
                    break
        
        if success:
            logger.info("Connection Successful!")
            self.connection_state = {"state": "CONNECTED", "status": "Connected!"}
            self.config.save_wifi_credentials(ssid, password)
            await self.on_connected()
        else:
            logger.error("Connection Failed. Reverting to AP...")
            self.connection_state = {"state": "FAILED", "status": "Connection Failed"}
            await self._enable_ap_mode()

    async def _scan_networks(self):
        """Scan using iwlist (since we are in AP mode, might need to pause hostapd?)"""
        # Scanning while hostapd is running is tricky on some chips.
        # For now, return empty or mock if in dev.
        # On RPi, 'iw dev wlan0 scan' might work if AP is up.
        try:
            cmd = f"iw dev {INTERFACE} scan | grep SSID"
            res = subprocess.run(cmd, shell=True, capture_output=True)
            networks = []
            seen = set()
            for line in res.stdout.decode().split('\n'):
                if "SSID: " in line:
                    ssid = line.split("SSID: ")[1].strip()
                    if ssid and ssid != PORTAL_SSID and ssid not in seen:
                        networks.append({"ssid": ssid})
                        seen.add(ssid)
            return networks
        except:
            return []

    def _render_home(self, networks):
        net_html = "".join([f'<div class="network" onclick="document.getElementById(\'ssid\').value=\'{n["ssid"]}\'">{n["ssid"]}</div>' for n in networks])
        return f"""<!DOCTYPE html><html><head><title>PaperDrop</title><meta name="viewport" content="width=device-width,initial-scale=1">{STYLE}</head>
<body><div class="card">
<h2>WiFi Setup</h2>
<form action="/connect" method="post">
<label>Network</label><input id="ssid" name="ssid" placeholder="SSID" required>
<label>Password</label><input type="password" name="password" placeholder="Password" required>
<button type="submit">Connect</button>
</form>
<h3>Available Networks</h3>
{net_html}
</div></body></html>"""

    def _render_connecting(self, ssid):
        return f"""<!DOCTYPE html><html><head><title>Connecting...</title><meta http-equiv="refresh" content="5;url=/status"><meta name="viewport" content="width=device-width,initial-scale=1">{STYLE}</head>
<body><div class="card"><h2>Connecting to {ssid}...</h2><p>Please wait. If successful, this page will stop loading.</p></div></body></html>"""
