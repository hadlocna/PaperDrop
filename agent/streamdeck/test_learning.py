import hashlib
from pathlib import Path
import tempfile
import unittest
import wave
from games import new_round
from riddles import RIDDLES, ANSWERS, ICONS
from languages import LANGUAGES, translate, label, all_phrases
from audio_cues import combine, star_frames, RATE, STAR_DURATION

class LearningTests(unittest.TestCase):
    def test_riddles_have_four_distinct_picture_answers_and_complete_translations(self):
        previous=None
        for _ in range(100):
            question=new_round('riddles',previous)
            self.assertEqual(len(set(question['choices'])),4)
            self.assertIn(question['target'],question['choices'])
            self.assertNotEqual(question['target'],previous)
            previous=question['target']
            for choice in question['choices']:
                self.assertTrue((Path(__file__).parent/'assets/icons'/f'{ICONS[choice]}.svg').exists())
        for _,words in RIDDLES:
            for language,expected in zip(LANGUAGES,words):self.assertEqual(translate(words[0],language),expected)
        for answer,words in ANSWERS.items():
            for language,expected in zip(LANGUAGES,words):self.assertEqual(label(answer,language),expected)
        for phrase in all_phrases():
            for language in LANGUAGES:self.assertTrue(translate(phrase,language))

    def test_star_and_question_compose_in_order_without_clipping(self):
        import audioop
        self.assertEqual(len(star_frames()),int(RATE*STAR_DURATION)*2)
        self.assertLess(audioop.max(star_frames(),2),30000)
        self.assertGreater(audioop.rms(star_frames(),2),200)
        with tempfile.TemporaryDirectory() as root:
            paths=[]
            for n in (400,800):
                path=Path(root)/f'{n}.wav';paths.append(path)
                with wave.open(str(path),'wb') as out:
                    out.setparams((1,2,RATE,0,'NONE','not compressed'))
                    out.writeframes(n.to_bytes(2,'little')*RATE)
            result=combine(paths,Path(root)/'cue.wav',star=True)
            with wave.open(str(result)) as wav:
                frames=wav.readframes(wav.getnframes())
                self.assertEqual(wav.getframerate(),RATE)
                self.assertAlmostEqual(wav.getnframes()/RATE,3.1,places=2)
            self.assertEqual(frames[:len(star_frames())],star_frames())
            self.assertEqual(frames[len(star_frames()):len(star_frames())+2],(400).to_bytes(2,'little'))
