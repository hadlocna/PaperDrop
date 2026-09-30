"""Receipt geometry shared by managed print paths (576 dots = 72 mm)."""
from PIL import Image, ImageOps

PRINT_WIDTH = 576
MAX_PRINT_HEIGHT = 16000  # About two metres; reject oversized jobs, never distort them.
FRAGMENT_HEIGHT = 960


def fit_width(source, *, trim_white=False, max_height=MAX_PRINT_HEIGHT):
    if source.width * source.height > 16000000:
        raise ValueError('Picture too large')
    source = ImageOps.exif_transpose(source).convert('RGBA')
    image = Image.new('RGBA', source.size, 'white')
    image.alpha_composite(source)
    image = image.convert('RGB')
    if trim_white:
        # Keep every non-white mark and a small breathing margin. Only artwork,
        # never a composed page or QR code, opts into this crop.
        bounds = image.convert('L').point(lambda p: 255 if p < 250 else 0).getbbox()
        if bounds:
            left, top, right, bottom = bounds
            pad = max(1, round((right-left) * 8 / PRINT_WIDTH))
            image = image.crop((max(0, left-pad), max(0, top-pad),
                                min(image.width, right+pad), min(image.height, bottom+pad)))
    height = max(1, round(image.height * PRINT_WIDTH / image.width))
    if height > max_height:
        raise ValueError('Picture exceeds the two-metre print limit; split it into shorter images')
    return image.resize((PRINT_WIDTH, height), Image.Resampling.LANCZOS)
