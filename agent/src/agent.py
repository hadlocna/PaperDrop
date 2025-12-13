#!/usr/bin/env python3
"""
PaperDrop Device Agent
Runs on Raspberry Pi, manages WiFi setup, cloud connection, and printing.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosed

from config import Config
from wifi_setup import WiFiSetupServer
from print_handler import print_handler # Use the singleton instance

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('paperdrop')


class DeviceState(Enum):
    """Device operating states"""
    WIFI_SETUP = "wifi_setup"       # AP mode, waiting for WiFi config (No Creds)
    CONNECTING = "connecting"       # Trying to connect to home WiFi
    ONLINE = "online"               # Connected to cloud, ready
    OFFLINE = "offline"             # Has WiFi but can't reach cloud
    FALLBACK_HOTSPOT = "fallback"   # Has Creds, but failed. AP Mode + Periodic Retry


# ─────────────────────────────────────────────────────────────────────
# MAIN AGENT CLASS
# ─────────────────────────────────────────────────────────────────────

class PaperDropAgent:
    """
    Main agent that orchestrates WiFi setup, cloud connection, and printing.
    """
    
    def __init__(self):
        self.config = Config()
        self.state = DeviceState.WIFI_SETUP
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.print_handler = print_handler # Use singleton
        self.wifi_setup = WiFiSetupServer(self.config, self.on_wifi_configured)
        self.running = True
        self.reconnect_delay = 5  # Start with 5 second reconnect delay
        self.max_reconnect_delay = 60  # Max 60 seconds between attempts
        
    async def run(self):
        """Main entry point - runs the agent forever"""
        logger.info(f"PaperDrop Agent starting - Device: {self.config.device_code}")
        
        # Set up signal handlers for graceful shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop = asyncio.get_running_loop()
                loop.add_signal_handler(
                    sig, lambda: asyncio.create_task(self.shutdown())
                )
            except NotImplementedError:
                # Windows/Non-Unix support if needed
                pass
        
        # Initialize printer connection (Note: print_handler does this in init)
        # We can simulate a startup print
        if os.environ.get("PAPERDROP_ENV") != "development":
             # Only print connection status on real boot or integration test, 
             # not every time code reloads in dev
             pass
        
        # ─────────────────────────────────────────────────────────────
        # LAYER 1 BYPASS: DEVELOPMENT MODE
        # ─────────────────────────────────────────────────────────────
        if os.environ.get("PAPERDROP_ENV") == "development":
            logger.warning("⚠️ DEVELOPMENT MODE DETECTED: Skipping WiFi Setup checks.")
            logger.info("Force-entering ONLINE mode...")
            await self.run_online_mode()
            return

        # Main loop (Layer 2 / Production)
        self.connection_start_time = 0
        self.next_retry_time = 0
        
        while self.running:
            try:
                # ─────────────────────────────────────────────────────────
                # STATE: ONLINE
                # ─────────────────────────────────────────────────────────
                if self.state == DeviceState.ONLINE:
                    await self.run_online_mode()
                    # If returns, we disconnected. Try to reconnect.
                    self.state = DeviceState.CONNECTING
                    self.connection_start_time = datetime.now().timestamp()
                
                # ─────────────────────────────────────────────────────────
                # STATE: WIFI SETUP (No Credentials)
                # ─────────────────────────────────────────────────────────
                elif self.state == DeviceState.WIFI_SETUP:
                    # Check if we actually have creds (maybe added manually)
                    if self.config.has_wifi_credentials():
                        self.state = DeviceState.CONNECTING
                        self.connection_start_time = datetime.now().timestamp()
                        continue
                        
                    logger.info("No WiFi credentials. Entering Setup Mode.")
                    # Run AP until user provides creds (callback changes state)
                    await self.run_wifi_setup_mode()

                # ─────────────────────────────────────────────────────────
                # STATE: CONNECTING
                # ─────────────────────────────────────────────────────────
                elif self.state == DeviceState.CONNECTING:
                    if not self.connection_start_time:
                         self.connection_start_time = datetime.now().timestamp()
                    
                    # Try to connect
                    success = await self.connect_to_home_wifi()
                    if success:
                        logger.info("WiFi Connected! Keeping AP alive for 60s to show Success Page...")
                        # Allow time for UI on the AP to update and user to see "Connected" and the Code
                        await asyncio.sleep(60) 
                        await self.wifi_setup.stop()
                        
                        self.state = DeviceState.ONLINE
                        self.connection_start_time = 0 # Reset
                    else:
                        # Connection Failed
                        # Check if we have exceeded 5 minutes
                        elapsed = datetime.now().timestamp() - self.connection_start_time
                        if elapsed > 300: # 5 Minutes
                            logger.warning(f"Connection failed for {int(elapsed)}s. Switching to FALLBACK HOTSPOT.")
                            self.state = DeviceState.FALLBACK_HOTSPOT
                            self.next_retry_time = datetime.now().timestamp() + 600 # 10 Minutes
                        else:
                            # Wait a bit before retrying to avoid spamming
                            logger.info("Retrying connection in 5s...")
                            await asyncio.sleep(5)

                # ─────────────────────────────────────────────────────────
                # STATE: FALLBACK HOTSPOT
                # ─────────────────────────────────────────────────────────
                elif self.state == DeviceState.FALLBACK_HOTSPOT:
                    logger.info("Entering Fallback Hotspot Mode.")
                    
                    # 1. Start AP
                    await self.wifi_setup.start()
                    
                    # 2. Loop until Time to Retry OR User Configured
                    while self.state == DeviceState.FALLBACK_HOTSPOT and self.running:
                        remaining = self.next_retry_time - datetime.now().timestamp()
                        
                        if remaining <= 0:
                            logger.info("10 Minute Timer Expired. Retrying saved network...")
                            break # Break loop to retry
                        
                        # Sleep briefly to allow interruptions/state changes
                        await asyncio.sleep(1)
                    
                    # 3. Stop AP
                    await self.wifi_setup.stop()
                    
                    # 4. Decide next step
                    if self.state == DeviceState.FALLBACK_HOTSPOT:
                        # Timer expired, try connecting ONCE
                        logger.info("Attempting periodic reconnection...")
                        success = await self.connect_to_home_wifi()
                        if success:
                             self.state = DeviceState.ONLINE
                             self.connection_start_time = 0
                        else:
                             # Failed. Reset Timer and go back to AP loop
                             logger.info("Reconnect failed. Resuming Fallback Hotspot.")
                             self.next_retry_time = datetime.now().timestamp() + 600 # 10 Minutes
                    
                    # If state changed (e.g. to CONNECTING via callback), the main loop handles it
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down...")
        self.running = False
        if self.websocket:
            await self.websocket.close()
        # self.print_handler.disconnect() # Handled by GC/exit usually
    
    # ─────────────────────────────────────────────────────────────────
    # WIFI SETUP MODE
    # ─────────────────────────────────────────────────────────────────
    
    async def run_wifi_setup_mode(self):
        """
        Start AP mode and run captive portal for WiFi configuration.
        Blocks until WiFi is successfully configured.
        """
        self.state = DeviceState.WIFI_SETUP
        logger.info("Entering WiFi setup mode")
        
        # Print setup instructions
        self.print_handler.print_text("SETUP MODE ACTIVE\nConnect to 'PaperDrop' WiFi")
        
        # Start the WiFi setup server (AP + captive portal)
        # This will block until WiFi is configured and verified
        await self.wifi_setup.start()
        
        # In spec this blocks? create_task in wifi_setup suggests it runs server.
        # We need to wait here or the loop continues.
        # For simplicity in this async structure, we'll wait for a flag or event.
        while self.state == DeviceState.WIFI_SETUP and self.running:
            await asyncio.sleep(1)

        # CRITICAL: Do NOT stop AP if we are transitioning to CONNECTING.
        # We need the AP alive so the UI can poll and show "Connected!".
        if self.state != DeviceState.CONNECTING:
            await self.wifi_setup.stop()
    
    async def on_wifi_configured(self, ssid: str, password: str):
        """
        Callback when user submits WiFi credentials via captive portal.
        """
        logger.info(f"WiFi credentials received for network: {ssid}")
        
        # Save credentials
        self.config.save_wifi_credentials(ssid, password)
        
        logger.info("Credentials saved. Waiting 15s before switching networks to allow UI to render...")
        await asyncio.sleep(15) # Give the user time to read the success page
        
        # Change state to trigger loop update
        self.state = DeviceState.CONNECTING
    
    async def connect_to_home_wifi(self) -> bool:
        """
        Attempt to connect to the saved home WiFi network.
        Returns True on success, False on failure.
        """
        self.state = DeviceState.CONNECTING
        logger.info("Checking for existing WiFi connection...")
        
        # 1. OPTIMIZATION: Check if already connected (e.g. by OS Headless Setup)
        if await self.is_wifi_connected():
            logger.info("Already connected to WiFi! Skipping reconfiguration.")
            return True

        logger.info("Attempting to connect to home WiFi...")
        
        # Apply WiFi credentials to wpa_supplicant and restart
        success = await self.wifi_setup.apply_wifi_credentials()
        
        if not success:
            return False
        
        # Wait for connection with timeout
        for i in range(30):  # 30 second timeout
            if await self.is_wifi_connected():
                logger.info("WiFi connected!")
                return True
            await asyncio.sleep(1)
        
        logger.error("WiFi connection timeout")
        return False
    
    async def is_wifi_connected(self) -> bool:
        """Check if we have a WiFi connection with internet access"""
        try:
            # Check if wlan0 has an IP
            proc = await asyncio.create_subprocess_shell(
                'ip -4 addr show wlan0 | grep -oP "(?<=inet\\s)\\d+(\\.\\d+){3}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            ip = stdout.decode().strip()
            
            if not ip or ip.startswith('192.168.4.'):  # AP mode IP
                return False
            
            # Try to reach the internet
            # In Layer 2 Integration, the 'ip' mock might behave differently or we mock ping
            # For now, simplistic check
            return True
            
        except Exception as e:
            logger.error(f"Error checking WiFi: {e}")
            return False
    
    def get_local_ip(self) -> str:
        """Get the device's local IP address"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Doesn't actually connect, just gets potential route interface
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    # ─────────────────────────────────────────────────────────────────
    # ONLINE MODE (Connected to Cloud)
    # ─────────────────────────────────────────────────────────────────
    
    async def run_online_mode(self):
        """
        Main operating mode - connected to cloud, listening for print jobs.
        """
        self.reconnect_delay = 5  # Reset reconnect delay on successful connection
        
        logger.info(f"Starting ONLINE mode. Cloud URL: {self.config.cloud_ws_url}")

        while self.running:
            try:
                await self.connect_to_cloud()
                self.state = DeviceState.ONLINE
                
                # If we return from connect_to_cloud, it means connection closed cleanly or we logic'd out
                # Usually listen_for_messages runs until error
                
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                self.state = DeviceState.OFFLINE
                
            except Exception as e:
                logger.error(f"Error in online mode: {e}")
                self.state = DeviceState.OFFLINE
            
            # Reconnect with exponential backoff
            if self.running:
                logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(
                    self.reconnect_delay * 1.5, 
                    self.max_reconnect_delay
                )
    
    async def connect_to_cloud(self):
        """Establish WebSocket connection to PaperDrop cloud"""
        logger.info("Connecting to cloud...")
        
        self.websocket = await websockets.connect(
            self.config.cloud_ws_url,
            additional_headers={
                "X-Device-Code": self.config.device_code,
                "X-Device-Secret": self.config.device_secret,
            },
            ping_interval=30,
            ping_timeout=10,
        )
        
        self.reconnect_delay = 5  # Reset on successful connection
        
        # Send hello message
        await self.websocket.send(json.dumps({
            "type": "device_hello",
            "device_code": self.config.device_code,
            "firmware_version": self.config.firmware_version,
            "local_ip": self.get_local_ip(),
            "printer_status": {"connected": True}, # Mock status
        }))
        
        logger.info("Connected to cloud!")
        await self.listen_for_messages()
    
    async def listen_for_messages(self):
        """Listen for incoming messages from cloud"""
        async for raw_message in self.websocket:
            try:
                message = json.loads(raw_message)
                await self.handle_cloud_message(message)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from cloud: {e}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
    
    async def handle_cloud_message(self, message: dict):
        """Route incoming cloud messages to appropriate handlers"""
        # Support both 'print_job' (Spec) and 'new_message' (Current Backend Implementation)
        msg_type = message.get("type")
        
        logger.info(f"Received message type: {msg_type}")

        if msg_type == "print_job" or msg_type == "new_message":
            await self.handle_print_job(message)
        
        elif msg_type == "ping":
            await self.websocket.send(json.dumps({"type": "pong"}))
        
        elif msg_type == "claimed":
            owner_name = message.get("owner_name", "Someone")
            self.print_handler.print_text(
                f"Obtained by {owner_name}!\n\nREADY."
            )
        
        elif msg_type == "test_print":
            self.print_handler.print_text(
                f"Test Print\n{datetime.now()}"
            )
            await self.report_print_status(message.get("request_id"), "printed")
        
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    # ─────────────────────────────────────────────────────────────────
    # PRINT JOB HANDLING
    # ─────────────────────────────────────────────────────────────────
    
    async def handle_print_job(self, job: dict):
        """
        Process and print a message from the cloud.
        """
        # Backend sends { type: 'new_message', message: { ... } }
        # Spec sends { type: 'print_job', content: { ... } }
        # We need to normalize
        
        if 'message' in job:
            # Backend format
            msg_obj = job['message']
            message_id = msg_obj.get('id')
            content_type = msg_obj.get('contentType', 'text')
            
            # Content might be a JSON string or object depending on parsing
            content = msg_obj.get('content')
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except:
                    pass # Keep as string if text
            
            # If backend sends just string for content (legacy), wrap it
            if isinstance(content, str) and content_type == 'text':
                content = { 'body': content }

        else:
            # Spec format
            message_id = job.get("message_id")
            content_type = job.get("content_type")
            content = job.get("content", {})
        
        sender_name = job.get("sender_name", "Unknown") # Spec
        if 'message' in job and 'sender' in job['message']:
             # Attempt to find sender name if nested (backend might not send it yet)
             pass

        logger.info(f"Processing print job: {message_id} ({content_type})")
        
        try:
            # Acknowledge
            if message_id:
                await self.websocket.send(json.dumps({
                    "type": "print_status",
                    "message_id": message_id,
                    "status": "printing"
                }))

            if content_type == "text":
                self.print_handler.print_message({ 
                    'content': content, 
                    'sender_name': sender_name 
                })
            
            elif content_type == "image":
                # Backend sends base64 string directly as 'content' sometimes
                img_data = content if isinstance(content, str) else content.get('image_url')
                self.print_handler.print_image(img_data)
            
            # Report success
            await self.report_print_status(message_id, "printed")
            logger.info(f"Print job completed: {message_id}")
            
        except Exception as e:
            logger.error(f"Print job failed: {message_id} - {e}")
            await self.report_print_status(message_id, "failed", str(e))
    
    async def report_print_status(
        self, 
        message_id: str, 
        status: str, 
        error: str = None
    ):
        """Report print job completion back to cloud"""
        if not self.websocket or not message_id:
            return
        
        await self.websocket.send(json.dumps({
            "type": "print_status",
            "message_id": message_id,
            "status": status,
            "error": error,
            "printed_at": datetime.utcnow().isoformat() + "Z",
        }))

# ─────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

def main():
    """Entry point for the agent"""
    agent = PaperDropAgent()
    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
