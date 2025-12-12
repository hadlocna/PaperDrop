import asyncio
import logging
import os
import subprocess
from typing import Callable, Awaitable
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from uvicorn import Config as UvicornConfig, Server

logger = logging.getLogger("paperdrop.wifi")

# ─────────────────────────────────────────────────────────────────────
# UI STYLING & TEMPLATES
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
        --text-secondary: #636E72;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
        background-color: var(--light);
        color: var(--text);
        margin: 0;
        padding: 0;
        min-height: 100vh;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .container {
        width: 100%;
        max-width: 380px;
        padding: 24px;
        box-sizing: border-box;
    }
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
        margin-bottom: 8px;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block;
    }
    h1 {
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 8px;
        color: var(--dark);
    }
    p {
        color: var(--text-secondary);
        font-size: 14px;
        line-height: 1.5;
        margin-bottom: 24px;
    }
    .form-group {
        text-align: left;
        margin-bottom: 16px;
    }
    label {
        display: block;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    input {
        width: 100%;
        padding: 12px 16px;
        border: 2px solid #EEE;
        border-radius: 12px;
        font-size: 16px;
        transition: all 0.2s;
        box-sizing: border-box;
        outline: none;
        background: #FAFAFA;
    }
    input:focus {
        border-color: var(--primary);
        background: white;
    }
    button {
        background: var(--primary);
        color: white;
        border: none;
        width: 100%;
        padding: 16px;
        border-radius: 14px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.1s, box-shadow 0.2s;
        margin-top: 16px;
        box-shadow: 0 4px 12px rgba(255, 107, 107, 0.3);
    }
    button:active {
        transform: scale(0.98);
    }
    .networks {
        text-align: left;
        margin-top: 20px;
        border-top: 1px solid #EEE;
        padding-top: 20px;
    }
    .network-item {
        display: flex;
        justify-content: space-between;
        padding: 12px;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.1s;
    }
    .network-item:hover {
        background: #F0F0F0;
    }
    .signal {
        color: var(--primary);
    }
    /* Modal Styles */
    .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: none; align-items: center; justify-content: center; z-index: 100; }
    .modal { background: white; padding: 25px; border-radius: 12px; width: 90%; max-width: 350px; }
    .modal-title { font-size: 18px; font-weight: bold; margin-bottom: 15px; }
    .close-btn { background: transparent; color: #666; float: right; font-size: 20px; margin-top: -10px; cursor: pointer; width: auto; padding: 0; }
</style>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Setup PaperDrop</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    """ + STYLE + """
    <script>
        function selectNetwork(ssid) {
            document.getElementById('modal-ssid').value = ssid;
            document.getElementById('modal-ssid-display').innerText = ssid;
            document.getElementById('modal-overlay').style.display = 'flex';
            document.getElementById('modal-password').focus();
        }
        function closeModal() {
            document.getElementById('modal-overlay').style.display = 'none';
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="logo">PaperDrop</div>
            <h1>Let's get connected</h1>
            <p>Choose your home WiFi so PaperDrop can come online.</p>
            
            <!-- Hidden form for direct submission or modal use -->
            <form action="/connect" method="post" style="display:none">
                 <!-- Kept for fallback if needed, but mainly using modal now -->
            </form>

            <div class="networks">
                <label>Nearby Networks</label>
                <!-- NETWORKS_PLACEHOLDER -->
            </div>
        </div>

        <div id="modal-overlay" class="modal-overlay">
            <div class="modal">
                <button class="close-btn" onclick="closeModal()">×</button>
                <div class="modal-title">Connect to <span id="modal-ssid-display"></span></div>
                <form action="/connect" method="post">
                    <input type="hidden" id="modal-ssid" name="ssid">
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" id="modal-password" name="password" required placeholder="Enter WiFi Password">
                    </div>
                    <button type="submit">Connect</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Connected!</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    """ + STYLE + """
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="logo">PaperDrop</div>
            <h1>Saving Credentials...</h1>
            <p>Your device will now restart and connect to the network.</p>
             <div style="font-size: 60px; margin: 20px 0;">🔄</div>
        </div>
    </div>
</body>
</html>
"""

# ─────────────────────────────────────────────────────────────────────
# CLASS IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────

class WiFiSetupServer:
    def __init__(self, config, on_configured_callback: Callable[[str, str], Awaitable[None]]):
        self.config = config
        self.on_configured = on_configured_callback
        self.server = None
        self.is_running = False
        self.app = FastAPI()
        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def home():
            networks_html = await self._scan_wifi_html()
            return HTML_TEMPLATE.replace("<!-- NETWORKS_PLACEHOLDER -->", networks_html)

        @self.app.get("/{full_path:path}", response_class=HTMLResponse)
        async def catch_all(full_path: str):
            logger.info(f"Captive Portal redirect for: {full_path}")
            networks_html = await self._scan_wifi_html()
            return HTML_TEMPLATE.replace("<!-- NETWORKS_PLACEHOLDER -->", networks_html)


        @self.app.post("/connect", response_class=HTMLResponse)
        async def connect(ssid: str = Form(...), password: str = Form(...), background_tasks: BackgroundTasks = None):
            try:
                logger.info(f"Received credentials for {ssid}")
                
                # Simple validation
                if len(password) < 8:
                     return HTML_TEMPLATE.replace("Connection failed! Please try again.", "Password too short (min 8 chars)").replace("window.location.search.includes('error')", "true")

                # Save credentials implementation
                self.config.save_wifi_credentials(ssid, password)
                
                # Schedule the state change (which kills AP) for AFTER the response is sent
                # We assume on_configured is async, but BackgroundTasks expects sync or async
                background_tasks.add_task(self.on_configured, ssid, password)
                
                # We return a success page that instructs the user
                # We inject the Dashboard URL (Local Mac IP for now, ideally dynamic)
                DASHBOARD_URL = "http://192.168.86.21:5173/setup" 
                
                return f"""
                <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body {{ font-family: -apple-system, sans-serif; padding: 20px; text-align: center; color: #333; }}
                        h1 {{ color: #2ecc71; margin-bottom: 20px; }}
                        .step {{ background: #f9f9f9; padding: 15px; margin: 15px 0; border-radius: 8px; text-align: left; }}
                        .btn {{ display: inline-block; background: #000; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 20px; }}
                    </style>
                </head>
                <body>
                    <h1>Credentials Saved!</h1>
                    <p>The device is now connecting to <strong>{ssid}</strong>...</p>
                    
                    <div class="step">
                        <strong>1. Wait ~30 seconds</strong><br>
                        The "PaperDrop_Setup" hotspot will disappear.
                    </div>
                    
                    <div class="step">
                        <strong>2. Switch Networks</strong><br>
                        Connect your phone back to <strong>{ssid}</strong> (or your home WiFi).
                    </div>
                    
                    <a href="{DASHBOARD_URL}" class="btn">Continue to Dashboard</a>
                </body>
                </html>
                """

            except Exception as e:
                logger.exception("CRITICAL ERROR IN /CONNECT ROUTE")
                return f"<h1>Internal Error</h1><p>{str(e)}</p>"

    async def start(self):
        """Start the Setup AP and Web Server"""
        if self.is_running:
            logger.info("WiFi Setup Server already running.")
            return

        self.is_running = True
        logger.info("Starting WiFi Setup Server...")
        
        # 1. Start Hostapd (AP Mode)
        await self._start_ap_mode()
        
        # 2. Start Web Server (Non-blocking)
        config = UvicornConfig(self.app, host="0.0.0.0", port=8080, log_level="debug")
        self.server = Server(config)
        # Run server in a task so it doesn't block the agent loop
        asyncio.create_task(self.server.serve())

    async def stop(self):
        """Stop server and AP mode"""
        if self.server:
            self.server.should_exit = True
        
        await self._stop_ap_mode()
        self.is_running = False

    # ─────────────────────────────────────────────────────────────────
    # SYSTEM COMMANDS (MOCKED IN DEV/INTEGRATION)
    # ─────────────────────────────────────────────────────────────────

    async def _start_ap_mode(self):
        """Start hostapd and dnsmasq"""
        try:
            # In Dev mode, these might be skipped or mocked binaries will be called
            if os.environ.get("PAPERDROP_ENV") == "development":
                logger.info("[DEV] Skipping AP mode startup commands")
                return

            logger.info("Starting AP Mode (hostapd/dnsmasq)...")
            
            # Unblock wlan0
            await self._run_bg("rfkill", "unblock", "wlan")
            
            # Start interface (using 'ip' command mock)
            await self._run_bg("ip", "link", "set", "wlan0", "up")
            try:
                await self._run_bg("ip", "addr", "flush", "dev", "wlan0")
            except:
                pass
            await self._run_bg("ip", "addr", "add", "192.168.4.1/24", "dev", "wlan0")
            
            # Start services
            # In a real setup these might be systemd services or direct binary calls
            # For this agent approach, we assume we call binaries directly or via systemctl
            await self._run_bg("systemctl", "start", "dnsmasq")
            await self._run_bg("systemctl", "start", "hostapd")
            
        except Exception as e:
            logger.error(f"Failed to start AP mode: {e}")

    async def _stop_ap_mode(self):
        if os.environ.get("PAPERDROP_ENV") == "development":
            return
            
        try:
            await self._run_bg("systemctl", "stop", "hostapd")
            await self._run_bg("systemctl", "stop", "dnsmasq")
        except:
            pass

    async def apply_wifi_credentials(self) -> bool:
        """Use wpa_cli to connect to the network"""
        if os.environ.get("PAPERDROP_ENV") == "development":
            logger.info("[DEV] Pretending to apply WiFi credentials...")
            return True

        ssid, password = self.config.get_wifi_credentials()
        if not ssid:
            return False
            
        logger.info(f"Applying WiFi credentials for {ssid}...")
        
        # This interaction uses wpa_cli (mocked in Layer 2)
        try:
            # 1. Add Network
            # wpa_cli add_network -> returns network_id (e.g. "0")
            # We'll just assume ID 0 for the mock/mvp
            await self._run("wpa_cli", "-i", "wlan0", "add_network")
            
            # 2. Set SSID
            await self._run("wpa_cli", "-i", "wlan0", "set_network", "0", "ssid", f'"{ssid}"')
            
            # 3. Set Password
            await self._run("wpa_cli", "-i", "wlan0", "set_network", "0", "psk", f'"{password}"')
            
            # 4. Enable
            await self._run("wpa_cli", "-i", "wlan0", "enable_network", "0")
            
            # 5. Save
            await self._run("wpa_cli", "-i", "wlan0", "save_config")
            
            # 6. Reassociate
            await self._run("wpa_cli", "-i", "wlan0", "reassociate")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply WiFi creds: {e}")
            return False

    async def _scan_wifi_html(self) -> str:
        """Scan for networks and return HTML string"""
        if os.environ.get("PAPERDROP_ENV") == "development":
            return """
            <div class="network-item" onclick="document.getElementById('ssid').value='Dev_Net_1'"><span>Dev_Net_1</span><span class="signal">Strong</span></div>
            <div class="network-item" onclick="document.getElementById('ssid').value='Dev_Net_2'"><span>Dev_Net_2</span><span class="signal">Weak</span></div>
            """

        try:
            # Run scan dump (Instant, cached results)
            # If empty, we might want to trigger a background scan, but usually dump is enough
            proc = await asyncio.create_subprocess_shell(
                "sudo /usr/sbin/iw dev wlan0 scan dump",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode('utf-8')

            networks = []
            current_ssid = None
            current_signal = 0

            for line in output.split('\n'):
                line = line.strip()
                if line.startswith("SSID:"):
                    ssid = line.replace("SSID: ", "").strip()
                    if ssid and "\\x00" not in ssid and len(ssid) > 0:
                         networks.append((ssid, current_signal))
                elif line.startswith("signal:"):
                    try:
                         # Format: signal: -50.00 dBm
                         sig_str = line.split(" ")[1]
                         current_signal = float(sig_str)
                    except:
                        pass

            # Dedup and sort by signal
            unique_nets = {}
            for ssid, sig in networks:
                if ssid not in unique_nets or sig > unique_nets[ssid]:
                     unique_nets[ssid] = sig

            sorted_nets = sorted(unique_nets.items(), key=lambda x: x[1], reverse=True)
            
            html = ""
            for ssid, sig in sorted_nets[:10]: # Top 10
                 signal_text = "Strong" if sig > -60 else "Good" if sig > -70 else "Weak"
                 html += f"""
                 <div class="network-item" onclick="selectNetwork('{ssid}')">
                    <span>{ssid}</span>
                    <span class="signal">{signal_text}</span>
                 </div>
                 """
            
            
            if not html:
                # Trigger active scan in background to populate cache for next refresh
                await self._run_bg("sudo", "/usr/sbin/iw", "dev", "wlan0", "scan")
                return "<div style='padding:10px; color:#666;'>Scanning... Refresh in 5s</div>"
                
            return html

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            return "<div style='padding:10px; color:red;'>Scan error</div>"

    async def _run(self, *args):
        """Run a subprocess and wait for it"""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if proc.returncode != 0:
            raise Exception(f"Command failed: {args}")

    async def _run_bg(self, *args):
        """Run a subprocess in background (fire and forget basically, or just wait)"""
        # For simplicity reusing _run
        await self._run(*args)

