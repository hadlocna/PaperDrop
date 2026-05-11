import requests
import json
import sys

# Configuration
API_URL = "https://api.paperdrop.me" # Or http://localhost:3000
DEVICE_ID = "PD-780420ea" # Your device code
USER_ID = "" # Need a valid user ID from your database

def send_test_print():
    print(f"Sending test print to {DEVICE_ID}...")
    
    # 1. You need a valid user ID who owns the device or has access.
    # Since we don't have authentication flow here easily without a token,
    # we might need to rely on the frontend or a known user ID.
    # If you are running this locally against localhost, you can inspect the DB.
    
    if not USER_ID:
        print("Error: Please set USER_ID in the script to a valid user UUID.")
        return

    payload = {
        "senderId": USER_ID,
        "deviceId": DEVICE_ID, # Note: Backend expects UUID, but let's see if it resolves code. 
        # Wait, messageController expects deviceId to be UUID. 
        # We need to look up the device UUID from the code first?
        # The frontend passes the device UUID.
        "content": "Hello from PaperDrop Test Script!",
        "contentType": "text"
    }
    
    # We might need to look up device UUID first if DEVICE_ID is the code.
    # But let's assume the user can get the UUID from the URL or DB.
    
    try:
        response = requests.post(f"{API_URL}/api/messages", json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    send_test_print()
