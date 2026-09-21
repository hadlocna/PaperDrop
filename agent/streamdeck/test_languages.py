import ast
import hashlib
import json
from pathlib import Path
import unittest
from languages import LANGUAGES, all_phrases, translate

ROOT=Path(__file__).parent

class LanguageTests(unittest.TestCase):
    def test_every_spoken_controller_cue_has_all_five_translations(self):
        phrases=set(all_phrases())
        for source in ('controller.py','app.py'):
            tree=ast.parse((ROOT/source).read_text())
            for call in ast.walk(tree):
                if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute):continue
                if call.func.attr not in ('transition','speak'):continue
                args=call.args[1:] if call.func.attr=='transition' else call.args
                for arg in args:
                    if not isinstance(arg,(ast.Constant,ast.IfExp)):continue
                    for node in ast.walk(arg):
                        if isinstance(node,ast.Constant) and isinstance(node.value,str):
                            # f-string fragments are covered by concrete names below.
                            if not isinstance(arg,ast.JoinedStr):phrases.add(node.value)
        family=json.loads((ROOT/'family.json').read_text())
        for person in family['children']:
            phrases.add(f'Hello {person["name"]}. Choose letters, numbers, or a postcard.')
            phrases.add(f'For {person["name"]}. Tap the microphone to talk, or the picture to draw. Tap again when you are done.')
        for language in LANGUAGES:
            inventory={translate(p,language) for p in all_phrases()}
            for phrase in phrases:
                with self.subTest(language=language,phrase=phrase):
                    self.assertIn(translate(phrase,language),inventory)

    def test_questions_keep_their_numbers_and_letter_targets(self):
        for language in LANGUAGES:
            self.assertIn('7',translate('What number comes after 7?',language))
            self.assertIn('4',translate('What is 4 plus 5?',language))
            self.assertIn('5',translate('What is 4 plus 5?',language))
            self.assertIn('Z',translate('Can you find the letter Z?',language))
        self.assertIn('rouge',translate('Can you find red?','fr'))
        self.assertIn('Grün',translate('Can you find green?','de'))
        self.assertIn('amarelo',translate('Can you find yellow?','pt'))

if __name__=='__main__':unittest.main()
