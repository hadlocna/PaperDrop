import asyncio
import json
import logging
import websockets
import os
import time
from config import config
from print_handler import print_handler

# Configuration
API_URL = os.environ.get('API_URL', 'ws://localhost:3000/api/device/connect')
# In production, this might be wss://api.paperdrop.com/api/device/connect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PaperDropAgent")

class Agent:
    def __init__(self):
        self.connected = False
        config.initialize()
        
    async def connect(self):
        headers = {
            "X-Device-Code": config.device_code,
            "X-Device-Secret": config.device_secret
        }
        
        logger.info(f"Connecting to {API_URL} as {config.device_code}")
        
        while True:
            try:
                async with websockets.connect(API_URL, extra_headers=headers) as websocket:
                    logger.info("✅ Connected to Cloud")
                    self.connected = True
                    
                    # Send any initial status if needed
                    
                    while True:
                        try:
                            message = await websocket.recv()
                            data = json.loads(message)
                            logger.info(f"📩 Received: {data.get('type')}")
                            
                            await self.handle_message(websocket, data)
                            
                        except websockets.ConnectionClosed:
                            logger.warning("Connection closed by server")
                            self.connected = False
                            break
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.connected = False
                logger.info("Retrying in 5s...")
                await asyncio.sleep(5)

    async def handle_message(self, websocket, data):
        msg_type = data.get('type')
        
        if msg_type == 'print_job' or msg_type == 'new_message':
            # Handle print
            logger.info("🖨️ Printing job...")
            
            try:
                # Acknowledge receipt/processing
                if data.get('message_id'):
                    await websocket.send(json.dumps({
                        "type": "print_status",
                        "message_id": data['message_id'],
                        "status": "printing"
                    }))

                # Print Logic
                content_type = data.get('content_type', 'text')
                content_body = data.get('message', {}).get('content') # Structure varies slightly in my backend vs simple mock
                # The backend sends: 
                # { type: 'new_message', message: { id, content, contentType ... } } (broadcastToDevice in messageController)
                # OR { type: 'print_job', ... } (scheduled)
                
                # Normalize
                msg_obj = data.get('message') if 'message' in data else data
                
                if content_type == 'image':
                    print_handler.print_image(msg_obj.get('content'))
                else:
                     print_handler.print_message(msg_obj)
                
                # Success
                logger.info("✅ Print Complete")
                if data.get('message_id') or msg_obj.get('id'):
                     mid = data.get('message_id') or msg_obj.get('id')
                     await websocket.send(json.dumps({
                        "type": "print_status",
                        "message_id": mid,
                        "status": "printed"
                    }))
            
            except Exception as e:
                logger.error(f"Print failed: {e}")
                if data.get('message_id') or msg_obj.get('id'):
                     mid = data.get('message_id') or msg_obj.get('id')
                     await websocket.send(json.dumps({
                        "type": "print_status",
                        "message_id": mid,
                        "status": "failed",
                        "error": str(e)
                    }))

        elif msg_type == 'claimed':
             logger.info("🎉 Device Claimed!")
             print_handler.print_text("Device Claimed!\nWelcome to PaperDrop.")

        elif msg_type == 'test_print':
             logger.info("Testing print...")
             print_handler.print_text("Test Print Successful!\nPaperDrop is Online.")

    def run(self):
        # In a real Pi implementation, we check for WiFi.
        # If no WiFi, start wifi_setup.start_setup_server() (blocking or separate thread)
        # For now, we assume WiFi/Network is available (dev mode).
        
        logger.info("Starting PaperDrop Agent...")
        logger.info(f"Device Identity: {config.device_code}")
        
        # Print startup slip
        print_handler.print_text(f"PaperDrop Online\nCode: {config.device_code}\n")
        
        try:
            asyncio.run(self.connect())
        except KeyboardInterrupt:
            logger.info("Stopping...")

if __name__ == "__main__":
    agent = Agent()
    agent.run()
