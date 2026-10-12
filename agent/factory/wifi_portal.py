#!/usr/bin/python3
"""Offline network picker and captive portal for PaperDrop's setup access point."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit

ADDRESS = '10.42.0.1'
PROFILE = 'PaperDrop-Setup'
INTERFACE = 'wlan0'
TOKEN = secrets.token_urlsafe(24)
ALLOWED_HOSTS = {ADDRESS, 'paperdrop.setup', 'localhost', '127.0.0.1'}


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=35)


def connected():
    result = run('nmcli', '-t', '-f', 'TYPE,STATE,CONNECTION', 'device')
    return any(':connected:' in line and not line.endswith(':' + PROFILE)
               and line.split(':')[0] in ('wifi', 'ethernet')
               for line in result.stdout.splitlines())


def fields(line):
    """nmcli terse fields escape both colons and backslashes in network names."""
    result, part, escaped = [], '', False
    for character in line:
        if escaped:
            part += character
            escaped = False
        elif character == '\\':
            escaped = True
        elif character == ':':
            result.append(part)
            part = ''
        else:
            part += character
    result.append(part)
    return result


def parse_networks(output):
    networks = {}
    for line in output.splitlines():
        parts = fields(line)
        if len(parts) != 3:
            continue
        ssid, strength, security = parts
        if not ssid or ssid == PROFILE:
            continue
        try:
            signal = max(0, min(100, int(strength)))
        except ValueError:
            continue
        unsupported = any(word in security for word in ('802.1X', 'EAP', 'WEP'))
        network = {'ssid': ssid, 'signal': signal, 'secured': 'WPA' in security or 'WEP' in security,
                   'supported': not unsupported, 'security': security or '--'}
        if ssid not in networks or signal > networks[ssid]['signal']:
            networks[ssid] = network
    return sorted(networks.values(), key=lambda item: (-item['signal'], item['ssid']))


def valid_country(value):
    return bool(re.fullmatch('[A-Z]{2}', value))


class Portal:
    def __init__(self):
        self.lock = threading.Lock()
        self.scan_lock = threading.Lock()
        self.networks = []
        self.scan_time = 0
        self.scan_error = ''
        self.country = 'US'
        self.state = {'state': 'ready', 'message': '', 'ssid': ''}
        self.dns = None

    def scan(self, force=False):
        with self.scan_lock:
            with self.lock:
                if self.state['state'] == 'connecting':
                    return {'networks': self.networks, 'message': self.scan_error}
            if not force and time.monotonic() - self.scan_time < 15:
                return {'networks': self.networks, 'message': self.scan_error}
            try:
                result = run('nmcli', '-t', '--escape', 'yes', '-f', 'SSID,SIGNAL,SECURITY',
                             'device', 'wifi', 'list', 'ifname', INTERFACE, '--rescan', 'yes')
                discovered = parse_networks(result.stdout) if result.returncode == 0 else []
                self.scan_error = ''
                if not discovered:
                    # Some Pi radios cannot rescan all channels while hosting the setup AP.
                    cached = run('nmcli', '-t', '--escape', 'yes', '-f', 'SSID,SIGNAL,SECURITY',
                                 'device', 'wifi', 'list', 'ifname', INTERFACE, '--rescan', 'no')
                    discovered = parse_networks(cached.stdout) if cached.returncode == 0 else []
                    self.scan_error = 'Showing the last available scan. Refresh or enter your network name below.'
                if discovered:
                    self.networks = discovered
            except (OSError, subprocess.SubprocessError):
                self.scan_error = 'We could not refresh the network list. Try again or enter your network name below.'
            self.scan_time = time.monotonic()
            return {'networks': self.networks, 'message': self.scan_error}

    def stop_dns(self):
        if self.dns is not None:
            self.dns.terminate()
            try:
                self.dns.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.dns.kill()
                self.dns.wait()
            self.dns = None

    def start_ap(self):
        """NM owns the radio; a dedicated dnsmasq owns only the setup subnet."""
        run('rfkill', 'unblock', 'wifi')
        result = run('nmcli', 'connection', 'show', PROFILE)
        if result.returncode:
            result = run('nmcli', 'connection', 'add', 'type', 'wifi', 'ifname', INTERFACE,
                         'con-name', PROFILE, 'ssid', PROFILE)
            if result.returncode:
                raise RuntimeError('Could not create setup Wi-Fi')
        result = run('nmcli', 'connection', 'modify', PROFILE,
                     '802-11-wireless.mode', 'ap', '802-11-wireless.band', 'bg',
                     '802-11-wireless-security.key-mgmt', 'wpa-psk',
                     '802-11-wireless-security.psk', 'paperdrop-setup',
                     'ipv4.method', 'manual', 'ipv4.addresses', ADDRESS + '/24',
                     'ipv4.gateway', '', 'ipv4.dns', '', 'ipv4.never-default', 'yes',
                     'ipv6.method', 'disabled', 'connection.autoconnect', 'no')
        if result.returncode or run('nmcli', 'connection', 'up', PROFILE).returncode:
            raise RuntimeError('Could not start setup Wi-Fi')
        self.stop_dns()
        # No system-wide DNS configuration, upstream DNS or Internet dependency.
        self.dns = subprocess.Popen([
            'dnsmasq', '--keep-in-foreground', '--conf-file=/dev/null', '--pid-file=',
            '--interface=' + INTERFACE, '--except-interface=lo', '--bind-dynamic',
            '--listen-address=' + ADDRESS, '--no-resolv', '--no-hosts',
            '--address=/#/' + ADDRESS, '--local=/#/',
            '--dhcp-range=10.42.0.10,10.42.0.200,255.255.255.0,10m',
            '--dhcp-option=3,' + ADDRESS, '--dhcp-option=6,' + ADDRESS,
            '--dhcp-authoritative', '--leasefile-ro'], stdout=subprocess.DEVNULL)
        time.sleep(0.5)
        if self.dns.poll() is not None:
            raise RuntimeError('Could not start setup DNS and DHCP')

    def begin_connection(self, data):
        ssid = data.get('ssid', '')
        password = data.get('password', '')
        country = data.get('country', self.country).upper()
        security = data.get('security', 'secured')
        if not 1 <= len(ssid.encode()) <= 32 or any(ord(c) < 32 for c in ssid) or ssid == PROFILE:
            raise ValueError('Enter a network name of 1–32 bytes.')
        if not valid_country(country):
            raise ValueError('Choose your country using its two-letter code, such as PT.')
        if security not in ('open', 'secured'):
            raise ValueError('Choose the network security type.')
        if security == 'secured' and not (8 <= len(password) <= 63 or re.fullmatch('[0-9a-fA-F]{64}', password)):
            raise ValueError('Wi-Fi passwords need 8–63 characters, or a 64-digit hexadecimal key.')
        if len(password.encode()) > 256 or any(ord(c) < 32 for c in password):
            raise ValueError('Check the Wi-Fi password and try again.')
        with self.lock:
            if self.state['state'] == 'connecting':
                return False
            self.state = {'state': 'connecting', 'message': 'Connecting to your Wi-Fi…', 'ssid': ssid}
        threading.Thread(target=self.connect,
                         args=(ssid, password, country, security, data.get('hidden') == 'yes'),
                         daemon=True).start()
        return True

    def connect(self, ssid, password, country, security, hidden=False):
        # Do not change radio mode in the middle of an in-flight network scan.
        with self.scan_lock:
            self._connect(ssid, password, country, security, hidden)

    def _connect(self, ssid, password, country, security, hidden):
        try:
            # Give the browser time to receive the response before removing its network.
            time.sleep(2)
            if run('raspi-config', 'nonint', 'do_wifi_country', country).returncode:
                raise RuntimeError('Could not set Wi-Fi country')
            self.country = country
            self.stop_dns()
            run('nmcli', 'connection', 'down', PROFILE)
            args = ['nmcli', 'device', 'wifi', 'connect', ssid, 'ifname', INTERFACE]
            if hidden:
                args += ['hidden', 'yes']
            if security == 'secured':
                args += ['password', password]
            result = run(*args)
            if result.returncode or not connected():
                raise RuntimeError('Wi-Fi activation failed')
            with self.lock:
                self.state = {'state': 'connected', 'message': 'PaperDrop is connected to Wi-Fi.', 'ssid': ssid}
        except (OSError, subprocess.SubprocessError, RuntimeError):
            # Do not expose nmcli output: it can contain credentials.
            try:
                self.start_ap()
            finally:
                with self.lock:
                    self.state = {'state': 'failed', 'message': 'We could not connect. Check the password and network, then try again.', 'ssid': ssid}
        else:
            # A runtime/enrollment failure must not undo a successful Wi-Fi connection.
            try:
                run('systemctl', 'restart', 'paperdrop-enroll.service')
                run('systemctl', 'start', 'paperdrop-runtime.service')
            except (OSError, subprocess.SubprocessError):
                pass


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#f6f3ec"><title>Connect PaperDrop</title>
<style>
:root{font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#203b32;background:#f6f3ec;font-synthesis:none}*{box-sizing:border-box}body{margin:0;padding:28px 20px 48px}main{max-width:480px;margin:auto}.brand{display:flex;gap:10px;align-items:center;font-weight:750;font-size:19px;margin-bottom:32px}.mark{width:34px;height:38px;border-radius:9px 9px 14px 9px;background:#244b3c;color:white;display:grid;place-items:center;font-size:22px}.step{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#567164;font-weight:750}h1{font-size:36px;line-height:1.1;letter-spacing:-1.5px;margin:12px 0}p{line-height:1.55;margin:0 0 22px;color:#59675d}.card{background:#fff;border:1px solid #e0e4db;border-radius:20px;padding:22px;margin-top:24px;box-shadow:0 6px 22px #203b3205}.heading{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}h2{font-size:16px;margin:0}.quiet{background:none;border:0;color:#35624e;font:inherit;font-size:14px;font-weight:650;cursor:pointer;padding:10px;min-height:44px}.network{display:flex;align-items:center;gap:12px;width:100%;padding:16px 2px;background:none;border:0;border-bottom:1px solid #edf0e9;text-align:left;cursor:pointer;color:inherit;font:inherit;min-height:66px}.network:last-child{border-bottom:0}.network:disabled{cursor:default;opacity:.6}.network:hover:enabled{background:#f5f8f3}.network.selected{background:#edf5ef;border-radius:12px;padding:16px 10px}.bars{display:flex;gap:3px;align-items:flex-end;width:28px;height:22px;flex-shrink:0}.bars i{width:4px;background:#d7dfd6;border-radius:2px}.bars i.on{background:#467258}.name{flex:1;min-width:0;overflow-wrap:anywhere}.name strong{display:block;font-size:15px}.name small{font-size:12px;color:#6e7c70}.arrow{font-size:20px}.empty{font-size:14px;padding:18px 0;margin:0}.hint{font-size:13px;margin:12px 0 0}.manual{margin:14px 0 0;padding:0;text-align:left;font-size:14px}label{display:block;font-size:14px;font-weight:650;margin:18px 0 8px}input,select{font:inherit;color:inherit;padding:13px;border:1px solid #cdd7cc;border-radius:10px;background:#fff;width:100%;min-height:48px}input:focus,select:focus,button:focus-visible{outline:3px solid #99bea6;outline-offset:2px}.password{position:relative}.password input{padding-right:76px}.password button{position:absolute;right:6px;top:3px}.primary{background:#244b3c;color:#fff;font:inherit;font-weight:650;border:0;border-radius:12px;padding:15px;width:100%;min-height:50px;margin-top:22px;cursor:pointer}.primary:disabled{opacity:.65;cursor:wait}.back{padding:0;margin-bottom:10px}.status{padding:15px 17px;background:#edf5ef;border:1px solid #c9ddcd;border-radius:12px;margin:22px 0 0;font-size:14px;line-height:1.5}.status.error{background:#fff1e9;border-color:#efd1bd;color:#823e24}.status h2{margin:0 0 8px}footer{margin-top:25px;font-size:12px;color:#718073;line-height:1.7;text-align:center}footer a{color:inherit}details{margin-top:20px}summary{cursor:pointer;font-size:13px;color:#627264;min-height:30px}[hidden]{display:none!important}@media(max-width:360px){body{padding:22px 14px}h1{font-size:32px}.card{padding:17px}}
</style></head><body><main>
<div class="brand"><span class="mark" aria-hidden="true">↳</span>PaperDrop</div>
<div class="step">A little setup. A lot of magic.</div><h1>Let’s get connected.</h1>
<p>Choose the Wi-Fi you want PaperDrop to use.</p>
<div id="status" class="status" role="status" aria-live="polite" __STATUS_HIDDEN__>__STATUS__</div>
<section class="card" id="picker" aria-labelledby="networks-title">
<div class="heading"><h2 id="networks-title">Nearby networks</h2><button class="quiet" id="refresh" type="button">↻ Refresh</button></div>
<div id="networks" aria-live="polite"><p class="empty">Looking for Wi-Fi…</p></div>
<p class="hint" id="scan-message" hidden></p>
<button class="quiet manual" id="manual" type="button">Don’t see your network? Enter its name</button>
</section>
<section class="card" id="connection" hidden aria-labelledby="connection-title">
<button type="button" class="quiet back" id="back">← All networks</button>
<h2 id="connection-title">Connect to Wi-Fi</h2>
<form id="form" method="post" action="/connect">
<input type="hidden" name="token" value="__TOKEN__">
<input type="hidden" name="hidden" id="hidden-network" value="no">
<div id="name-field"><label for="ssid">Network name</label><input id="ssid" name="ssid" required autocomplete="off"></div>
<div id="security-field"><label for="security">Network security</label><select id="security" name="security"><option value="secured">Password protected</option><option value="open">Open network · no password</option></select></div>
<div id="password-field"><label for="password">Wi-Fi password</label><div class="password"><input id="password" name="password" type="password" autocomplete="off" autocapitalize="none" spellcheck="false" minlength="8" maxlength="64"><button class="quiet" id="show" type="button" aria-label="Show password" aria-pressed="false">Show</button></div></div>
<details><summary>Country / region</summary><label for="country">Two-letter country code</label><input id="country" name="country" value="__COUNTRY__" maxlength="2" minlength="2" pattern="[A-Za-z]{2}" required autocapitalize="characters"><p class="hint">Use PT for Portugal, GB for the UK, or US for the United States.</p></details>
<button class="primary" id="submit" type="submit">Connect PaperDrop</button>
</form></section>
<noscript><style>#connection{display:block!important}#picker{display:none}</style><p class="hint">Enter your Wi-Fi name and password below.</p></noscript>
<footer>Keep this phone on PaperDrop-Setup until you connect.<br>Setup page: <a href="http://10.42.0.1">10.42.0.1</a><br>__DEVICE__</footer>
</main><script>
const $ = (id) => document.getElementById(id);
let busy = false;
let polling = false;
function message(text, error = false) {
  $("status").hidden = !text;
  $("status").textContent = text;
  $("status").classList.toggle("error", error);
}
function passwordMode() {
  const secured = $("security").value === "secured";
  $("password-field").hidden = !secured;
  $("password").required = secured;
  $("password").disabled = !secured;
}
function selectNetwork(network) {
  $("hidden-network").value = network ? "no" : "yes";
  $("picker").hidden = true;
  $("connection").hidden = false;
  $("ssid").value = network ? network.ssid : "";
  $("name-field").hidden = !!network;
  $("security-field").hidden = !!network;
  $("security").value = network && !network.secured ? "open" : "secured";
  $("connection-title").textContent = network
    ? network.ssid
    : "Enter your network";
  $("password").value = "";
  $("password").type = "password";
  $("show").textContent = "Show";
  $("show").setAttribute("aria-pressed", "false");
  passwordMode();
  ($("security").value === "secured" && network
    ? $("password")
    : $("ssid")
  ).focus();
}
async function scan(refresh = false) {
  if (busy) return;
  $("refresh").disabled = true;
  $("refresh").textContent = "Scanning…";
  try {
    const response = await fetch(
      "/api/networks" + (refresh ? "?refresh=1" : ""),
      { cache: "no-store" },
    );
    if (!response.ok) throw Error();
    const data = await response.json();
    $("networks").replaceChildren();
    for (const network of data.networks) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "network";
      button.disabled = !network.supported;
      const bars = document.createElement("span");
      bars.className = "bars";
      bars.setAttribute("aria-hidden", "true");
      for (let i = 0; i < 4; i++) {
        const bar = document.createElement("i");
        bar.style.height = 7 + i * 5 + "px";
        if (network.signal > i * 25) bar.className = "on";
        bars.append(bar);
      }
      const name = document.createElement("span");
      name.className = "name";
      const strong = document.createElement("strong");
      strong.textContent = network.ssid;
      const small = document.createElement("small");
      small.textContent = !network.supported
        ? "This network needs a different sign-in method"
        : (network.secured ? "Password protected" : "No password") +
          " · " +
          (network.signal > 65
            ? "Strong signal"
            : network.signal > 35
              ? "Good signal"
              : "Weak signal");
      name.append(strong, small);
      const arrow = document.createElement("span");
      arrow.className = "arrow";
      arrow.textContent = "›";
      arrow.setAttribute("aria-hidden", "true");
      button.append(bars, name, arrow);
      button.addEventListener("click", () => selectNetwork(network));
      $("networks").append(button);
    }
    if (!data.networks.length) {
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent =
        "No nearby networks found. Refresh or enter your network name.";
      $("networks").append(p);
    }
    $("scan-message").textContent = data.message;
    $("scan-message").hidden = !data.message;
  } catch {
    $("networks").textContent =
      "Unable to load nearby networks. Refresh or enter your network name.";
  } finally {
    $("refresh").disabled = false;
    $("refresh").textContent = "↻ Refresh";
  }
}
$("refresh").addEventListener("click", () => scan(true));
$("manual").addEventListener("click", () => selectNetwork(null));
$("back").addEventListener("click", () => {
  if (!busy) {
    $("picker").hidden = false;
    $("connection").hidden = true;
    $("password").value = "";
    $("manual").focus();
  }
});
$("security").addEventListener("change", passwordMode);
$("show").addEventListener("click", () => {
  const showing = $("password").type === "password";
  $("password").type = showing ? "text" : "password";
  $("show").textContent = showing ? "Hide" : "Show";
  $("show").setAttribute(
    "aria-label",
    showing ? "Hide password" : "Show password",
  );
  $("show").setAttribute("aria-pressed", String(showing));
});
function setBusy(value) {
  busy = value;
  for (const field of $("form").elements)
    if (field.id !== "password") field.disabled = value;
  $("password").disabled = value || $("security").value === "open";
  $("back").disabled = value;
  $("manual").disabled = value;
  $("refresh").disabled = value;
  $("submit").textContent = value ? "Connecting…" : "Connect PaperDrop";
}
async function getStatus() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    return await fetch("/api/status", {
      cache: "no-store",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}
async function poll() {
  if (polling) return;
  polling = true;
  let misses = 0;
  while (busy) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    try {
      const response = await getStatus();
      if (!response.ok) throw Error();
      const data = await response.json();
      misses = 0;
      if (data.state === "failed") {
        setBusy(false);
        message(data.message, true);
        break;
      }
      if (data.state === "connected") {
        message(
          data.message + " Rejoin your normal Wi-Fi, then open PaperDrop.",
        );
        $("password").value = "";
        break;
      }
      message(data.message || "Connecting…");
    } catch {
      misses++;
      message(
        "PaperDrop is switching networks. If PaperDrop-Setup disappears, rejoin your normal Wi-Fi and check PaperDrop. If setup returns, reconnect here to try again.",
      );
      if (misses >= 15) {
        setBusy(false);
        message(
          "Check PaperDrop on your normal Wi-Fi. If it is still offline, reconnect to PaperDrop-Setup to try again.",
        );
        break;
      }
    }
  }
  polling = false;
}
$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const data = new URLSearchParams(new FormData($("form")));
  setBusy(true);
  message(
    "Connecting… The setup Wi-Fi may disappear while PaperDrop changes networks.",
  );
  try {
    const response = await fetch("/connect", { method: "POST", body: data });
    const result = await response.json();
    if (!response.ok) {
      setBusy(false);
      message(result.message, true);
      return;
    }
    $("password").value = "";
    poll();
  } catch {
    setBusy(false);
    message(
      "We could not send your Wi-Fi details. Stay on PaperDrop-Setup and try again.",
      true,
    );
  }
});
fetch("/api/status", { cache: "no-store" })
  .then((r) => r.json())
  .then((data) => {
    if (data.state === "connecting") {
      setBusy(true);
      message(data.message);
      poll();
    } else if (data.state === "failed") message(data.message, true);
  })
  .catch(() => {});
scan();
</script></body></html>'''


def page(portal):
    code = Path('/etc/paperdrop/device-id')
    device = code.read_text().strip() if code.exists() else ''
    with portal.lock:
        state = portal.state.copy()
    return (PAGE.replace('__TOKEN__', html.escape(TOKEN, quote=True))
            .replace('__COUNTRY__', html.escape(portal.country, quote=True))
            .replace('__DEVICE__', html.escape(device))
            .replace('__STATUS_HIDDEN__', '' if state['message'] else 'hidden')
            .replace('__STATUS__', html.escape(state['message'])))


class Setup(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    # Neither request paths nor POST credentials belong in device logs.
    def log_message(self, *args):
        pass

    def reply(self, status, body, content_type='application/json'):
        payload = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def known_host(self):
        return self.headers.get('Host', '').split(':')[0].lower() in ALLOWED_HOSTS

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.known_host() or path not in ('/', '/api/networks', '/api/status', '/favicon.ico'):
            # Includes Android generate_204, Apple hotspot-detect and Windows probes.
            self.send_response(302)
            self.send_header('Location', 'http://' + ADDRESS + '/')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', '0')
            self.end_headers()
        elif path == '/api/networks':
            query = parse_qs(urlsplit(self.path).query)
            self.reply(200, self.server.portal.scan(force=query.get('refresh') == ['1']))
        elif path == '/favicon.ico':
            self.reply(204, '')
        elif path == '/api/status':
            with self.server.portal.lock:
                state = self.server.portal.state.copy()
            self.reply(200, state)
        else:
            self.reply(200, page(self.server.portal), 'text/html')

    def do_POST(self):
        try:
            if not self.known_host() or urlsplit(self.path).path not in ('/', '/connect'):
                self.reply(403, {'message': 'Open the PaperDrop setup page to connect.'})
                return
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host'):
                self.reply(403, {'message': 'Open the PaperDrop setup page to connect.'})
                return
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096:
                raise ValueError('Wi-Fi details are too long.')
            data = {key: value[0] for key, value in parse_qs(
                self.rfile.read(size).decode(), keep_blank_values=True).items()}
            if not secrets.compare_digest(data.get('token', ''), TOKEN):
                self.reply(403, {'message': 'Refresh the setup page and try again.'})
                return
            started = self.server.portal.begin_connection(data)
            if not started:
                self.reply(409, {'message': 'PaperDrop is already connecting. Please wait.'})
                return
            if 'text/html' not in self.headers.get('Accept', ''):
                self.reply(202, {'message': 'Connecting…'})
            else:
                self.reply(202, page(self.server.portal), 'text/html')
        except (ValueError, UnicodeError):
            self.reply(400, {'message': 'Check the network name, password and two-letter country code.'})


def serve(portal, ports=(80, 8080), address=ADDRESS):
    servers = []
    try:
        for port in ports:
            server = ThreadingHTTPServer((address, port), Setup)
            server.portal = portal
            server.daemon_threads = True
            servers.append(server)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        return servers
    except OSError:
        for server in servers:
            server.shutdown()
            server.server_close()
        raise


def main():
    portal = Portal()
    servers = []
    try:
        country = run('raspi-config', 'nonint', 'get_wifi_country').stdout.strip().upper()
        if valid_country(country):
            portal.country = country
        else:
            run('raspi-config', 'nonint', 'do_wifi_country', portal.country)
        # Stay alive to offer setup again after moving the device to a new location.
        while True:
            if not connected():
                time.sleep(30)  # Let saved profiles reconnect before starting setup.
                if connected():
                    continue
                portal.scan(force=True)
                portal.start_ap()
                servers = serve(portal)
                while portal.state['state'] != 'connected':
                    if portal.state['state'] != 'connecting' and connected():
                        break  # Ethernet or a saved Wi-Fi profile recovered independently.
                    if portal.state['state'] == 'failed' and portal.dns is None:
                        raise RuntimeError('Could not restore setup Wi-Fi')
                    if portal.dns is not None and portal.dns.poll() is not None:
                        raise RuntimeError('Setup DNS stopped')
                    time.sleep(2)
                portal.stop_dns()
                for server in servers:
                    server.shutdown()
                    server.server_close()
                servers = []
                run('nmcli', 'connection', 'down', PROFILE)
                portal.state = {'state': 'ready', 'message': '', 'ssid': ''}
            time.sleep(10)
    finally:
        portal.stop_dns()
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
