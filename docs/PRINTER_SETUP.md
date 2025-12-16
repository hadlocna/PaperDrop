# Epson TM-T20III Printer Setup Guide

This guide documents how to successfully connect to and print from an Epson TM-T20III USB thermal printer using Python.

## Hardware Details
*   **Model:** Epson TM-T20III
*   **Vendor ID (VID):** `0x04b8`
*   **Product ID (PID):** `0x0e28`

## Prerequisites

### 1. System Libraries
You must install `libusb` for the Python USB backend to work.

*   **macOS:**
    ```bash
    brew install libusb
    ```
    *Note: If Python cannot find the library, you may need to export the path:*
    ```bash
    export DYLD_LIBRARY_PATH=/usr/local/opt/libusb/lib:$DYLD_LIBRARY_PATH
    ```

*   **Linux (Raspberry Pi):**
    ```bash
    sudo apt-get install libusb-1.0-0-dev
    ```

### 2. Python Dependencies
Install the following packages:
```bash
pip install python-escpos pyusb
```
*Note: `pyusb` is strictly required for USB communication but is sometimes not installed automatically by `python-escpos`.*

## Implementation Details

### Profile Selection
The `python-escpos` library may not fully support the `TM-T20III` profile directly, or it may throw errors. **Use the `TM-T20II` profile instead**, as it is backward compatible.

### Working Code Snippet

```python
from escpos.printer import Usb
import sys

def print_hello():
    try:
        # Epson TM-T20III (VID 0x04b8, PID 0x0e28)
        # We use the 'TM-T20II' profile which is compatible
        p = Usb(0x04b8, 0x0e28, profile="TM-T20II")
        
        p.text("Hello World\n")
        p.text("PaperDrop Printing Test\n")
        p.cut()
        
    except Exception as e:
        print(f"Error: {e}")
        
        # Common macOS Error: Resource busy
        if "Resource busy" in str(e):
            print("Error: USB device is busy. macOS may have claimed the interface.")
            print("Try unloading the kernel extension or killing the process using it.")

if __name__ == "__main__":
    print_hello()
```

## Troubleshooting

### "Resource busy" (macOS)
macOS often automatically claims USB printers for its own print system (CUPS). If you get a "Resource busy" error:
1.  Check if the printer is added in **System Settings > Printers & Scanners**. If so, remove it or ensure it's not actively trying to print.
2.  You may need to detach the kernel driver if you want direct raw access, though `libusb` usually handles this.

### "No backend available"
This means `pyusb` cannot find the `libusb` system library.
1.  Ensure `libusb` is installed.
2.  Check your `DYLD_LIBRARY_PATH` (macOS) or `LD_LIBRARY_PATH` (Linux).
