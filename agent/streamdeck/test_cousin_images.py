import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from media import Media, named_cousins


class CousinImageTests(unittest.TestCase):
    def test_whole_names_and_spoken_spellings(self):
        self.assertEqual([child['name'] for child in named_cousins('Alma as a princess')], ['Alma'])
        self.assertEqual([child['name'] for child in named_cousins('andy and Margo with Rue')],
                         ['Margaux', 'Andi', 'Roux'])
        self.assertEqual([child['name'] for child in named_cousins('Théodore et Élise')],
                         ['Theodore', 'Elise'])
        self.assertEqual(named_cousins('A map of Germany'), [])

    def test_named_prompt_sends_matching_portraits(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Media(directory)
            audio = Path(directory) / 'request.wav'
            audio.write_bytes(b'test')
            target = Path(directory) / 'picture.png'
            from PIL import Image
            import io
            image = Image.new('RGB', (16, 16), 'white')
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            ai = MagicMock()
            ai.audio.transcriptions.create.return_value.text = 'Alma and Elise as princesses'
            ai.moderations.create.return_value.results = [MagicMock(flagged=False)]
            ai.images.edit.return_value.data = [MagicMock(b64_json=base64.b64encode(buffer.getvalue()).decode())]
            with patch('media.client', return_value=ai):
                self.assertEqual(media.draw(audio, target, lambda _: None), 'Alma and Elise as princesses')
            ai.images.generate.assert_not_called()
            kwargs = ai.images.edit.call_args.kwargs
            self.assertEqual(len(kwargs['image']), 2)
            self.assertIn('Image 1 is Alma. Image 2 is Elise.', kwargs['prompt'])
            self.assertTrue(target.exists())
            media.close()


if __name__ == '__main__':
    unittest.main()
