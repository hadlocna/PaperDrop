import requests
import json

# Configuration
API_URL = "https://paperdrop-backend.onrender.com"
DEVICE_CODE = "PD-780420ea"

def clear_queue():
    print(f"Clearing queue for device {DEVICE_CODE}...")
    
    try:
        response = requests.delete(
            f"{API_URL}/api/messages/queue", 
            json={"deviceCode": DEVICE_CODE}
        )
        
        if response.status_code == 200:
            print("Success!")
            print(response.json())
        else:
            print(f"Failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    clear_queue()
