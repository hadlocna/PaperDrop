from escpos.printer import Usb
import sys
import usb.core
import usb.util

def test_print():
    try:
        print("Attempting to connect to Epson TM-T20III...")
        # Try generic profile first if specific one fails
        try:
            p = Usb(0x04b8, 0x0e28, profile="TM-T20II") # Try II instead of III
        except Exception as e:
            print(f"Profile TM-T20II failed: {e}")
            print("Trying default profile...")
            p = Usb(0x04b8, 0x0e28, profile="default")

        print("Connected! Printing Hello World...")
        p.text("Hello World\n")
        p.text("PaperDrop Printing Test\n")
        p.cut()
        
        print("Print successful!")
        
    except Exception as e:
        print(f"Error: {e}")
        # Check for resource busy
        if "Resource busy" in str(e):
            print("\nNOTE: macOS often claims USB printers automatically.")
            print("You may need to unload the kernel extension or kill the process using it.")
        sys.exit(1)

if __name__ == "__main__":
    test_print()
