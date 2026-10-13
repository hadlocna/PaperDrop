import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from controller import Controller
from store import Mailbox

FAMILY=json.loads((Path(__file__).parent/'family.json').read_text())


class FakeMedia:
    def __init__(self):
        self.draw_gate=threading.Event()
        self.play_gate=threading.Event()
        self.play_gate.set()
        self.sequences=[]
        self.draw_calls=0
        self.record_calls=0
        self.fail_record=False
        self.print_calls=0
        self.fail_print=False
    def start_guidance(self,text):return None
    def cue(self,text):pass
    def cue_sequence(self,texts,star=False):self.sequences.append((texts,star))
    def stop_audio(self):pass
    def start_recording(self,path):
        self.record_calls+=1
        Path(path).write_bytes(b'fake audio')
    def wait_recording_ready(self):pass
    def finish_recording(self,path):
        if self.fail_record:raise ValueError('short')
        return 2.0
    def draw(self,audio,target,progress):
        self.draw_calls+=1
        progress('Drawing…')
        if not self.draw_gate.wait(3):raise TimeoutError()
        Path(target).write_bytes(b'fake image')
        return 'a snail'
    def play(self,path):
        if not self.play_gate.wait(3):raise TimeoutError()
    def print_image(self,path,ident):
        self.print_calls+=1
        if self.fail_print:raise RuntimeError("offline")
        return {"status":"sent"}
    def close(self):
        self.draw_gate.set();self.play_gate.set()


class ControllerTests(unittest.TestCase):
    def test_recording_time_is_per_child_and_survives_reopen(self):
        self.tap(0)
        self.tap(3)
        self.assertEqual(self.c.mode, 'recording_time')
        self.assertEqual([t['label'] for t in self.c.snapshot()['tiles'][:4]], ['10s', '15s', '30s', '60s'])
        self.assertTrue(self.c.snapshot()['tiles'][2]['selected'])
        self.tap(3)
        self.assertEqual(self.c.mode, 'personal')
        self.assertEqual(self.box.recording_seconds('alma'), 60)
        self.assertEqual(self.box.recording_seconds('theodore'), 30)
        reopened = Mailbox(self.temp.name)
        self.assertEqual(reopened.recording_seconds('alma'), 60)
        reopened.close()
        for invalid in (0, 20, 61, True, '30'):
            with self.assertRaises(ValueError):
                self.box.set_recording_seconds('alma', invalid)

    def test_selected_time_controls_capture_countdown_and_timeout(self):
        from unittest.mock import patch
        for seconds in (10, 15, 30, 60):
            with self.subTest(seconds=seconds):
                self.c.person = 'alma'
                self.box.set_recording_seconds('alma', seconds)
                with patch('controller.threading.Timer') as timer:
                    self.c.start_recording(1, 'voice')
                    self.wait('recording')
                    deadline = time.monotonic() + 1
                    while not timer.called and time.monotonic() < deadline:
                        time.sleep(.005)
                    self.assertEqual(timer.call_args.args[0], seconds)
                    self.assertEqual(self.media.recording_seconds, seconds)
                    self.assertEqual(self.c.snapshot()['tiles'][3]['label'], f'{seconds}s')
                    callback = timer.call_args.args[1]
                    callback()
                    self.wait('review')
                    callback()
                    self.assertEqual(self.c.mode, 'review')
                self.c.discard()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.box=Mailbox(self.temp.name)
        self.media=FakeMedia()
        self.c=Controller(FAMILY,self.box,self.media)
    def tearDown(self):
        self.c.close()
        self.box.close()
        self.temp.cleanup()
    def test_guidance_finishes_before_microphone_and_countdown(self):
        gate = threading.Event()
        class Player:
            def wait(self, timeout):
                gate.wait(timeout)
                return 0
        prompts = []
        self.media.start_guidance = lambda text: prompts.append(text) or Player()
        self.c.block_until = 0
        self.c.press(5, True)
        self.c.press(5, False)
        self.assertEqual(self.c.mode, 'arming')
        self.assertEqual(self.media.record_calls, 0)
        self.assertEqual(self.c.snapshot()['record_seconds'], 0)
        self.assertIn('picture', prompts[0])
        gate.set()
        self.wait('recording')
        self.assertEqual(self.media.record_calls, 1)
        self.assertLess(self.c.snapshot()['record_seconds'], 1)

    def test_delete_during_guidance_never_opens_microphone(self):
        gate = threading.Event()
        finished = threading.Event()
        class Player:
            def wait(self, timeout):
                gate.wait(timeout)
                finished.set()
                return 0
        self.media.start_guidance = lambda text: Player()
        self.c.block_until = 0
        self.c.press(5, True)
        self.c.press(5, False)
        self.c.finish_recording(discard=True)
        self.wait('home')
        gate.set()
        self.assertTrue(finished.wait(1))
        self.assertEqual(self.media.record_calls, 0)

    def test_deliver_saved_preserves_original_and_uses_existing_id(self):
        deliveries=[]
        self.media.send_drawing=lambda draft,family: deliveries.append(draft) or {'status':'sent'}
        self.media.delivery_status=lambda ident: {'status':'printed'}
        draft=dict(id='a'*32,sender='portugal',recipient='lore',kind='drawing',image='saved.png')
        self.box.send(draft)
        self.c.deliver_saved(draft['id'])
        self.wait('sent')
        self.assertEqual(deliveries,[draft])
        self.assertIsNone(self.c.draft)
        self.assertEqual(self.box.get(draft['id']),draft)
        self.assertEqual(self.c.snapshot()['heading'],'Printed at Düsseldorf')
        with self.assertRaises(ValueError):self.c.deliver_saved(draft['id'])

    def wait(self,mode):
        until=time.monotonic()+2
        while time.monotonic()<until:
            if self.c.mode==mode:return
            time.sleep(.005)
        self.fail(f'Expected {mode}, found {self.c.mode}')
    def tap(self,key):
        self.c.block_until=0
        self.c.press(key,True);self.c.press(key,False)
    def compose(self):
        self.tap(0) # Alma
        self.tap(5) # Home
        self.tap(3) # Ohio
        self.tap(0) # Andy
        self.assertEqual(self.c.mode,'compose')
    def record(self,key=1):
        self.c.block_until=0
        self.c.press(key,True)
        self.wait('recording')
        self.c.record_started -= 1
        self.c.press(key,False)

    def test_remote_voice_selects_child_and_uses_cloud_transport(self):
        sent=[]
        self.media.send_mail=lambda draft,family: sent.append(dict(draft)) or {'status':'queued','type':'mail_result'}
        self.media.delivery_status=lambda ident: {}
        self.tap(3);self.tap(0)
        self.assertEqual(self.c.mode,'sender')
        self.tap(1)
        self.assertEqual(self.c.person,'theodore')
        self.record();self.wait('review');self.tap(5);self.wait('sent')
        self.assertEqual(len(sent),1)
        self.assertEqual((sent[0]['sender'],sent[0]['recipient'],sent[0]['kind']),('theodore','andy','voice'))
        self.assertIn('Queued',self.c.snapshot()['heading'])
        self.assertIn('Theodore',self.c.snapshot()['hint'])

    def test_every_child_reachable_and_house_sends_without_identity_screen(self):
        self.tap(3);self.tap(0)
        self.assertEqual(self.c.mode,'compose')
        self.record(1);self.wait('review')
        self.tap(5);self.wait('sent')
        self.assertIsNone(self.c.person)
        self.assertEqual(self.box.inbox('andy')[0]['sender'],'portugal')
        seen=set()
        for house in self.c.houses:
            self.c.switch_station(house)
            for house_key in (3,4):
                self.tap(house_key)
                seen.update(t['person'] for t in self.c.snapshot()['tiles'][:3] if t.get('person'))
                self.tap(5)
        self.assertEqual(seen,set(self.c.people))

    def test_voice_send_once_and_badge_is_recipient_specific(self):
        self.compose();self.record();self.wait('review')
        draft=dict(self.c.draft)
        self.tap(5);self.wait('sent')
        self.box.send(draft);self.box.send(draft)
        self.assertEqual(len(self.box.inbox('andy')),1)
        self.assertEqual(len(self.box.inbox('sloan')),0)
        self.assertTrue(Path(draft['audio']).exists())
        self.c.switch_station('ohio')
        self.assertEqual(self.c.snapshot()['tiles'][0]['badge'],1)
        self.assertEqual(self.c.snapshot()['tiles'][1]['badge'],0)
        self.tap(0);self.tap(4);self.tap(0);self.tap(0);self.tap(1)
        self.wait('incoming')
        self.tap(5)
        self.assertEqual(len(self.box.inbox('andy',unread=True)),0)
        self.assertEqual(self.c.snapshot()['tiles'][4]['icon'],'Mail')
        self.assertEqual(self.c.snapshot()['tiles'][4]['badge'],0)

    def test_generation_mashing_cannot_send_or_change_recipient(self):
        self.compose();self.record(2);self.wait('generating')
        for _ in range(20):
            for key in range(6):self.tap(key)
        self.c.press(5,True) # held across completion
        self.assertEqual(self.media.draw_calls,1)
        self.assertEqual(self.c.recipient,'andy')
        self.media.draw_gate.set();self.wait('preview')
        self.c.press(5,False)
        self.assertEqual(self.c.mode,'preview')
        self.assertFalse(self.box.inbox('andy'))
        self.tap(5) # preview -> review only
        self.assertEqual(self.c.mode,'review')
        self.assertFalse(self.box.inbox('andy'))
        self.tap(5);self.wait('sent')
        self.assertEqual(len(self.box.inbox('andy')),1)

    def test_transition_discards_other_held_keys(self):
        self.c.block_until=0
        self.c.press(0,True);self.c.press(3,True)
        self.c.press(0,False) # select Alma
        self.c.press(3,False) # stale key cannot select Ohio
        self.assertEqual(self.c.mode,'personal')

    def test_delete_removes_draft_not_sent_messages(self):
        self.compose();self.record();self.wait('review')
        path=Path(self.c.draft['audio'])
        self.tap(4)
        self.assertFalse(path.exists());self.assertIsNone(self.c.draft)
        self.assertEqual(self.c.mode,'compose')

    def test_cancel_short_recording_is_not_error(self):
        self.compose();self.c.block_until=0;self.c.press(1,True)
        self.wait('recording')
        self.media.fail_record=True
        self.tap(5);self.wait('compose')
        self.c.press(1,False)
        self.assertEqual(self.c.mode,'compose')
        self.assertFalse(self.box.inbox('andy'))

    def test_short_recording_can_be_retried(self):
        self.compose();self.media.fail_record=True;self.record();self.wait('error')
        self.tap(3)
        self.assertEqual(self.c.mode,'compose')
        self.media.fail_record=False
        self.record();self.wait('review')

    def test_station_change_blocked_during_draft(self):
        self.compose();self.record();self.wait('review')
        with self.assertRaises(ValueError):self.c.switch_station('ohio')
        self.assertEqual(self.c.station,'portugal')

    def test_send_failure_preserves_audio_for_retry(self):
        self.compose();self.record();self.wait('review')
        path=self.c.draft['audio']
        send=self.box.send
        self.box.send=lambda _:(_ for _ in ()).throw(OSError('disk full'))
        self.tap(5);self.wait('error')
        self.assertTrue(Path(path).exists())
        self.box.send=send
        self.tap(3);self.wait('sent')
        self.assertEqual(len(self.box.inbox('andy')),1)

    def test_cousin_envelopes_preserve_read_rules_and_one_action(self):
        for ident, sender, kind in [('old', 'sloan', 'voice'), ('new', 'andy', 'voice'), ('pic', 'rue', 'drawing')]:
            self.box.send(dict(id=ident, sender=sender, recipient='alma', kind=kind,
                              audio='test' if kind=='voice' else None, image='image' if kind=='drawing' else None))
        self.tap(0); self.assertEqual(self.c.snapshot()['tiles'][4]['badge'],3)
        self.tap(4); self.assertEqual(self.c.mode,'mail_people')
        self.assertEqual([t.get('person') for t in self.c.snapshot()['tiles'][:4]],['andy','sloan','rue','elise'])
        self.assertEqual([t.get('badge') for t in self.c.snapshot()['tiles'][:3]],[1,1,1])
        self.tap(2); self.assertEqual(self.c.mode,'mail_list')
        self.assertEqual(self.c.snapshot()['tiles'][0]['icon'],'Mail')
        self.tap(0); self.assertEqual(self.c.current['id'],'pic')
        self.media.print_calls=0
        self.tap(1); self.assertEqual(self.c.mode,'preview'); self.tap(0)
        self.assertEqual(self.media.print_calls,0)
        self.tap(4); self.assertEqual(self.c.snapshot()['tiles'][0]['icon'],'MailOpen')
        self.tap(5); self.tap(0); self.tap(0)
        self.assertEqual(sum(t.get('icon')=='Play' and not t.get('disabled') for t in self.c.snapshot()['tiles']),1)
        self.media.play_gate.clear(); self.tap(1); self.wait('playing')
        self.assertEqual(len(self.box.inbox('alma',unread=True)),2)
        self.media.play_gate.set(); self.wait('incoming')
        self.tap(4); self.tap(5); self.tap(1); self.tap(0); self.tap(1); self.wait('incoming')
        self.tap(5); self.assertEqual(self.c.snapshot()['tiles'][4]['badge'],0)

    def test_cousin_picker_pages_empty_mail_and_child_isolation(self):
        self.box.send(dict(id='other', sender='andy', recipient='theodore', kind='voice', audio='test'))
        self.tap(0);self.tap(4)
        self.assertEqual(self.c.mode,'mail_people')
        self.assertEqual(self.c.snapshot()['tiles'][0]['badge'],0)
        self.tap(4);self.assertEqual(self.c.snapshot()['tiles'][0]['person'],'lore')
        self.tap(4);self.tap(0);self.assertEqual(self.c.mode,'mail_list')
        self.assertEqual(self.c.mail,[])
        self.tap(5);self.tap(5);self.assertEqual(self.c.mode,'personal')

    def test_envelope_paging_and_explicit_print_survive_reopen(self):
        for index in range(6):
            self.box.send(dict(id=str(index),sender='andy',recipient='alma',kind='drawing',image='test'))
        self.c.person='alma';self.c.open_mail('andy')
        self.assertEqual(self.c.snapshot()['tiles'][0]['message_id'],'5')
        self.tap(4);self.assertEqual(self.c.snapshot()['tiles'][0]['message_id'],'1')
        self.tap(0);self.assertEqual(self.media.print_calls,0)
        self.media.print_image=lambda path, ident:{'status':'printed'}
        self.tap(2);self.wait('incoming')
        self.assertTrue(self.c.snapshot()['tiles'][2]['disabled'])
        self.assertTrue(self.box.get('1')['printed'])
        reopened=Mailbox(self.temp.name);self.assertTrue(reopened.get('1')['printed']);reopened.close()

    def test_notification_is_durable_localized_and_does_not_interrupt_recording(self):
        from languages import translate
        self.box.set_language('alma','fr')
        message=dict(id='notify',sender='andy',recipient='alma',kind='voice',audio='test',remote=True)
        self.box.send(message);self.box.send(message)
        self.assertEqual(len(self.box.notifications()),1)
        cues=[];self.media.start_guidance=lambda text:cues.append(text)
        self.c.mode='recording';self.c.announce_mail();self.assertEqual(cues,[])
        self.c.mode='home';self.c.notification_attempt=-100;self.c.announce_mail()
        deadline=time.monotonic()+1
        while self.c.notification_busy and time.monotonic()<deadline:time.sleep(.005)
        self.assertEqual(cues,[translate('There is a postcard for you. Press play to listen, or the picture to see it.','fr')])
        self.assertEqual(self.box.notifications(),[])
        self.c.notification_attempt=-100;self.c.announce_mail();self.assertEqual(len(cues),1)
        self.assertEqual(len(self.box.inbox('alma',unread=True)),1)

    def test_personal_announcement_matches_top_row_in_every_language(self):
        from languages import LANGUAGES, translate
        cues = []
        self.media.cue = cues.append
        for language in LANGUAGES:
            self.box.set_language('alma', language)
            self.c.home()
            self.tap(0)
            self.assertEqual(cues[-1], translate('Choose games, your language, or a postcard.', language))
            self.assertEqual(self.c.snapshot()['tiles'][1]['label'], LANGUAGES[language])

    def test_games_correct_retry_repeat_and_home(self):
        self.tap(1)
        for kind,key in [('letters',1),('numbers',2)]:
            self.tap(0);self.tap(key);question=dict(self.c.round)
            wrong=next(i for i,x in enumerate(question['choices']) if x!=question['target'])
            self.tap(wrong);self.assertEqual(self.c.round,question)
            self.tap(4);self.assertEqual(self.c.round,question)
            self.tap(question['choices'].index(question['target']))
            self.assertTrue(self.c.game_correct)
            self.c.advance_round(self.c.revision);self.assertNotEqual(self.c.round['target'],question['target'])
            self.tap(5);self.assertEqual(self.c.mode,'personal')

    def test_home_draw_print_once_and_retry_same_picture(self):
        self.media.fail_print=True;self.media.draw_gate.set()
        self.record(5);self.wait('print_review')
        self.assertEqual(self.media.print_calls,0)
        self.assertTrue(self.c.snapshot()['picture'])
        self.tap(5);self.wait('error')
        self.assertEqual(self.c.failed_mode,'printing')
        image=self.c.draft['image']
        self.assertTrue(Path(image).exists())
        self.media.fail_print=False;self.tap(3);self.wait('print_done')
        self.assertEqual(self.media.draw_calls,1)
        self.assertEqual(self.media.print_calls,2)
        self.assertFalse(self.box.inbox('andy'))
        self.tap(1);self.assertEqual(self.c.mode,'preview')
        self.tap(0);self.assertEqual(self.c.mode,'print_done')
        self.tap(5);self.assertEqual(self.c.mode,'home')

    def test_five_correct_answers_finish_a_game_without_penalty_for_retry(self):
        self.tap(0);self.tap(0);self.tap(1)
        for n in range(5):
            wrong=next(i for i,x in enumerate(self.c.round['choices']) if x!=self.c.round['target'])
            self.tap(wrong)
            self.assertEqual(self.c.game_score,n)
            self.assertTrue(self.c.snapshot()['tiles'][wrong]['disabled'])
            correct=self.c.round['choices'].index(self.c.round['target'])
            self.tap(correct)
            if n<4:self.c.advance_round(self.c.revision)
        self.assertEqual(self.c.mode,'game_win')
        self.assertEqual(self.c.game_score,5)
        self.tap(4);self.assertEqual(self.c.mode,'game')
        self.assertEqual(self.c.game_score,0)

    def test_wrong_answer_repeats_exact_translated_question_and_no_star(self):
        self.tap(0);self.c.language='fr';self.tap(0);self.tap(3)
        from languages import translate
        before=self.c.round.copy()
        wrong=next(i for i,x in enumerate(before['choices']) if x!=before['target'])
        self.tap(wrong)
        self.assertEqual(self.c.round,before)
        self.assertEqual(self.media.sequences[-1], ([translate('Try again. Here is the same question.','fr'),translate(before['prompt'],'fr')],False))
        self.assertEqual(self.c.game_score,0)
        count=len(self.media.sequences)
        self.tap(wrong)
        self.assertEqual(len(self.media.sequences),count)
        self.tap(before['choices'].index(before['target']))
        self.assertTrue(self.media.sequences[-1][1])

    def win(self):
        for n in range(5):
            self.tap(self.c.round['choices'].index(self.c.round['target']))
            if n<4:self.c.advance_round(self.c.revision)
        self.assertEqual(self.c.mode,'game_win')

    def test_prize_unique_saved_previewed_and_only_printed_on_request(self):
        self.tap(0);self.tap(0);self.tap(3);self.win()
        first=self.c.draft.copy()
        self.assertTrue(self.media.sequences[-1][1])
        self.assertEqual(sum(star for _,star in self.media.sequences),5)
        self.assertEqual(self.media.print_calls,0)
        self.assertTrue(Path(first['image']).exists())
        self.tap(1);self.assertEqual(self.c.mode,'preview')
        self.assertEqual(self.c.snapshot()['picture'],first['image'])
        self.tap(0);self.assertEqual(self.c.mode,'game_win')
        self.tap(0);self.wait('print_done')
        self.assertEqual(self.media.print_calls,1)
        self.tap(5)
        self.assertTrue(Path(first['image']).exists())
        self.tap(0);self.tap(0);self.tap(4)
        self.assertEqual(self.c.draft,first)
        self.tap(4);self.win()
        second=self.c.draft.copy()
        self.assertEqual(second['number'],first['number']+1)
        self.assertNotEqual(Path(first['image']).read_bytes(),Path(second['image']).read_bytes())
        reopened=Mailbox(self.temp.name)
        self.assertEqual(reopened.latest_reward('alma'),second)
        self.assertIsNone(reopened.latest_reward('theodore'))
        reopened.close()

    def test_reward_print_failure_keeps_same_card_on_retry(self):
        self.tap(0);self.tap(0);self.tap(3);self.win()
        prize=self.c.draft.copy();self.media.fail_print=True
        self.tap(0);self.wait('error')
        self.assertEqual(self.c.draft,prize)
        self.media.fail_print=False;self.tap(3);self.wait('print_done')
        self.assertEqual(self.box.latest_reward('alma'),prize)

    def test_language_choice_is_per_child_and_survives_reopen(self):
        cues=[]
        self.media.cue=cues.append
        self.tap(0);self.tap(1)
        self.assertEqual(self.c.mode,'languages')
        self.assertEqual([t['label'] for t in self.c.snapshot()['tiles'][:5]],['English','Français','Deutsch','Italiano','Português'])
        self.tap(1)
        self.assertEqual(self.c.language,'fr')
        self.assertIn('français',cues[-1])
        self.tap(0);self.tap(1)
        self.assertIn('lettre',cues[-1])
        self.tap(5);self.tap(5);self.tap(1)
        self.assertEqual(self.c.language,'en')
        self.tap(5);self.tap(0)
        self.assertEqual(self.c.language,'fr')
        reopened=Mailbox(self.temp.name)
        self.assertEqual(reopened.language('alma'),'fr')
        self.assertEqual(reopened.language('@station'),'fr')
        reopened.close()

    def test_automatic_game_round_and_cancel_on_home(self):
        self.c.feedback_delay=lambda:.05
        self.tap(0);self.tap(0);self.tap(1)
        question=self.c.round.copy()
        self.tap(question['choices'].index(question['target']))
        self.assertIsNotNone(self.c.round_timer)
        self.assertTrue(self.c.snapshot()['tiles'][4]['disabled'])
        until=time.monotonic()+1
        while self.c.game_correct and time.monotonic()<until:time.sleep(.005)
        self.assertFalse(self.c.game_correct)
        self.assertNotEqual(self.c.round['target'],question['target'])
        self.c.feedback_delay=lambda:10
        self.tap(self.c.round['choices'].index(self.c.round['target']))
        stale=self.c.revision
        self.tap(5)
        self.assertIsNone(self.c.round_timer)
        self.c.advance_round(stale)
        self.assertEqual(self.c.mode,'personal')

    def test_tap_starts_and_second_tap_finishes_recording(self):
        self.tap(5);self.wait('recording')
        self.assertTrue(self.c.record_latched)
        self.assertFalse(self.c.snapshot()['tiles'][5]['disabled'])
        self.media.draw_gate.set()
        self.tap(5);self.wait('print_review')
        self.assertEqual(self.media.draw_calls,1)
        self.assertEqual(self.media.print_calls,0)

    def test_print_requires_fresh_press_after_generation(self):
        self.record(5);self.wait('generating')
        self.c.press(5,True)
        self.media.draw_gate.set();self.wait('print_review')
        self.c.press(5,False)
        self.assertEqual(self.media.print_calls,0)
        self.tap(1);self.assertEqual(self.c.mode,'preview')
        self.assertTrue(self.c.snapshot()['picture'])
        self.tap(5);self.assertEqual(self.c.mode,'print_review')
        self.assertEqual(self.media.print_calls,0)
        self.tap(5);self.wait('print_done')
        self.assertEqual(self.media.print_calls,1)
        self.tap(5);self.assertEqual(self.c.mode,'home')
        self.record(5);self.wait('print_review')
        self.assertEqual(self.media.draw_calls,2)
        self.assertEqual(self.media.print_calls,1)

    def test_mail_persists_after_restart(self):
        self.box.send(dict(id='one',sender='alma',recipient='andy',kind='voice',audio='test'))
        another=Mailbox(self.temp.name)
        self.assertEqual(another.inbox('andy')[0]['id'],'one')
        another.close()


if __name__=='__main__':unittest.main()
