from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import subprocess
import asyncio
import logging

app = FastAPI()
logger = logging.getLogger("WiFiSetup")

# Embedded HTML Template for simple deployment
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PaperDrop Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, sans-serif; background: #faf9f6; color: #333; padding: 20px; max-width: 400px; mx-auto; }
        .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { margin-top: 0; color: #ff6b6b; }
        input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #ff6b6b; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .scanning { text-align: center; color: #666; font-style: italic; }
    </style>
</head>
<body>
    <div class="card">
        <h1>PaperDrop Setup</h1>
        <p>Connect your device to WiFi.</p>
        
        <form action="/connect" method="post">
            <label>SSID (Network Name)</label>
            <input type="text" name="ssid" placeholder="MyWiFi" required>
            
            <label>Password</label>
            <input type="password" name="password" placeholder="Password">
            
            <button type="submit">Connect</button>
        </form>
    </div>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_TEMPLATE

@app.post("/connect")
async def connect(ssid: str = Form(...), password: str = Form(...)):
    logger.info(f"Received WiFi creds for {ssid}")
    
    # In a real scenario, we would write wpa_supplicant.conf
    # For simulation/mockup, we'll pretend to connect.
    
    # Simulate connection delay
    # In real implementation:
    # subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password])
    
    config_success = True 
    if config_success:
        return HTMLResponse("""
            <div style="font-family: sans-serif; padding: 20px; text-align: center;">
                <h1>Connecting...</h1>
                <p>PaperDrop is connecting to your network.</p>
                <p>If the light turns green, you're good to go!</p>
            </div>
        """)
    else:
        return RedirectResponse(url="/?error=failed")

def start_setup_server():
    uvicorn.run(app, host="0.0.0.0", port=80)

if __name__ == "__main__":
    start_setup_server()
