import asyncio
import websockets
import json
import logging
import time
from config import config

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('WSAgent')

async def connect_to_backend():
    # Ensure config is initialized (loads device info)
    config.initialize()
    
    device_code = config.device_code
    device_secret = config.device_secret
    ws_url = config.cloud_ws_url

    if not device_code:
        logger.error("No device code found. Exiting.")
        return

    headers = {
        'x-device-code': device_code,
        'x-device-secret': device_secret
    }

    logger.info(f"Starting WebSocket agent for device: {device_code}")
    logger.info(f"Connecting to: {ws_url}")
    
    while True:
        try:
            # In websockets 14.0+, connect() can be used as an infinite iterator for auto-reconnect
            # But for compatibility and explicit control, we'll use a loop
            async with websockets.connect(ws_url, additional_headers=headers) as websocket:
                logger.info("Connected to backend!")
                
                # Send initial hello/heartbeat
                await websocket.send(json.dumps({
                    'type': 'device_hello',
                    'firmware_version': config.firmware_version,
                    'mac_address': 'unknown' # TODO: Get actual MAC
                }))
                
                # Keep connection alive and handle messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        logger.info(f"Received message: {data}")
                        
                        # Handle specific message types
                        if data.get('type') == 'ping':
                            await websocket.send(json.dumps({'type': 'pong'}))
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Received non-JSON message: {message}")
                        
        except (websockets.ConnectionClosed, OSError) as e:
            logger.warning(f"Connection lost: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(connect_to_backend())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
