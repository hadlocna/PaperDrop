"""
WiFi Setup Server for PaperDrop
Based on balena wifi-connect pattern:
1. Start AP-only mode
2. User enters credentials via captive portal
3. Stop AP, try to connect
4. If fails, restart AP
5. If succeeds, device is online

This is simpler and more reliable than AP+STA concurrent mode.
"""
import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, Awaitable, Optional

from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from uvicorn import Config as UvicornConfig, Server

logger = logging.getLogger("paperdrop.wifi")

# Configuration
PORTAL_SSID = os.environ.get("PORTAL_SSID", "PaperDrop_Setup")
PORTAL_GATEWAY = os.environ.get("PORTAL_GATEWAY", "192.168.4.1")
PORTAL_INTERFACE = os.environ.get("PORTAL_INTERFACE", "wlan0")
SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "wifi_setup.sh"

# ─────────────────────────────────────────────────────────────────────
# HTML TEMPLATES
# ─────────────────────────────────────────────────────────────────────

STYLE = """
<style>
    :root {
        --primary: #FF6B6B;
        --secondary: #4ECDC4;
        --dark: #2D3436;
        --light: #F7FFF7;
        --surface: #FFFFFF;
        --text: #2D3436;
        --text-muted: #636E72;
    }
    * { box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: var(--light);
        margin: 0;
        padding: 20px;
        min-height: 100vh;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .container { width: 100%; max-width: 380px; }
    .card {
        background: var(--surface);
        border-radius: 24px;
        padding: 32px 24px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.08);
        text-align: center;
    }
    .logo {
        font-weight: 800;
        font-size: 24px;
        margin-bottom: 16px;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    h1 { font-size: 20px; font-weight: 600; margin: 0 0 8px; color: var(--dark); }
    p { color: var(--text-muted); font-size: 14px; margin: 0 0 24px; }
    .form-group { text-align: left; margin-bottom: 16px; }
    label {
        display: block; font-size: 12px; font-weight: 600;
        color: var(--text-muted); margin-bottom: 6px;
        text-transform: uppercase; letter-spacing: 0.5px;
    }
    input, select {
        width: 100%; padding: 14px 16px;
        border: 2px solid #EEE; border-radius: 12px;
        font-size: 16px; background: #FAFAFA; outline: none;
    }
    input:focus, select:focus { border-color: var(--primary); background: white; }
    button {
        width: 100%; padding: 16px;
        background: var(--primary); color: white;
        border: none; border-radius: 14px;
        font-size: 16px; font-weight: 600;
        cursor: pointer; margin-top: 8px;
        box-shadow: 0 4px 12px rgba(255,107,107,0.3);
    }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .networks { margin-top: 20px; border-top: 1px solid #EEE; padding-top: 20px; }
    .network-item {
        display: flex; justify-content: space-between; align-items: center;
        padding: 12px; border-radius: 10px; cursor: pointer;
        transition: background 0.1s;
    }
    .network-item:hover { background: #F5F5F5; }
    .network-name { font-weight: 500; }
    .network-signal { font-size: 12px; color: var(--text-muted); }
    .status-icon { font-size: 48px; margin: 20px 0; }
    .spinner { animation: spin 1s linear infinite; display: inline-block; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .code {
        font-family: monospace; font-size: 28px; letter-spacing: 3px;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        color: white; padding: 12px 20px; border-radius: 12px;
        display: inline-block; margin: 16px 0;
    }
    .success-text { color: var(--secondary); }
    .error-text { color: var(--primary); }
    .error-box { background: #FEE; border: 1px solid #FCC; color: #C00; padding: 12px; border-radius: 10px; margin-bottom: 16px; font-size: 14px; }
    a.btn {
        display: inline-block; padding: 16px 32px; text-decoration: none;
        background: var(--primary); color: white; border-radius: 14px;
        font-weight: 600; margin-top: 16px;
    }
    .hidden { display: none !important; }
</style>
"""


class WiFiSetupServer:
    """
    Captive portal server for WiFi setup.
    Uses the simpler AP -> Connect -> AP fallback pattern.
    """
    
    def __init__(self, config, on_connected_callback: Callable[[], Awaitable[None]]):
        self.config = config
        self.on_connected = on_connected_callback
        self.server: Optional[Server] = None
        self.is_running = False
        self.connection_state = {"state": "IDLE", "status": "Ready", "ssid": ""}
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
            if len(password) < 8:
                networks = await self._scan_networks()
                return self._render_home(networks, error="Password must be at least 8 characters")
            
            # Save credentials
            self.config.save_wifi_credentials(ssid, password)
            self.connection_state = {"state": "CONNECTING", "status": f"Connecting to {ssid}...", "ssid": ssid}
            
            # Start connection in background
            background_tasks.add_task(self._try_connect, ssid, password)
            
            # Return connecting page
            return self._render_connecting(ssid)
        
        # Captive portal detection endpoints
        @self.app.get("/generate_204")
        @self.app.get("/gen_204")
        async def android_check():
            return RedirectResponse("/")
        
        @self.app.get("/hotspot-detect.html")
        @self.app.get("/library/test/success.html")
        async def apple_check():
            return RedirectResponse("/")
        
        @self.app.get("/connecttest.txt")
        @self.app.get("/ncsi.txt")
        async def windows_check():
            return RedirectResponse("/")
        
        @self.app.get("/{path:path}")
        async def catch_all(path: str):
            return RedirectResponse("/")
    
    async def _try_connect(self, ssid: str, password: str):
        """Try to connect to WiFi. If fails, restart AP."""
        try:
            logger.info(f"Attempting to connect to {ssid}...")
            
            # Stop AP mode
            await self._stop_ap()
            await asyncio.sleep(2)
            
            # Try to connect using nmcli
            success = await self._connect_wifi(ssid, password)
            
            if success:
                logger.info(f"Successfully connected to {ssid}!")
                self.connection_state = {"state": "CONNECTED", "status": "Connected!", "ssid": ssid}
                
                # Notify the agent
                await self.on_connected()
            else:
                logger.error(f"Failed to connect to {ssid}, restarting AP...")
                self.connection_state = {"state": "FAILED", "status": "Connection failed. Please try again.", "ssid": ssid}
                
                # Restart AP for retry
                await asyncio.sleep(2)
                await self._start_ap()
                
        except Exception as e:
            logger.exception(f"Error during connection attempt: {e}")
            self.connection_state = {"state": "FAILED", "status": str(e), "ssid": ssid}
            await self._start_ap()
    
    async def _connect_wifi(self, ssid: str, password: str) -> bool:
        """Connect to WiFi using NetworkManager."""
        try:
            # Delete existing connection if any
            proc = await asyncio.create_subprocess_exec(
                "nmcli", "connection", "delete", ssid,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
            
            # Try to connect
            proc = await asyncio.create_subprocess_exec(
                "nmcli", "device", "wifi", "connect", ssid, "password", password,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                logger.error(f"nmcli failed: {stderr.decode()}")
                return False
            
            # Wait for IP
            for _ in range(30):
                await asyncio.sleep(1)
                proc = await asyncio.create_subprocess_shell(
                    f"ip -4 addr show {PORTAL_INTERFACE} | grep inet",
                    stdout=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                if b"inet" in stdout and b"192.168.4" not in stdout:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    async def _start_ap(self):
        """Start the access point using NetworkManager Native Hotspot."""
        if os.environ.get("PAPERDROP_ENV") == "development":
            logger.info("[DEV] Skipping AP start")
            return
        
        logger.info("Starting AP via NetworkManager...")
        try:
            # 1. Ensure interface is managed by NM
            subprocess.run(["nmcli", "device", "set", PORTAL_INTERFACE, "managed", "yes"], capture_output=True)
            
            # 2. Unblock WiFi (Just in case)
            subprocess.run(["rfkill", "unblock", "wifi"], capture_output=True)
            
            # 3. Clean up old profile
            subprocess.run(["nmcli", "title", "PaperDrop_AP", "delete", "PaperDrop_AP"], capture_output=True) # Try by name
            subprocess.run(["nmcli", "con", "delete", "PaperDrop_AP"], capture_output=True)

            # 4. Create AP Profile
            # ipv4.method manual means NM sets the IP, but we handle DHCP (via dnsmasq)
            cmd = [
                "nmcli", "con", "add", "type", "wifi", "ifname", PORTAL_INTERFACE,
                "con-name", "PaperDrop_AP", "autoconnect", "yes",
                "ssid", PORTAL_SSID, "mode", "ap",
                "ipv4.method", "manual", "ipv4.addresses", f"{PORTAL_GATEWAY}/24",
                "wifi-sec.key-mgmt", "none"
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # 5. Bring UP the AP
            logger.info("Activating AP Profile...")
            subprocess.run(["nmcli", "con", "up", "PaperDrop_AP"], check=True)
            
            # 6. Start dnsmasq (Manual mode for Captive Portal DNS spoofing)
            # Kill existing
            subprocess.run(["killall", "dnsmasq"], capture_output=True)
            await asyncio.sleep(1)
            
            # Config for dnsmasq
            dnsmasq_conf = f"""interface={PORTAL_INTERFACE}
bind-interfaces
dhcp-range=192.168.4.2,192.168.4.254,255.255.255.0,24h
address=/#/{PORTAL_GATEWAY}
keep-in-foreground
"""
            Path("/tmp/paperdrop_dnsmasq.conf").write_text(dnsmasq_conf)
            
            # Start dnsmasq
            logger.info("Starting dnsmasq...")
            subprocess.Popen(["dnsmasq", "-C", "/tmp/paperdrop_dnsmasq.conf"])
            
            # 7. Iptables Redirect (Port 80 -> 8080)
            subprocess.run([
                "iptables", "-t", "nat", "-A", "PREROUTING",
                "-i", PORTAL_INTERFACE, "-p", "tcp", "--dport", "80",
                "-j", "REDIRECT", "--to-port", "8080"
            ], capture_output=True)
            
            logger.info(f"Access Point started successfully: {PORTAL_SSID}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start AP (Command Error): {e}")
        except Exception as e:
            logger.error(f"Failed to start AP: {e}")
    
    async def _stop_ap(self):
        """Stop the access point."""
        if os.environ.get("PAPERDROP_ENV") == "development":
            return
        
        logger.info("Stopping Access Point...")
        try:
            # Clean up dnsmasq
            subprocess.run(["killall", "dnsmasq"], capture_output=True)
            
            # Clean up iptables
            subprocess.run([
                "iptables", "-t", "nat", "-D", "PREROUTING",
                "-i", PORTAL_INTERFACE, "-p", "tcp", "--dport", "80",
                "-j", "REDIRECT", "--to-port", "8080"
            ], capture_output=True)
            
            # Bring down AP connection
            subprocess.run(["nmcli", "con", "down", "PaperDrop_AP"], capture_output=True)
            
            # Delete profile to clean up
            subprocess.run(["nmcli", "con", "delete", "PaperDrop_AP"], capture_output=True)
            
        except Exception as e:
            logger.error(f"Error stopping AP: {e}")
    
    async def _scan_networks(self) -> list:
        """Scan for available WiFi networks."""
        if os.environ.get("PAPERDROP_ENV") == "development":
            return [
                {"ssid": "Home-WiFi", "signal": "Strong"},
                {"ssid": "Neighbor-5G", "signal": "Medium"},
            ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            networks = []
            seen = set()
            for line in stdout.decode().strip().split("\n"):
                if ":" in line:
                    parts = line.split(":")
                    ssid = parts[0]
                    signal = int(parts[1]) if parts[1].isdigit() else 0
                    if ssid and ssid not in seen and ssid != PORTAL_SSID:
                        seen.add(ssid)
                        strength = "Strong" if signal > 70 else "Medium" if signal > 40 else "Weak"
                        networks.append({"ssid": ssid, "signal": strength})
            
            return sorted(networks, key=lambda x: x["signal"], reverse=True)[:10]
        except Exception as e:
            logger.error(f"Scan error: {e}")
            return []
    
    def _get_device_code(self) -> str:
        """Get the device code."""
        try:
            with open("/etc/paperdrop/device.json", "r") as f:
                return json.load(f).get("device_code", "UNKNOWN")
        except:
            return "UNKNOWN"
    
    def _render_home(self, networks: list, error: str = None) -> str:
        """Render the home page."""
        network_html = ""
        for net in networks:
            network_html += f'''
            <div class="network-item" onclick="selectNetwork('{net["ssid"]}')">
                <span class="network-name">{net["ssid"]}</span>
                <span class="network-signal">{net["signal"]}</span>
            </div>
            '''
        
        error_html = f'<div class="error-box">{error}</div>' if error else ""
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>PaperDrop Setup</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            {STYLE}
            <script>
                function selectNetwork(ssid) {{
                    document.getElementById('ssid').value = ssid;
                    document.getElementById('password').focus();
                }}
            </script>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="logo">PaperDrop</div>
                    <h1>WiFi Setup</h1>
                    <p>Select your WiFi network to get started</p>
                    
                    {error_html}
                    
                    <form method="POST" action="/connect">
                        <div class="form-group">
                            <label>Network Name</label>
                            <input type="text" id="ssid" name="ssid" required placeholder="Select below or type">
                        </div>
                        <div class="form-group">
                            <label>Password</label>
                            <input type="password" id="password" name="password" required placeholder="Enter WiFi password">
                        </div>
                        <button type="submit">Connect</button>
                    </form>
                    
                    <div class="networks">
                        <label style="margin-bottom:12px;">Available Networks</label>
                        {network_html if network_html else '<p style="text-align:center;">No networks found. Try refreshing.</p>'}
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _render_connecting(self, ssid: str) -> str:
        """Render the connecting page."""
        device_code = self._get_device_code()
        dashboard_url = f"https://paperdrop-frontend.onrender.com/claim?code={device_code}"
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Connecting - PaperDrop</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            {STYLE}
            <script>
                function checkStatus() {{
                    fetch('/status')
                        .then(r => r.json())
                        .then(data => {{
                            document.getElementById('status-msg').innerText = data.status;
                            if (data.state === 'CONNECTED') {{
                                document.getElementById('connecting-view').classList.add('hidden');
                                document.getElementById('success-view').classList.remove('hidden');
                            }} else if (data.state === 'FAILED') {{
                                document.getElementById('connecting-view').classList.add('hidden');
                                document.getElementById('error-view').classList.remove('hidden');
                                document.getElementById('error-msg').innerText = data.status;
                            }} else {{
                                setTimeout(checkStatus, 1500);
                            }}
                        }})
                        .catch(() => setTimeout(checkStatus, 2000));
                }}
                window.onload = checkStatus;
            </script>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="logo">PaperDrop</div>
                    
                    <div id="connecting-view">
                        <h1>Connecting to WiFi</h1>
                        <p id="status-msg">Connecting to {ssid}...</p>
                        <div class="status-icon"><span class="spinner">🔄</span></div>
                        <p style="font-size:12px;">This may take up to 30 seconds.<br>The setup network will disconnect.</p>
                    </div>
                    
                    <div id="success-view" class="hidden">
                        <h1 class="success-text">Connected!</h1>
                        <div class="status-icon">✅</div>
                        <p>Your PaperDrop is now online.</p>
                        <p style="font-size:12px; margin-bottom:8px;">YOUR DEVICE CODE</p>
                        <div class="code">{device_code}</div>
                        <p style="font-size:13px;">Use this code to add the device to your account</p>
                        <a href="{dashboard_url}" class="btn">Add to My Account</a>
                    </div>
                    
                    <div id="error-view" class="hidden">
                        <h1 class="error-text">Connection Failed</h1>
                        <div class="status-icon">❌</div>
                        <p id="error-msg">Could not connect to WiFi</p>
                        <p style="font-size:12px;">The setup network will restart. Please try again.</p>
                        <a href="/" class="btn" style="background:#636E72;">Try Again</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    async def start(self):
        """Start the captive portal."""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Starting WiFi Setup Portal...")
        
        # Start AP
        await self._start_ap()
        
        # Start web server
        config = UvicornConfig(self.app, host="0.0.0.0", port=8080, log_level="warning")
        self.server = Server(config)
        asyncio.create_task(self.server.serve())
        
        logger.info("WiFi Setup Portal running on http://0.0.0.0:8080")
    
    async def stop(self):
        """Stop the captive portal."""
        logger.info("Stopping WiFi Setup Portal...")
        if self.server:
            self.server.should_exit = True
        await self._stop_ap()
        self.is_running = False
