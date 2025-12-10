#!/usr/bin/env python3
"""
PaperDrop Device Agent
Runs on Raspberry Pi, manages WiFi setup, cloud connection, and printing.
"""

import asyncio
import logging
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('paperdrop')

async def main():
    logger.info("PaperDrop Agent starting...")
    
    # Keep running
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
