from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
import logging
import asyncio

app = FastAPI()
logger = logging.getLogger("WiFiSetup")

# CSS for Premium Design
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
</style>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Setup PaperDrop</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    """ + STYLE + """
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="logo">PaperDrop</div>
            <h1>Let's get connected</h1>
            <p>Choose your home WiFi so PaperDrop can come online.</p>
            
            <form action="/connect" method="post">
                <div class="form-group">
                    <label>Network Name</label>
                    <input type="text" name="ssid" id="ssid" placeholder="Select or type..." required>
                </div>
                
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" placeholder="••••••••" required>
                </div>
                
                <button type="submit">Join Network</button>
            </form>

            <div class="networks">
                <label>Nearby Networks</label>
                <div class="network-item" onclick="document.getElementById('ssid').value='Home_WiFi_5G'">
                    <span>Home_WiFi_5G</span>
                    <span class="signal">Nice & Fast</span>
                </div>
                <div class="network-item" onclick="document.getElementById('ssid').value='Guest_Network'">
                    <span>Guest_Network</span>
                    <span class="signal">Open</span>
                </div>
                <div class="network-item" onclick="document.getElementById('ssid').value='Not_Yours'">
                    <span>Not_Yours</span>
                    <span class="signal">Weak</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

from config import config

# Initialize config to ensure we have a device code
config.initialize()
DEVICE_CODE = config.device_code
WEB_APP_URL = "http://localhost:5173" # In production, this would be https://app.paperdrop.com

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
            <h1>You're Online!</h1>
            <p>The device has successfully connected to the WiFi network.</p>
            
            <div style="font-size: 60px; margin: 20px 0;">🎉</div>
            
            <p style="color: var(--text-secondary);">Your Device Code is:</p>
            <div style="font-family: monospace; font-size: 24px; font-weight: bold; color: var(--dark); margin-bottom: 24px; letter-spacing: 2px;">
                """ + DEVICE_CODE + """
            </div>

            <a href=\"""" + WEB_APP_URL + """/setup?code=""" + DEVICE_CODE + """\" style="text-decoration: none;">
                <button>Complete Setup</button>
            </a>
            
            <p style="font-size: 12px; margin-top: 16px; color: var(--text-secondary);">
                Tap the button above to link this device to your account.
            </p>
        </div>
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
    # Logic to trigger WIFI connection would go here
    return HTMLResponse(SUCCESS_TEMPLATE)

def start_setup_server():
    # Running on 8080 for dev/demo purposes to avoid root requirement
    uvicorn.run(app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    start_setup_server()
