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
from device_interface import get_printer_connection
from PIL import Image
import io
import socket

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
                    font = ImageFont.truetype(path, 18)
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
        margin = 10
        x = width - textwidth - margin
        y = height - textheight - margin
        
        # Draw a small white rectangle behind the text for legibility on dark backgrounds
        draw.rectangle([x-2, y-2, x+textwidth+2, y+textheight+2], fill="white")
        
        # Draw main text
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
            
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            img_bytes = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_bytes))
            
            # Apply watermark
            watermark_text = f"Sent by {sender_name}"
            img = add_watermark(img, watermark_text)
            
            logger.info(f"Printing image: {img.size}")
            # ESC/POS image printing
            p.image(img)
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
                                elif data.get('type') == 'fetch_logs':
                                    await handle_fetch_logs(websocket, data)
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
