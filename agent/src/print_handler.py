from PIL import Image
import io
import base64
from device_interface import get_printer_connection

class PrintHandler:
    def __init__(self):
        self.p = get_printer_connection()
        if not self.p:
            print("WARNING: No printer connection established (Real or Mock).")

    def print_text(self, text):
        if not self.p: return
        try:
            self.p.text(text + "\n")
            self.p.cut()
        except Exception as e:
            print(f"Print error: {e}")

    def print_image(self, base64_image):
        if not self.p: return
        try:
            # Remove header if present (data:image/png;base64,...)
            if 'base64,' in base64_image:
                base64_image = base64_image.split('base64,')[1]
            
            image_data = base64.b64decode(base64_image)
            img = Image.open(io.BytesIO(image_data))
            
            # Resize logic (max width ~384px for 58mm thermal printer)
            width = 384
            w_percent = (width / float(img.size[0]))
            h_size = int((float(img.size[1]) * float(w_percent)))
            img = img.resize((width, h_size), Image.Resampling.LANCZOS)

            self.p.image(img)
            self.p.cut()
            
        except Exception as e:
            print(f"Print image error: {e}")

    def print_message(self, message):
         if not self.p: return
         # content is JSON/dict
         # { "body": "...", "timestamp": true }
         body = message.get('content')
         
         # Basic formatting commands
         # Note: MockPrinter wraps these calls, Real printer uses escpos commands
         # We assume 'set' method exists on both interfaces
         if hasattr(self.p, 'set'):
             self.p.set(align='center', bold=True)
         
         self.p.text("PaperDrop\n")
         self.p.text("----------------\n")
         
         if hasattr(self.p, 'set'):
             self.p.set(align='left', bold=False)
         
         if isinstance(body, str):
             self.p.text(body + "\n")
         elif isinstance(body, dict):
             if body.get('body'):
                 self.p.text(body.get('body') + "\n")
         
         self.p.text("\n")
         if hasattr(self.p, 'set'):
             self.p.set(align='center')
         self.p.text("----------------\n")
         self.p.text(f"Sent by {message.get('sender_name', 'Unknown')}\n")
         self.p.cut()

print_handler = PrintHandler()
