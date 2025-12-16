import usb.core
import usb.backend.libusb1

print("Checking USB backend...")
try:
    b = usb.backend.libusb1.get_backend()
    if b is None:
        print("No backend found.")
    else:
        print(f"Backend found: {b}")
except Exception as e:
    print(f"Error finding backend: {e}")

print("Listing devices...")
try:
    devs = usb.core.find(find_all=True)
    for d in devs:
        print(f"Device: {d}")
except Exception as e:
    print(f"Error listing devices: {e}")
