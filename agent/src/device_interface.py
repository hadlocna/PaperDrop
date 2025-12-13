import os
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger('paperdrop.interface')

class MockPrinter:
    """Saves print jobs to local files for visual verification instead of printing"""
    def __init__(self):
        self.output_dir = Path("./debug_prints")
        self.output_dir.mkdir(exist_ok=True)
        logger.info(f"MOCK PRINTER ACTIVE. Outputting to {self.output_dir.absolute()}")

    def text(self, txt):
        # Append text to a debug file
        with open(self.output_dir / "last_print.txt", "a") as f:
            f.write(txt)
            
    def image(self, img):
        # Save the generated PIL image so you can visually inspect dithering
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        img.save(self.output_dir / f"print_{timestamp}.png")

    def cut(self):
        with open(self.output_dir / "last_print.txt", "a") as f:
            f.write("\n[--- CUT ---]\n")

    # Stub other required methods used in print_handler
    def close(self): pass
    def set(self, **kwargs): pass
    def qr(self, content, **kwargs):
        with open(self.output_dir / "last_print.txt", "a") as f:
            f.write(f"\n[QR CODE: {content}]\n")


def get_printer_connection():
    """Factory to return real or mock printer based on ENV var"""
    if os.environ.get("PAPERDROP_ENV") == "development" or os.environ.get("PAPERDROP_ENV") == "integration":
        return MockPrinter()
    
    # Real Hardware connection
    try:
        from escpos.printer import Usb
        # Epson TM-T20III (VID 0x04b8, PID 0x0e28)
        # We explicitly target the user's specific model
        return Usb(0x04b8, 0x0e28, profile="TM-T20III")
    except Exception as e:
        logger.error(f"Could not connect to real printer: {e}")
        # In production, returning None might crash logic if not handled.
        # Falling back to Mock might be dangerous, but for now returning None is safer to indicate failure.
        return None
