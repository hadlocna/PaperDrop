import asyncio
import logging
import os
import subprocess
from pathlib import Path
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
# SELF-HEALING RESOURCES
# ─────────────────────────────────────────────────────────────────────

RECOVERY_SCRIPTS = {
    "/opt/paperdrop/enable_apsta.sh": r"""#!/bin/bash
set -e

# CONSTANTS
PHY_IFACE="wlan0"
AP_IFACE="uap0"
IP_ADDR="192.168.4.1/24"
HOSTAPD_CONF="/etc/paperdrop/hostapd_apsta.conf"
DNSMASQ_CONF="/etc/paperdrop/dnsmasq_apsta.conf"

function start() {
    echo "[APSTA] Enabling Mode..."
    
    # 0. Harden NetworkManager (Prevent interference)
    if command -v nmcli >/dev/null 2>&1; then
        echo "[APSTA] Configuring NetworkManager to ignore $AP_IFACE..."
        nmcli dev set $AP_IFACE managed no || true
    fi

    # 1. Create uap0 if not exists
    if ! iw dev $AP_IFACE info >/dev/null 2>&1; then
        echo "[APSTA] Creating virtual interface $AP_IFACE..."
        iw dev $PHY_IFACE interface add $AP_IFACE type __ap
        ip link set dev $AP_IFACE address 02:00:00:00:01:00
    fi

    # 2. Config IP
    echo "[APSTA] Setting IP for $AP_IFACE..."
    ip link set $AP_IFACE up
    ip addr flush dev $AP_IFACE
    ip addr add $IP_ADDR dev $AP_IFACE

    # 3. Config Firewall (NAT + Redirect)
    echo "[APSTA] Configuring firewall (NAT + Redirect)..."
    sysctl -w net.ipv4.ip_forward=1 > /dev/null
    
    # Cleanups
    iptables -t nat -D PREROUTING -i $AP_IFACE -d $IP_ADDR -p tcp --dport 80 -j REDIRECT --to-port 8080 2>/dev/null || true
    iptables -t nat -D POSTROUTING -o $PHY_IFACE -j MASQUERADE 2>/dev/null || true

    iptables -t nat -A PREROUTING -i $AP_IFACE -d $IP_ADDR -p tcp --dport 80 -j REDIRECT --to-port 8080
    iptables -t nat -A POSTROUTING -o $PHY_IFACE -j MASQUERADE
    
    iptables -D FORWARD -i $PHY_IFACE -o $AP_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i $AP_IFACE -o $PHY_IFACE -j ACCEPT 2>/dev/null || true
    
    iptables -A FORWARD -i $PHY_IFACE -o $AP_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i $AP_IFACE -o $PHY_IFACE -j ACCEPT

    # 4. Channel Sync (Avoid Single-Radio Conflict)
    CURRENT_CHANNEL=$(iw dev $PHY_IFACE info 2>/dev/null | grep channel | awk '{print $2}')
    if [ ! -z "$CURRENT_CHANNEL" ]; then
        echo "[APSTA] Detected wlan0 on channel $CURRENT_CHANNEL. Syncing hostapd..."
        sed -i "s/channel=.*/channel=$CURRENT_CHANNEL/" $HOSTAPD_CONF
    fi

    # 5. Start Services
    echo "[APSTA] Waiting for interface to stabilize..."
    sleep 2
    
    echo "[APSTA] Starting dnsmasq..."
    killall dnsmasq || true
    dnsmasq -C $DNSMASQ_CONF || { echo "[APSTA] dnsmasq failed to start!"; exit 1; }

    echo "[APSTA] Starting hostapd..."
    killall hostapd || true
    hostapd -B $HOSTAPD_CONF
    
    echo "[APSTA] Enabled."
}

function stop() {
    echo "[APSTA] Disabling Mode..."
    killall hostapd || true
    killall dnsmasq || true
    
    iptables -t nat -F PREROUTING
    
    if iw dev $AP_IFACE info >/dev/null 2>&1; then
        echo "[APSTA] Removing $AP_IFACE..."
        iw dev $AP_IFACE del
    fi
    echo "[APSTA] Disabled."
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac
""",
    "/etc/paperdrop/dnsmasq_apsta.conf": r"""interface=uap0
bind-interfaces
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=paperdrop.local

# Upstream DNS (Google)
server=8.8.8.8
server=8.8.4.4

# TARGETED CAPTIVE PORTAL POISONING
address=/setup.paperdrop.local/192.168.4.1
address=/connectivitycheck.gstatic.com/192.168.4.1
address=/connectivitycheck.android.com/192.168.4.1
address=/clients3.google.com/192.168.4.1
address=/clients2.google.com/192.168.4.1
address=/android.clients.google.com/192.168.4.1
address=/captive.apple.com/192.168.4.1
address=/airport.us/192.168.4.1
address=/thinkdifferent.us/192.168.4.1
address=/ibeacon.apple.com/192.168.4.1
address=/www.msftconnecttest.com/192.168.4.1
address=/msftconnecttest.com/192.168.4.1
address=/msftncsi.com/192.168.4.1
address=/www.msftncsi.com/192.168.4.1
address=/detectportal.firefox.com/192.168.4.1
""",
    "/etc/paperdrop/hostapd_apsta.conf": r"""interface=uap0
driver=nl80211
ssid=PaperDrop_Setup
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
ieee80211n=1
"""
}

# ─────────────────────────────────────────────────────────────────────
# CLASS IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────

class WiFiSetupServer:
    def __init__(self, config, on_configured_callback: Callable[[str, str], Awaitable[None]]):
        self.config = config
        self.on_configured = on_configured_callback
        self.server = None
        self.is_running = False
        self.connection_state = {"state": "IDLE", "status": "Waiting..."} # IDLE, CONNECTING, CONNECTED, FAILED
        self.app = FastAPI()
        self._setup_routes()
        
        # Self-Healing: Ensure scripts exist
        self._ensure_scripts_exist()

    def _ensure_scripts_exist(self):
        """Recover missing scripts from embedded backup"""
        if os.environ.get("PAPERDROP_ENV") == "development":
            return

        for path_str, content in RECOVERY_SCRIPTS.items():
            path = Path(path_str)
            if not path.exists():
                logger.warning(f"⚠️ Missing critical file: {path}. restoring from backup...")
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    # Write file
                    with open(path, 'w') as f:
                        f.write(content)
                    
                    # Make executable if it's the script
                    if path_str.endswith(".sh"):
                        os.chmod(path, 0o755)
                        
                    logger.info(f"✅ Restored {path}")
                except Exception as e:
                    logger.error(f"❌ Failed to restore {path}: {e}")

    def _setup_routes(self):
        from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

        @self.app.get("/status")
        async def status():
            return JSONResponse(self.connection_state)

        @self.app.get("/", response_class=HTMLResponse)
        async def home():
            networks_html = await self._scan_wifi_html()
            return HTML_TEMPLATE.replace("<!-- NETWORKS_PLACEHOLDER -->", networks_html)

        @self.app.get("/generate_204")
        async def generate_204():
            # Android check. We want to fail this check so it knows it's captive.
            # But redirecting to the portal is the standard way.
            return RedirectResponse("/")

        @self.app.get("/{full_path:path}")
        async def catch_all(full_path: str):
            logger.info(f"Captive Portal probe: {full_path}")
            # Redirect everything to root to force the popup URL to verify
            # Some devices check for specific content (Success) on 200 OK.
            # Returning 302 Found -> / usually triggers the CNA.
            return RedirectResponse("/")


        @self.app.post("/connect", response_class=HTMLResponse)
        async def connect(ssid: str = Form(...), password: str = Form(...), background_tasks: BackgroundTasks = None):
            try:
                logger.info(f"Received credentials for {ssid}")
                
                # Simple validation
                if len(password) < 8:
                     return HTML_TEMPLATE.replace("Connection failed! Please try again.", "Password too short (min 8 chars)").replace("window.location.search.includes('error')", "true")

                # Save credentials implementation
                self.config.save_wifi_credentials(ssid, password)
                
                # Update State
                self.connection_state = {"state": "CONNECTING", "status": f"Connecting to {ssid}..."}

                # Schedule the state change (which kills AP) for AFTER the response is sent
                # We assume on_configured is async, but BackgroundTasks expects sync or async
                background_tasks.add_task(self.on_configured, ssid, password)
                
                # Read Device Code
                import json
                device_code = "UNKNOWN"
                try:
                    with open("/etc/paperdrop/device.json", "r") as f:
                        data = json.load(f)
                        device_code = data.get("device_code", "UNKNOWN")
                except:
                    pass

                # DASHBOARD_URL = "http://192.168.86.21:5173/setup" # Local fallback
                DASHBOARD_URL = f"https://paperdrop-frontend.onrender.com/claim?code={device_code}"
                
                # Return a page with the same styling as the landing page
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Connecting - PaperDrop</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    """ + STYLE + """
                    <style>
                        .status-icon {{ font-size: 48px; margin: 20px 0; }}
                        .spinner {{ animation: spin 1.5s linear infinite; display: inline-block; }}
                        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                        .code {{ font-family: monospace; font-size: 28px; background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; padding: 12px 20px; border-radius: 12px; letter-spacing: 3px; display: inline-block; margin: 16px 0; }}
                        .success-text {{ color: var(--secondary); }}
                        .error-text {{ color: var(--primary); }}
                        a.btn {{ display: inline-block; background: var(--primary); color: white; padding: 16px 32px; text-decoration: none; border-radius: 14px; font-weight: 600; margin-top: 16px; box-shadow: 0 4px 12px rgba(255, 107, 107, 0.3); }}
                        a.btn-secondary {{ background: #636E72; box-shadow: 0 4px 12px rgba(99, 110, 114, 0.3); }}
                        .hidden {{ display: none !important; }}
                    </style>
                    <script>
                        function checkStatus() {{
                            fetch('/status')
                                .then(response => response.json())
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
                                .catch(e => setTimeout(checkStatus, 2000));
                        }}
                        window.onload = checkStatus;
                    </script>
                </head>
                <body>
                    <div class="container">
                        <div class="card">
                            <div class="logo">PaperDrop</div>
                            
                            <!-- Connecting State -->
                            <div id="connecting-view">
                                <h1>Connecting to WiFi</h1>
                                <p id="status-msg">Connecting to {ssid}...</p>
                                <div class="status-icon"><span class="spinner">🔄</span></div>
                                <p style="color: var(--text-secondary); font-size: 12px;">This may take up to 30 seconds</p>
                            </div>
                            
                            <!-- Success State -->
                            <div id="success-view" class="hidden">
                                <h1 class="success-text">Connected!</h1>
                                <div class="status-icon">✅</div>
                                <p>Your PaperDrop is now online.</p>
                                <p style="margin-bottom: 8px; font-size: 12px; color: var(--text-secondary);">YOUR DEVICE CODE</p>
                                <div class="code">{device_code}</div>
                                <p style="font-size: 13px; color: var(--text-secondary);">Use this code to add the device to your account</p>
                                <a href="{DASHBOARD_URL}" class="btn">Add to My Account</a>
                            </div>
                            
                            <!-- Error State -->
                            <div id="error-view" class="hidden">
                                <h1 class="error-text">Connection Failed</h1>
                                <div class="status-icon">❌</div>
                                <p id="error-msg">Could not connect to WiFi</p>
                                <a href="/" class="btn btn-secondary">Try Again</a>
                            </div>
                        </div>
                    </div>
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
        """Start AP+STA mode using helper script"""
        try:
            if os.environ.get("PAPERDROP_ENV") == "development":
                logger.info("[DEV] Skipping AP mode startup commands")
                return

            logger.info("Starting AP+STA Mode...")
            # We assume the script is installed at /opt/paperdrop/enable_apsta.sh
            await self._run_bg("sudo", "/opt/paperdrop/enable_apsta.sh", "start")
            
        except Exception as e:
            logger.error(f"Failed to start AP mode: {e}")

    async def _stop_ap_mode(self):
        if os.environ.get("PAPERDROP_ENV") == "development":
            return
            
        try:
            await self._run_bg("sudo", "/opt/paperdrop/enable_apsta.sh", "stop")
        except:
            pass

    async def apply_wifi_credentials(self) -> bool:
        """Apply credentials to wlan0 WITHOUT stopping AP"""
        if os.environ.get("PAPERDROP_ENV") == "development":
            logger.info("[DEV] Pretending to apply WiFi credentials...")
            return True

        ssid, password = self.config.get_wifi_credentials()
        if not ssid:
            return False
            
        logger.info(f"Applying WiFi credentials for {ssid} to wlan0 (Concurrent Mode)...")
        
        try:
            # 1. Update wpa_supplicant.conf
            # We use wpa_cli to add the network dynamically
            
            # Flush existing networks to be clean
            # Note: This might be aggressive, but for a simple setup it ensures we target the right one
            # wpa_cli is tricky with IDs. We'll just try to add a new one and select it.
            
            # Simple approach: Overwrite wpa_supplicant.conf directly and reconfigure
            # This is often more reliable than wpa_cli state management
            conf_content = f'''ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={{
    ssid="{ssid}"
    psk="{password}"
}}
'''
            # Write to temp then move
            cmd = f"echo '{conf_content}' > /tmp/wpa_supplicant.conf && sudo mv /tmp/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf"
            await self._run_bg("bash", "-c", cmd)
            
            # 2. Reconfigure wpa_supplicant
            await self._run("wpa_cli", "-i", "wlan0", "reconfigure")
            
            # 3. Wait for Connection (Poll for IP)
            self.connection_state = {"state": "CONNECTING", "status": "Obtaining IP..."}
            for _ in range(30): # Wait 30 seconds
                await asyncio.sleep(1)
                # Check for IP on wlan0
                pk = await asyncio.create_subprocess_shell("ip -4 addr show wlan0 | grep inet", stdout=asyncio.subprocess.PIPE)
                stdout, _ = await pk.communicate()
                if b"inet" in stdout:
                    logger.info("Connected! IP acquired.")
                    self.connection_state = {"state": "CONNECTED", "status": "Connected!"}
                    return True
            
            logger.error("Timed out waiting for connection.")
            self.connection_state = {"state": "FAILED", "status": "Timeout"}
            return False
            
        except Exception as e:
            logger.error(f"Failed to apply WiFi creds: {e}")
            self.connection_state = {"state": "FAILED", "status": f"Error: {str(e)}"}
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

