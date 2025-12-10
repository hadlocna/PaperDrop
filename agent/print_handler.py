from escpos.printer import Serial, Dummy
from PIL import Image
import io
import base64
import os

# Set to True to use Dummy printer (prints to console/buffer) if no hardware
USE_DUMMY = os.environ.get('USE_DUMMY_PRINTER', 'True') == 'True'

class PrintHandler:
    def __init__(self):
        try:
            if USE_DUMMY:
                self.p = Dummy()
                print("Initialized Dummy Printer")
            else:
                # Adjust settings for specific hardware (e.g. /dev/ttyS0, baudrate)
                self.p = Serial(devfile='/dev/serial0', baudrate=19200)
                print("Initialized Serial Printer")
        except Exception as e:
            print(f"Printer init failed: {e}, falling back to Dummy")
            self.p = Dummy()

    def print_text(self, text):
        try:
            self.p.text(text + "\n")
            self.p.cut()
            if isinstance(self.p, Dummy):
                print(f"[PRINTER OUPUT]:\n{self.p.output}")
                self.p.clear()
        except Exception as e:
            print(f"Print error: {e}")

    def print_image(self, base64_image):
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
            
            if isinstance(self.p, Dummy):
                 print(f"[PRINTER IMAGE OUTPUT]: (Binary data length: {len(self.p.output)})")
                 self.p.clear()

        except Exception as e:
            print(f"Print image error: {e}")

    def print_message(self, message):
         # content is JSON/dict
         # { "body": "...", "timestamp": true }
         body = message.get('content')
         
         self.p.set(align='center', bold=True)
         self.p.text("PaperDrop\n")
         self.p.text("----------------\n")
         self.p.set(align='left', bold=False)
         
         if isinstance(body, str):
             self.p.text(body + "\n")
         elif isinstance(body, dict):
             if body.get('body'):
                 self.p.text(body.get('body') + "\n")
         
         self.p.text("\n")
         self.p.set(align='center')
         self.p.text("----------------\n")
         self.p.text(f"Sent by {message.get('sender_name', 'Unknown')}\n")
         self.p.cut()
         
         if isinstance(self.p, Dummy):
            print(f"[PRINTER JOB]:\n{self.p.output}")
            self.p.clear()

print_handler = PrintHandler()
