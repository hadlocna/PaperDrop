import unittest
from PIL import Image, ImageDraw
from print_layout import fit_width


class PrintLayoutTests(unittest.TestCase):
    def test_long_picture_keeps_width_and_proportions(self):
        result = fit_width(Image.new('RGB', (288, 2000), 'black'))
        self.assertEqual(result.size, (576, 4000))
        self.assertEqual(result.getpixel((575, 3999)), (0, 0, 0))

    def test_oversized_picture_is_rejected_not_squashed(self):
        with self.assertRaises(ValueError):
            fit_width(Image.new('RGB', (10, 1000), 'black'))

    def test_artwork_crop_removes_blank_frame_but_keeps_all_marks(self):
        source = Image.new('RGB', (1000, 1000), 'white')
        ImageDraw.Draw(source).rectangle((300, 200, 699, 799), fill='black')
        result = fit_width(source, trim_white=True)
        bounds = result.convert('L').point(lambda p: 255 if p < 128 else 0).getbbox()
        self.assertLessEqual(bounds[0], 9)
        self.assertGreaterEqual(bounds[2], 567)
        self.assertGreater(result.height, 800)
        self.assertEqual(fit_width(source).size, (576, 576))

    def test_transparent_background_is_white(self):
        image = Image.new('RGBA', (576, 10), (0, 0, 0, 0))
        self.assertEqual(fit_width(image).getpixel((0, 0)), (255, 255, 255))

    def test_blank_art_does_not_fail_crop(self):
        self.assertEqual(fit_width(Image.new('RGB', (100, 200), 'white'), trim_white=True).size, (576, 1152))
