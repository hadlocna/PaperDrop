from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('onboarding')

app = FastAPI()

# HTML Template for Onboarding
html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PaperDrop Setup</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-white rounded-xl shadow-lg overflow-hidden">
        <div class="bg-blue-600 p-6 text-center">
            <h1 class="text-2xl font-bold text-white mb-2">PaperDrop Setup</h1>
            <p class="text-blue-100">Connect your device to WiFi</p>
        </div>
        
        <div class="p-8">
            {% if success %}
            <div class="bg-green-50 text-green-700 p-4 rounded-lg mb-6 text-center">
                <p class="font-bold">Configuration Saved!</p>
                <p class="text-sm mt-1">The device will now restart and connect to.</p>
                <p class="font-mono mt-2 font-bold">{{ ssid }}</p>
            </div>
            {% else %}
            <form action="/configure" method="post" class="space-y-6">
                <div>
                    <label for="ssid" class="block text-sm font-medium text-gray-700 mb-1">WiFi Network Name (SSID)</label>
                    <input type="text" id="ssid" name="ssid" required 
                        class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                        placeholder="Enter WiFi Name">
                </div>
                
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-700 mb-1">WiFi Password</label>
                    <input type="password" id="password" name="password" required 
                        class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                        placeholder="Enter WiFi Password">
                </div>

                <button type="submit" 
                    class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg transition-colors shadow-md">
                    Connect Device
                </button>
            </form>
            {% endif %}
            
            <div class="mt-8 border-t border-gray-100 pt-6 text-center">
                <p class="text-gray-500 text-sm">Device Code:</p>
                <p class="text-xl font-mono font-bold text-gray-800 tracking-wider mt-1">CODE-1234</p>
                <p class="text-xs text-gray-400 mt-2">Use this code to add the device in your app</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return HTMLResponse(content=html_template.replace("{% if success %}", "{% if False %}").replace("{% endif %}", "").replace("{% else %}", ""))

@app.post("/configure", response_class=HTMLResponse)
async def configure(request: Request, ssid: str = Form(...), password: str = Form(...)):
    logger.info(f"Received Configuration - SSID: {ssid}")
    # In a real device, this would write to wpa_supplicant or similar
    
    success_content = html_template.replace("{% if success %}", "{% if True %}").replace("{% endif %}", "").replace("{% else %}", "").replace("{{ ssid }}", ssid)
    # Simple template hack for single file demonstration
    success_content = success_content.split('{% else %}')[0] + success_content.split('{% endif %}')[-1]
    
    return HTMLResponse(content=success_content)

if __name__ == "__main__":
    print("Starting Onboarding Server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
