import asyncio
import websockets
import json
import logging
from logging.handlers import RotatingFileHandler
import time
from config import config
import subprocess
import base64
import tempfile
import os
from pathlib import Path
from device_interface import get_printer_connection
from PIL import Image
import io
import socket
from PIL import UnidentifiedImageError
try:
    from remote_shell import RemoteShell
except Exception:
    RemoteShell = None

# Logging setup
LOG_FILE = '/var/log/paperdrop/agent.log'
try:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
except:
    pass

# Configure logging to both file and console
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
try:
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5)
    file_handler.setFormatter(log_formatter)
    handlers = [file_handler, logging.StreamHandler()]
except:
    handlers = [logging.StreamHandler()]

logging.basicConfig(
    level=logging.INFO,
    handlers=handlers
)
logger = logging.getLogger('WSAgent')

# Watchdog state
connection_failures = 0
MAX_FAILURES_BEFORE_RESTART = 10
MAX_FAILURES_BEFORE_REBOOT = 30
MAX_DIAGNOSTIC_BYTES = 60000
OTA_SCRIPT = Path('/opt/paperdrop/ota-update.sh')
remote_shell = None

SAFE_COMMANDS = {
    'agent_status': ['systemctl', '--no-pager', '--full', 'status', 'paperdrop-ws-agent.service', 'paperdrop-agent.service'],
    'ble_status': ['systemctl', '--no-pager', '--full', 'status', 'paperdrop-ble.service'],
    'disk_status': ['df', '-h', '/', '/opt', '/var/log'],
    'network_status': ['sh', '-c', 'ip addr; printf "\\n--- routes ---\\n"; ip route; printf "\\n--- nmcli ---\\n"; nmcli dev status || true'],
    'printer_status': ['sh', '-c', 'lsusb || true; printf "\\n--- printer device files ---\\n"; ls -l /dev/usb /dev/bus/usb 2>/dev/null || true'],
    'wifi_status': ['sh', '-c', 'nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status || true; printf "\\n--- active wifi ---\\n"; nmcli -t -f ACTIVE,SSID,SIGNAL,SECURITY dev wifi || true'],
}

def get_health_metrics():
    """Get device health metrics like RSSI and IP."""
    metrics = {
        'ip': 'unknown',
        'rssi': None,
        'uptime': 0
    }
    try:
        # Get IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            metrics['ip'] = s.getsockname()[0]
        finally:
            s.close()
        
        # Get RSSI (if on WiFi)
        result = subprocess.run(['nmcli', '-t', '-f', 'IN-USE,SIGNAL', 'dev', 'wifi'], 
                               capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if line.startswith('*'):
                try:
                    metrics['rssi'] = int(line.split(':')[1])
                except:
                    pass
                break
                
        # Get Uptime
        try:
            with open('/proc/uptime', 'r') as f:
                metrics['uptime'] = float(f.readline().split()[0])
        except:
            pass
            
    except Exception as e:
        logger.warning(f"Failed to get health metrics: {e}")
    return metrics

def run_command(cmd, timeout=15):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            'ok': result.returncode == 0,
            'return_code': result.returncode,
            'stdout': result.stdout[-MAX_DIAGNOSTIC_BYTES:],
            'stderr': result.stderr[-MAX_DIAGNOSTIC_BYTES:]
        }
    except subprocess.TimeoutExpired as e:
        return {
            'ok': False,
            'return_code': None,
            'stdout': (e.stdout or '')[-MAX_DIAGNOSTIC_BYTES:] if isinstance(e.stdout, str) else '',
            'stderr': 'Command timed out'
        }
    except Exception as e:
        return {
            'ok': False,
            'return_code': None,
            'stdout': '',
            'stderr': str(e)
        }

def detect_agent_services():
    services = [
        'paperdrop-ws-agent.service',
        'paperdrop-agent.service',
        'paperdrop.service'
    ]
    found = []
    for service in services:
        result = subprocess.run(
            ['systemctl', 'is-enabled', service],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            found.append(service)
    return found or services[:2]

async def send_error(websocket, request_id, message):
    await websocket.send(json.dumps({
        'type': 'error',
        'request_id': request_id,
        'message': message
    }))

async def handle_fetch_logs(websocket, data):
    """Handle request to fetch logs from the device."""
    request_id = data.get('request_id')
    log_type = data.get('log_type', 'agent')
    lines = data.get('lines', 100)
    
    logger.info(f"Fetching logs: {log_type} (lines: {lines})")
    
    try:
        if log_type == 'agent':
            cmd = ['tail', '-n', str(lines), LOG_FILE]
        elif log_type == 'system':
            cmd = ['sudo', 'journalctl', '-n', str(lines), '--no-pager']
        elif log_type == 'provisioning':
            cmd = ['sudo', 'journalctl', '-u', 'paperdrop-ble', '-n', str(lines), '--no-pager']
        else:
            cmd = ['tail', '-n', str(lines), LOG_FILE]
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        await websocket.send(json.dumps({
            'type': 'log_bundle',
            'request_id': request_id,
            'log_type': log_type,
            'content': result.stdout
        }))
    except Exception as e:
        logger.error(f"Failed to fetch logs: {e}")
        await websocket.send(json.dumps({
            'type': 'error',
            'request_id': request_id,
            'message': f"Failed to fetch logs: {str(e)}"
        }))

async def handle_test_print(websocket, data):
    request_id = data.get('request_id')
    logger.info("Processing test print request")

    try:
        p = get_printer_connection()
        if not p:
            raise Exception("Printer not connected")

        p.set(align='center', font='b')
        p.text("PaperDrop test print\n")
        p.set(align='left', font='a')
        p.text(f"Device: {config.device_code}\n")
        p.text(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n\n")
        p.cut()

        await websocket.send(json.dumps({
            'type': 'test_print_result',
            'request_id': request_id,
            'ok': True
        }))
    except Exception as e:
        logger.error(f"Test print failed: {e}")
        await websocket.send(json.dumps({
            'type': 'test_print_result',
            'request_id': request_id,
            'ok': False,
            'error': str(e)
        }))
    finally:
        if 'p' in locals() and p:
            try:
                p.close()
            except Exception as e:
                logger.warning(f"Error closing printer after test print: {e}")

async def handle_collect_diagnostics(websocket, data):
    request_id = data.get('request_id')
    logger.info("Collecting diagnostics")

    sections = []
    sections.append(("health_metrics", json.dumps(get_health_metrics(), indent=2)))

    diagnostic_commands = {
        'hostname': ['hostname'],
        'kernel': ['uname', '-a'],
        'uptime': ['uptime'],
        'memory': ['free', '-h'],
        'disk': ['df', '-h', '/', '/opt', '/var/log'],
        'network': ['sh', '-c', 'ip addr; printf "\\n--- routes ---\\n"; ip route'],
        'wifi': SAFE_COMMANDS['wifi_status'],
        'usb': SAFE_COMMANDS['printer_status'],
        'services': ['systemctl', '--no-pager', '--full', 'status', 'paperdrop-ws-agent.service', 'paperdrop-agent.service', 'paperdrop-ble.service'],
        'agent_logs': ['sh', '-c', 'journalctl -u paperdrop-ws-agent.service -u paperdrop-agent.service -n 160 --no-pager 2>/dev/null || tail -n 160 /var/log/paperdrop/agent.log'],
        'ble_logs': ['journalctl', '-u', 'paperdrop-ble.service', '-n', '80', '--no-pager']
    }

    for name, cmd in diagnostic_commands.items():
        result = run_command(cmd, timeout=12)
        body = result['stdout']
        if result['stderr']:
            body += f"\n[stderr]\n{result['stderr']}"
        sections.append((name, body.strip()))

    content = "\n\n".join(f"===== {name} =====\n{body}" for name, body in sections)
    await websocket.send(json.dumps({
        'type': 'diagnostics_result',
        'request_id': request_id,
        'content': content[-MAX_DIAGNOSTIC_BYTES:]
    }))

async def handle_run_command(websocket, data):
    request_id = data.get('request_id')
    command = data.get('command')
    logger.info(f"Processing remote command request: {command}")

    if command == 'restart_agent':
        await websocket.send(json.dumps({
            'type': 'command_result',
            'request_id': request_id,
            'command': command,
            'ok': True,
            'stdout': 'Agent restart scheduled',
            'stderr': ''
        }))
        asyncio.get_running_loop().call_later(1.0, lambda: os._exit(0))
        return

    if command == 'restart_network':
        result = run_command(['systemctl', 'restart', 'NetworkManager'], timeout=20)
    elif command == 'reboot':
        await websocket.send(json.dumps({
            'type': 'command_result',
            'request_id': request_id,
            'command': command,
            'ok': True,
            'stdout': 'Reboot scheduled',
            'stderr': ''
        }))
        subprocess.Popen(['reboot'], start_new_session=True)
        return
    elif command in SAFE_COMMANDS:
        result = run_command(SAFE_COMMANDS[command], timeout=20)
    else:
        result = {
            'ok': False,
            'return_code': None,
            'stdout': '',
            'stderr': f"Unsupported command: {command}"
        }

    await websocket.send(json.dumps({
        'type': 'command_result',
        'request_id': request_id,
        'command': command,
        **result
    }))

async def handle_set_config(websocket, data):
    request_id = data.get('request_id')
    cloud_ws_url = data.get('cloud_ws_url')
    restart = data.get('restart', True)

    if cloud_ws_url:
        if not isinstance(cloud_ws_url, str) or not cloud_ws_url.startswith(('wss://', 'ws://')):
            await send_error(websocket, request_id, 'cloud_ws_url must start with ws:// or wss://')
            return
        config.save_runtime_config({'cloud_ws_url': cloud_ws_url})

    await websocket.send(json.dumps({
        'type': 'config_updated',
        'request_id': request_id,
        'cloud_ws_url': config.cloud_ws_url,
        'restart': restart
    }))

    if restart:
        asyncio.get_running_loop().call_later(1.0, lambda: os._exit(0))

async def handle_update(websocket, data):
    request_id = data.get('request_id')
    version = str(data.get('version') or '')
    url = str(data.get('url') or '')
    checksum = str(data.get('sha256') or data.get('checksum') or '')

    if url and not url.startswith(('https://', 'http://')):
        await send_error(websocket, request_id, 'Update URL must be http:// or https://')
        return

    script = OTA_SCRIPT if OTA_SCRIPT.exists() else Path(__file__).with_name('ota-update.sh')
    if not script.exists():
        await send_error(websocket, request_id, f'OTA script not found at {OTA_SCRIPT}')
        return

    await websocket.send(json.dumps({
        'type': 'update_status',
        'request_id': request_id,
        'status': 'accepted',
        'version': version
    }))

    log_path = '/var/log/paperdrop/ota.log'
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, 'a') as log_file:
        subprocess.Popen(
            [str(script), url, version, checksum],
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )

    logger.info(f"OTA update started for version {version or 'latest'}")

async def handle_start_shell(websocket, data):
    global remote_shell

    if RemoteShell is None:
        await websocket.send(json.dumps({
            'type': 'shell_output',
            'data': 'Remote shell support is not installed on this device.\n'
        }))
        return

    async def send_output(output):
        await websocket.send(json.dumps({
            'type': 'shell_output',
            'data': output
        }))

    if remote_shell:
        remote_shell.stop()

    remote_shell = RemoteShell(send_output)
    payload = data.get('payload') or {}
    cols = int(data.get('cols') or payload.get('cols') or 80)
    rows = int(data.get('rows') or payload.get('rows') or 24)
    remote_shell.start(cols=cols, rows=rows)
    await websocket.send(json.dumps({
        'type': 'shell_output',
        'data': f'PaperDrop remote shell started on {config.device_code}\\n'
    }))

async def handle_shell_input(data):
    if remote_shell:
        remote_shell.write(str(data.get('data') or ''))

async def handle_resize_shell(data):
    if remote_shell:
        payload = data.get('payload') or {}
        cols = int(data.get('cols') or payload.get('cols') or 80)
        rows = int(data.get('rows') or payload.get('rows') or 24)
        remote_shell.resize(cols, rows)

async def handle_stop_shell():
    global remote_shell

    if remote_shell:
        remote_shell.stop()
        remote_shell = None

from PIL import Image, ImageDraw, ImageFont

def add_watermark(img, text):
    """Adds a subtle watermark to the bottom-right of an image."""
    try:
        # Convert to RGBA to allow for some drawing operations if needed, 
        # but thermal printers are 1-bit, so we'll eventually be back to 1-bit.
        # Most images coming in are already RGB or L.
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        draw = ImageDraw.Draw(img)
        
        # Try to load a font, fall back to default
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, 12)
                    break
                except:
                    continue
        
        if font is None:
            font = ImageFont.load_default()
            
        # Calculate position (bottom right)
        try:
            # PIL 9.2.0+
            bbox = draw.textbbox((0, 0), text, font=font)
            textwidth = bbox[2] - bbox[0]
            textheight = bbox[3] - bbox[1]
        except AttributeError:
            # Older PIL
            textwidth, textheight = draw.textsize(text, font=font)
            
        width, height = img.size
        margin = 4
        x = width - textwidth - margin
        y = height - textheight - margin
        
        # Draw main text (no background for minimal impact)
        draw.text((x, y), text, font=font, fill="black")
        
        return img
    except Exception as e:
        logger.error(f"Failed to add watermark: {e}")
        return img

async def handle_print_job(websocket, message_data):
    msg = message_data.get('message', {})
    msg_id = msg.get('id')
    content = msg.get('content')
    content_type = msg.get('contentType')
    sender_name = msg.get('senderName', 'Unknown')

    logger.info(f"Processing print job {msg_id} ({content_type}) from {sender_name}")

    # Update status to printing
    await websocket.send(json.dumps({
        'type': 'print_status',
        'message_id': msg_id,
        'status': 'printing'
    }))

    try:
        p = get_printer_connection()
        if not p:
            raise Exception("Printer not connected")

        if content_type == 'text':
            text_body = content.get('body', '') if isinstance(content, dict) else str(content)
            logger.info(f"Printing text: {text_body[:50]}...")
            p.text(text_body + "\n\n")
            
            # Add attribution footer
            p.set(align='right', font='b')
            p.text(f"Sent by {sender_name}\n")
            p.set(align='left', font='a') # Reset
            
            p.cut()

        elif content_type == 'image':
            # Handle image (assume base64)
            image_data = content
            if isinstance(content, dict):
                image_data = content.get('image') or content.get('content') or ""

            if not image_data or not isinstance(image_data, str):
                raise Exception("No image data provided for print job")
            
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            try:
                img_bytes = base64.b64decode(image_data, validate=True)
            except (ValueError, TypeError) as e:
                raise Exception(f"Invalid image data: {e}")

            try:
                img = Image.open(io.BytesIO(img_bytes))
            except UnidentifiedImageError as e:
                raise Exception(f"Invalid image format: {e}")

            # Keep image input stable for the ESC/POS image routine.
            img = img.convert('RGB')
            
            # Resize to printer width (576px for 80mm at 203 DPI)
            # This ensures WYSIWYG consistency with the frontend canvas
            PRINTER_WIDTH = 576
            if img.width != PRINTER_WIDTH:
                aspect_ratio = img.height / img.width
                new_height = int(PRINTER_WIDTH * aspect_ratio)
                img = img.resize((PRINTER_WIDTH, new_height), Image.Resampling.LANCZOS)
                logger.info(f"Resized image to {PRINTER_WIDTH}x{new_height}")

            # Prevent very tall images from overloading the printer image command path.
            MAX_HEIGHT = 2400
            if img.height > MAX_HEIGHT:
                img = img.resize((PRINTER_WIDTH, MAX_HEIGHT), Image.Resampling.LANCZOS)
                logger.warning(f"Image too tall. Resized to {PRINTER_WIDTH}x{MAX_HEIGHT}")

            # Convert to 1-bit early; avoids several image-encoding crash paths.
            img = img.convert('1')
            
            # Apply watermark
            watermark_text = f"Sent by {sender_name}"
            img = add_watermark(img, watermark_text)
            
            logger.info(f"Printing image: {img.size}")
            # ESC/POS image printing
            p.image(img, impl='bitImageRaster')
            p.cut()

        # Update status to printed
        await websocket.send(json.dumps({
            'type': 'print_status',
            'message_id': msg_id,
            'status': 'printed'
        }))
        logger.info(f"Print job {msg_id} completed successfully")

    except Exception as e:
        logger.error(f"Print failed: {e}")
        await websocket.send(json.dumps({
            'type': 'print_status',
            'message_id': msg_id,
            'status': 'failed',
            'error': str(e)
        }))
    finally:
        if 'p' in locals() and p:
            try:
                p.close()
                logger.info("Printer connection closed")
            except Exception as e:
                logger.warning(f"Error closing printer: {e}")

async def connect_to_backend():
    global connection_failures
    # Ensure config is initialized (loads device info)
    config.initialize()
    
    device_code = config.device_code
    device_secret = config.device_secret
    base_ws_url = config.cloud_ws_url

    if not device_code:
        logger.error("No device code found. Exiting.")
        return

    import urllib.parse
    # Use query parameters for authentication
    encoded_code = urllib.parse.quote(device_code)
    encoded_secret = urllib.parse.quote(device_secret)
    ws_url = f"{base_ws_url}?deviceCode={encoded_code}&deviceSecret={encoded_secret}"

    logger.info(f"Starting WebSocket agent for device: {device_code}")
    logger.info(f"Connecting to: {base_ws_url}")
    
    while True:
        try:
            logger.info(f"Connecting to WebSocket: {ws_url}")
            async with websockets.connect(ws_url) as websocket:
                logger.info("Handshake successful! Connected to backend.")
                connection_failures = 0 # Reset failures on success
                
                # Start background listener
                async def listen():
                    try:
                        async for message in websocket:
                            logger.info(f"Received from backend: {message}")
                            try:
                                data = json.loads(message)
                                if data.get('type') == 'ping':
                                    await websocket.send(json.dumps({'type': 'pong'}))
                                elif data.get('type') == 'new_message':
                                    await handle_print_job(websocket, data)
                                elif data.get('type') == 'test_print':
                                    await handle_test_print(websocket, data)
                                elif data.get('type') == 'fetch_logs':
                                    await handle_fetch_logs(websocket, data)
                                elif data.get('type') == 'collect_diagnostics':
                                    await handle_collect_diagnostics(websocket, data)
                                elif data.get('type') == 'run_command':
                                    await handle_run_command(websocket, data)
                                elif data.get('type') == 'set_config':
                                    await handle_set_config(websocket, data)
                                elif data.get('type') == 'update':
                                    await handle_update(websocket, data)
                                elif data.get('type') == 'start_shell':
                                    await handle_start_shell(websocket, data)
                                elif data.get('type') == 'shell_input':
                                    await handle_shell_input(data)
                                elif data.get('type') == 'resize_shell':
                                    await handle_resize_shell(data)
                                elif data.get('type') == 'stop_shell':
                                    await handle_stop_shell()
                                elif data.get('type') == 'error':
                                    logger.error(f"Backend error: {data.get('message')}")
                                elif data.get('type') == 'test_connection':
                                    logger.info("Received connection test request")
                                    await websocket.send(json.dumps({'type': 'test_response', 'status': 'ok'}))
                                elif data.get('type') == 'reboot':
                                    logger.info("Received reboot request")
                                    subprocess.run(['sudo', 'reboot'])
                                elif data.get('type') == 'restart_service':
                                    logger.info("Received service restart request")
                                    os._exit(0)
                            except json.JSONDecodeError:
                                logger.warning(f"Received non-JSON message: {message}")
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.warning(f"Connection closed in listener: Code={e.code}, Reason={e.reason}")
                    except Exception as e:
                        logger.error(f"Error in listener: {e}")
                    finally:
                        await handle_stop_shell()

                # Start heartbeat loop
                async def heartbeat():
                    while True:
                        try:
                            metrics = get_health_metrics()
                            await websocket.send(json.dumps({
                                'type': 'heartbeat',
                                'firmware_version': config.firmware_version,
                                'metrics': metrics
                            }))
                            logger.info("Heartbeat sent")
                        except Exception as e:
                            logger.error(f"Failed to send heartbeat: {e}")
                            break
                        await asyncio.sleep(30)

                listener_task = asyncio.create_task(listen())
                heartbeat_task = asyncio.create_task(heartbeat())

                # Send initial hello
                logger.info("Sending device_hello...")
                metrics = get_health_metrics()
                await websocket.send(json.dumps({
                    'type': 'device_hello',
                    'firmware_version': config.firmware_version,
                    'metrics': metrics
                }))

                # Wait for either task to finish
                done, pending = await asyncio.wait(
                    [listener_task, heartbeat_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in pending:
                    task.cancel()
                        
        except Exception as e:
            connection_failures += 1
            logger.error(f"Connection error ({connection_failures}/{MAX_FAILURES_BEFORE_REBOOT}): {type(e).__name__}: {e}")
            
            if connection_failures >= MAX_FAILURES_BEFORE_REBOOT:
                logger.critical("Too many connection failures. Rebooting device...")
                subprocess.run(['sudo', 'reboot'])
            elif connection_failures >= MAX_FAILURES_BEFORE_RESTART:
                logger.warning("Multiple connection failures. Restarting NetworkManager...")
                subprocess.run(['sudo', 'systemctl', 'restart', 'NetworkManager'])
            
            wait_time = min(30, 5 + connection_failures)
            logger.info(f"Reconnecting in {wait_time}s...")
            await asyncio.sleep(wait_time)

if __name__ == "__main__":
    try:
        asyncio.run(connect_to_backend())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
