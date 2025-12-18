import asyncio
import websockets
import json
import logging
import time
from config import config
import subprocess
import base64
import tempfile
import os
from device_interface import get_printer_connection
from PIL import Image
import io

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('WSAgent')

async def handle_print_job(websocket, message_data):
    msg = message_data.get('message', {})
    msg_id = msg.get('id')
    content = msg.get('content')
    content_type = msg.get('contentType')

    logger.info(f"Processing print job {msg_id} ({content_type})")

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
            p.text(text_body + "\n")
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

async def connect_to_backend():
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
            async with websockets.connect(ws_url) as websocket:
                logger.info("Connected to backend!")
                
                # Wait a bit before sending hello to ensure backend is ready
                await asyncio.sleep(1)
                
                # Send initial hello/heartbeat
                logger.info("Sending device_hello...")
                try:
                    await websocket.send(json.dumps({
                        'type': 'device_hello',
                        'firmware_version': config.firmware_version,
                        'mac_address': 'unknown' 
                    }))
                except Exception as e:
                    logger.error(f"Failed to send device_hello: {e}")
                    raise
                
                # Keep connection alive and handle messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        logger.info(f"Received message type: {data.get('type')}")
                        
                        # Handle specific message types
                        if data.get('type') == 'ping':
                            await websocket.send(json.dumps({'type': 'pong'}))
                        elif data.get('type') == 'new_message':
                            await handle_print_job(websocket, data)
                        elif data.get('type') == 'error':
                            logger.error(f"Backend error: {data.get('message')}")
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Received non-JSON message: {message}")
                        
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Connection closed by server: Code={e.code}, Reason='{e.reason}'. Reconnecting in 5s...")
            await asyncio.sleep(5)
        except (OSError, Exception) as e:
            logger.error(f"Connection error: {type(e).__name__}: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(connect_to_backend())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")

