from languages import DRAW_PROMPT, TALK_PROMPT
"""Six-key interaction model, independent of USB and the AI provider.

All transitions are serialized. Key-up is tied to the screen where key-down
occurred: a press during generation can never become Send when it finishes.
"""
import copy
import logging
from pathlib import Path
import threading
import time
import uuid
from games import new_round, COLORS
from riddles import ICONS
from languages import LANGUAGES, translate, label


def tile(label='', icon=None, **kw):
    return dict(label=label, icon=icon, **kw)


class Controller:
    def __init__(self, family, mailbox, media):
        self.family, self.mailbox, self.media = family, mailbox, media
        self.people = {p['id']: p for p in family['children']}
        self.houses = {h['id']: h for h in family['houses']}
        self.station = family['station']
        self.person = None
        self.recipient = None
        self.house = None
        self.mode = 'home'
        self.revision = 0
        self.lock = threading.RLock()
        self.down = {}
        self.block_until = 0
        self.draft = None
        self.current = None
        self.mail = []
        self.mail_index = 0
        self.note = ''
        self.stage = ''
        self.record_key = None
        self.record_started = 0
        self.record_latched = False
        self.job = None
        self.return_mode = 'review'
        self.failed_mode = None
        self.closed = False
        self.round = None
        self.delivery = None
        self.game_correct = False
        self.game_score = 0
        self.wrong_keys = set()
        self.language = self.mailbox.language('@station')
        self.round_timer = None

    def children(self, house):
        return [p['id'] for p in self.family['children'] if p['house'] == house]

    def remote_houses(self):
        return [h for h in self.houses if h != self.station]

    def speak(self, text):
        self.media.cue(translate(text,self.language))

    def transition(self, mode, cue=None):
        if mode not in ('home', 'personal', 'houses', 'games', 'people', 'compose', 'sent', 'print_done'):
            if not getattr(self, '_update_guard', None):
                import os
                if os.environ.get('PAPERDROP_FIRMWARE_VERSION'):
                    from update_guard import acquire
                    self._update_guard = acquire()
        elif getattr(self, '_update_guard', None):
            self._update_guard.close()
            self._update_guard = None
        if self.round_timer:
            self.round_timer.cancel()
            self.round_timer=None
        self.mode = mode
        self.revision += 1
        self.block_until = time.monotonic() + .22
        logging.info('screen=%s revision=%d', mode, self.revision)
        if cue:
            self.speak(cue)

    def unread(self, person, sender=None):
        return len(self.mailbox.inbox(person, sender=sender, unread=True)) if person else 0

    def person_tile(self, person, **kw):
        return tile(self.people[person]['name'], person=person, **kw)

    def sender_tile(self, sender, **kw):
        if sender in self.houses:
            return tile(self.houses[sender]['name'], house=sender, **kw)
        return self.person_tile(sender, **kw)

    def sender_name(self, sender):
        return (self.houses.get(sender) or self.people[sender])['name']

    def snapshot(self):
        with self.lock:
            tiles = [tile(disabled=True) for _ in range(6)]
            name = self.people[self.person]['name'] if self.person else ''
            target = self.people[self.recipient]['name'] if self.recipient else ''
            heading, hint = '', ''
            picture = None
            busy = self.mode in ('arming', 'recording', 'finishing', 'generating', 'sending', 'playing', 'printing')
            if self.mode == 'home':
                heading = 'PaperDrop at home'
                hint = 'Your face opens learning and your latest postcards. Choose a house to send, or tap Draw & Print.'
                for i, p in enumerate(self.children(self.station)):
                    tiles[i] = self.person_tile(p, badge=self.unread(p), selected=p==self.person)
                for i, house in enumerate(self.remote_houses()):
                    tiles[3+i] = tile(self.houses[house]['name'],house=house)
                tiles[5] = tile('Draw & Print','Drawing',color='#f0cb86')
            elif self.mode == 'personal':
                heading, hint = f'{name}’s space', 'Letters, numbers, your latest voice note and your latest picture.'
                tiles[0] = tile('Games','Gamepad2',color='#c8b8e2')
                tiles[1] = tile(LANGUAGES[self.language],'Languages',color='#b7d8c7')
                tiles[2] = tile('Draw & Print','Drawing',color='#f0cb86')
                for key,kind,icon in [(3,'voice','Mic'),(4,'drawing','Pencil')]:
                    message = self.latest(kind)
                    if message:
                        tiles[key] = self.sender_tile(message['sender'],type_badge=icon,demo=message.get('demo',False),
                            badge=not message['seen'])
                tiles[5] = tile('Home','Home')
            elif self.mode == 'languages':
                heading, hint = 'Choose your language', 'Your choice is saved for you.'
                for i,(code,native_name) in enumerate(LANGUAGES.items()):
                    tiles[i]=tile(native_name,'Languages',selected=code==self.language,color=['#c7dfed','#d4c5e8','#f6d39d','#b7d8c7','#edc6bc'][i])
                tiles[5]=tile('Back','ArrowLeft')
            elif self.mode == 'houses':
                heading, hint = 'Choose a cousin’s house', f'Sending as {name}. Choose a house, then a cousin.'
                for i, house in enumerate(self.remote_houses()):
                    tiles[i] = tile(self.houses[house]['name'],house=house,
                                    badge=sum(self.unread(self.person,p) for p in self.children(house)))
                tiles[5] = tile('Home','Home')
            elif self.mode == 'games':
                heading, hint = f'Let’s play, {name}', 'Choose colors, letters, numbers, or riddles. Every game has a Home button.'
                tiles[0] = tile('Colors','Palette',color='#f0cb86')
                tiles[1] = tile('Letters',symbol='ABC')
                tiles[2] = tile('Numbers',symbol='123')
                tiles[3] = tile('Riddles','HelpCircle',color='#b7d8c7')
                if self.mailbox.latest_reward(self.person):tiles[4] = tile('My prize','Star')
                tiles[5] = tile('Home','Home')
            elif self.mode == 'game':
                heading, hint = self.round['prompt'], 'Tap an answer. Repeat says the question again. Home returns to your space.'
                for i,choice in enumerate(self.round['choices']):
                    tiles[i] = (tile(choice.capitalize(),color=COLORS[choice]) if self.round['kind']=='colors'
                                else tile(choice,ICONS[choice],color=['#c7dfed','#f6d39d','#d4c5e8','#b7d8c7'][i]) if self.round['kind']=='riddles'
                                else tile(symbol=str(choice),color=['#c7dfed','#f6d39d','#d4c5e8','#b7d8c7'][i],dots=choice if self.round['kind']=='numbers' else None))
                    if i in self.wrong_keys:tiles[i]['disabled']=True
                    if self.game_correct:
                        tiles[i]['disabled'] = True
                        tiles[i]['selected'] = choice==self.round['target']
                tiles[4] = tile(f'{self.game_score}/5' if self.game_correct else f'Hear {self.game_score}/5','Star' if self.game_correct else 'Volume2',stars=self.game_score,disabled=self.game_correct)
                tiles[5] = tile('Home','Home')
                if self.game_correct:
                    heading, hint = 'You found it!', 'The next round starts automatically. Home chooses something else.'
            elif self.mode == 'game_win':
                heading, hint = label('Five stars!',self.language), 'Your unique prize is saved. Press Print to print it, or play again.'
                picture = self.draft.get('image') if self.draft else None
                tiles = [tile('Wonderful!', 'Star', color='#f0cb86') for _ in range(6)]
                tiles[0] = tile('Print','Check',color='#85b8a2')
                tiles[1] = tile('My prize',image=picture)
                tiles[2] = tiles[3] = tile(disabled=True)
                tiles[4] = tile('Play again','RotateCcw',color='#85b8a2')
                tiles[5] = tile('Home','Home')
            elif self.mode == 'people':
                heading = f'Who in {self.houses[self.house]["name"]}?'
                hint = 'Choose a face. An envelope means they sent you something.'
                for i, p in enumerate(self.children(self.house)):
                    tiles[i] = self.person_tile(p, badge=self.unread(self.person, p))
                tiles[3] = tile('Back', 'ArrowLeft')
                tiles[4] = self.person_tile(self.person, disabled=True, selected=True) if self.person else tile(disabled=True)
                tiles[5] = tile('Home', 'Home')
            elif self.mode == 'sender':
                heading, hint = 'Who is sending?', 'Choose your face so your cousin knows who sent the mail.'
                for i, person in enumerate(self.children(self.station)):
                    tiles[i] = self.person_tile(person)
                tiles[5] = tile('Home', 'Home')
            elif self.mode == 'compose':
                heading, hint = f'For {target}', 'Tap Talk for a voice note or Draw for a picture. Wait for red, speak, then tap Done. You can also hold and release.'
                tiles = [self.person_tile(self.recipient, disabled=True), tile('Talk', 'Mic', color='#85b8a2'),
                         tile('Draw', 'Drawing', color='#f0cb86'),
                         tile('Their mail', 'Mail', badge=self.unread(self.person, self.recipient)),
                         tile('Back', 'ArrowLeft'), tile('Home', 'Home')]
            elif self.mode in ('arming', 'recording'):
                remaining = max(0, 15-int(time.monotonic()-self.record_started))
                arming = self.mode=='arming'
                heading = 'Listen, then wait for red…' if arming else ('Describe your picture' if self.draft['kind'] == 'drawing' else 'Recording your voice')
                hint = 'Wait for the red microphone before speaking.' if arming else 'Talk into the Pi microphone. Tap the red button when finished. Nothing is sent yet.'
                tiles[0] = self.person_tile(self.recipient, disabled=True) if self.recipient else tile('Print here','Pencil',disabled=True)
                tiles[self.record_key] = tile('Wait' if arming else 'Done', 'Loader2' if arming else 'Mic', color='#f0cb86' if arming else '#e89179', disabled=arming)
                tiles[3] = tile('Hold on' if arming else f'{remaining}s', 'Mic', disabled=True, color='#f0cb86' if arming else '#e89179')
                tiles[4 if self.record_key==5 else 5] = tile('Delete', 'Trash2')
            elif self.mode in ('finishing', 'generating', 'sending', 'playing', 'printing'):
                heading = {'finishing':'Keeping your recording…', 'generating':self.stage or 'Making your picture…',
                           'sending':'Sending your postcard…', 'playing':'Playing…', 'printing':'Sending to the printer…'}[self.mode]
                hint = 'One moment. Buttons are resting.'
                tiles = [tile('', 'Loader2', disabled=True, color='#f0cb86') for _ in range(6)]
                if self.mode=='playing' and self.current:
                    tiles[0] = self.sender_tile(self.current['sender'],disabled=True,type_badge='Mic')
                    heading = f"From {self.sender_name(self.current['sender'])}"
                elif self.recipient:
                    tiles[0] = self.person_tile(self.recipient, disabled=True)
                tiles[4]['label'] = 'Drawing' if self.mode=='generating' else 'Wait'
            elif self.mode == 'review':
                heading, hint = f'Ready for {target}?', 'Nothing is sent yet. Green sends once. Redo records a new idea. Delete throws this draft away.'
                picture = self.draft.get('image')
                tiles = [self.person_tile(self.recipient, disabled=True),
                         tile('Preview', 'ZoomIn' if picture else 'Volume2', image=picture),
                         tile('Listen', 'Play'), tile('Redo', 'RotateCcw'),
                         tile('Delete', 'Trash2', color='#e89179'), tile('Send', 'Send', color='#85b8a2')]
            elif self.mode == 'preview':
                source = self.draft if self.return_mode in ('review','print_review','print_done','game_win') else self.current
                picture = source.get('image')
                heading, hint = 'Your picture, across all six keys', 'Tap any button to return. This never sends the picture.'
                tiles = [tile('Return', mosaic=picture, piece=i) for i in range(6)]
            elif self.mode == 'incoming':
                sender = self.current['sender']
                picture = self.current.get('image')
                heading = f'For {name}, from {self.sender_name(sender)}'
                hint = f'{self.mail_index+1} of {len(self.mail)} · Play or preview, then reply when you want.'
                tiles = [self.sender_tile(sender, disabled=True), tile('Preview' if picture else 'Listen', 'ZoomIn' if picture else 'Play', image=picture),
                         tile('Listen', 'Play', disabled=not self.current.get('audio')), tile('Reply', 'Mic', color='#85b8a2'),
                         tile('Next', 'ChevronRight', disabled=len(self.mail)<2), tile('Home', 'Home')]
            elif self.mode == 'print_review':
                heading, hint = 'Ready to print?', 'Look at your picture, then press the green Print button. Nothing has printed yet.'
                picture = self.draft.get('image')
                tiles[1] = tile('Picture', 'ZoomIn', image=picture)
                tiles[3] = tile('Redo', 'RotateCcw')
                tiles[4] = tile('Delete', 'Trash2', color='#e89179')
                tiles[5] = tile('Print', 'Check', color='#85b8a2')
            elif self.mode == 'print_done':
                heading, hint = 'Sent to the printer', 'Your picture is in the printer queue. Tap the picture to look, or Home to start again.'
                picture = self.draft.get('image')
                tiles[1] = tile('Picture','ZoomIn',image=picture)
                tiles[5] = tile('Home','Home')
            elif self.mode == 'sent':
                heading, hint = 'Practice voice note saved', 'This practice voice note is saved on this PaperDrop.'
                if self.delivery:
                    receipt = self.media.delivery_status(self.delivery['id']) or self.delivery
                    status = receipt.get('status')
                    heading = {'received':'Mail received by '+target, 'read':'Played by '+target, 'printed':'Printed at '+self.houses[self.house]['name'], 'printing':'Printing for '+target, 'queued':'Queued for '+target, 'sent':'Sent to '+self.houses[self.house]['name'], 'dispatching':'Checking delivery', 'failed':'The other printer needs help'}.get(status,'Checking delivery')
                    hint = 'To: '+target+' · From: '+self.sender_name(self.person or self.station)
                    if status=='queued':hint += ' · Waiting for their PaperDrop to reconnect.'
                    elif status=='sent':hint += ' · Waiting for their PaperDrop to confirm.'
                    elif status=='printed':hint += ' · Their device confirmed printing.'
                tiles[0] = self.person_tile(self.recipient, disabled=True)
                delivery_label = {'queued':'Queued','sent':'Sent','printing':'Printing','printed':'Printed','received':'Received','read':'Played','dispatching':'Checking','failed':'Needs help'}.get(status,'Checking') if self.delivery else 'Saved'
                icon = 'Check' if delivery_label in ('Saved','Printed') else ('AlertCircle' if delivery_label=='Needs help' else 'Send')
                tiles[1] = tile(delivery_label, icon, color='#f0cb86' if delivery_label in ('Queued','Checking') else '#85b8a2', disabled=True)
                tiles[5] = tile('Home', 'Home')
            elif self.mode == 'error':
                heading, hint = 'Let’s try that again', self.note
                picture = self.draft.get('image') if self.draft else None
                tiles[0] = tile('Picture', image=picture, disabled=True) if picture else tile(disabled=True)
                tiles[1] = tile('Oops', 'AlertCircle', disabled=True, color='#e89179')
                tiles[3] = tile('Retry', 'RotateCcw')
                tiles[4] = tile('Delete', 'Trash2')
                tiles[5] = tile('Home', 'Home')
            if self.mode=='personal' and any(t.get('demo') for t in tiles):
                hint += ' Includes sample postcards for this demonstration.'
            if self.mode=='preview' and self.return_mode in ('personal','incoming') and self.current:
                heading = f"From {self.sender_name(self.current['sender'])} to {name}"
            demo = bool(self.current and self.current.get('demo') and self.mode in ('playing','preview','incoming'))
            if demo:
                heading = 'Example · '+heading
                hint = 'Sample postcard for testing, not a real message from this cousin. '+hint
            if self.mode=='game' and not self.game_correct:heading=translate(self.round['prompt'],self.language)
            for item in tiles:
                if item.get('label') and not item.get('person') and not item.get('house'):
                    item['label']=label(item['label'],self.language)
            return dict(demo=demo,mode=self.mode, revision=self.revision, tiles=tiles, heading=heading, hint=hint,
                        station=self.station, person=self.person, recipient=self.recipient, language=self.language,
                        busy=busy, picture=picture, note=self.note, local_only=not hasattr(self.media,'send_drawing'),
                        record_seconds=round(time.monotonic()-self.record_started,1) if self.mode=='recording' else 0)

    def home(self):
        self.delivery = None
        self.discard()
        self.current = None
        self.note = ''
        self.recipient = None
        self.media.stop_audio()
        self.transition('home')

    def latest(self, kind):
        messages = [m for m in self.mailbox.inbox(self.person) if m['kind']==kind] if self.person else []
        unread = [m for m in messages if not m['seen']]
        return (unread or messages)[-1] if messages else None

    def hub(self):
        if not self.person:
            self.home()
            return
        self.discard()
        self.current = self.recipient = None
        self.media.stop_audio()
        self.transition('personal')

    def feedback_delay(self):
        text=translate('You earned a star!',self.language)
        return max(2.4,self.media.cue_duration(text)+1.6) if hasattr(self.media,'cue_duration') else 2.4

    def advance_round(self, revision):
        with self.lock:
            if not self.closed and self.mode=='game' and self.game_correct and self.revision==revision:
                self.start_game(self.round['kind'])

    def start_game(self, kind):
        if self.mode != 'game':
            self.game_score=0
            self.discard()
        self.wrong_keys=set()
        previous = self.round.get('target') if self.round and self.round['kind']==kind else None
        self.round = new_round(kind,previous)
        self.game_correct = False
        self.transition('game',self.round['prompt'])

    def discard(self):
        # Only unpublished draft media are removed. Sent and received media survive.
        if self.draft and not self.draft.get('reward'):
            if self.draft.get('image') and hasattr(self.media, 'discard_image'):
                self.media.discard_image(self.draft['image'])
            for field in ('audio', 'image'):
                if self.draft.get(field):
                    Path(self.draft[field]).unlink(missing_ok=True)
        self.draft = None

    def switch_station(self, station):
        with self.lock:
            if self.mode not in ('home','personal','houses','games','game','people','compose','incoming','sent','sender','print_done'):
                raise ValueError('Finish or delete the current postcard first')
            if station not in self.houses:
                raise ValueError('Unknown station')
            self.media.stop_audio()
            self.station = station
            self.person = self.recipient = None
            self.home()

    def press(self, key, pressed):
        if key not in range(6):
            return
        with self.lock:
            if self.closed:
                return
            now = time.monotonic()
            if pressed:
                if key in self.down:
                    return
                allowed = now >= self.block_until and not self.snapshot()['tiles'][key].get('disabled', False)
                self.down[key] = (self.revision, allowed)
                if allowed and self.mode == 'compose' and key in (1,2):
                    self.start_recording(key, 'voice' if key==1 else 'drawing')
                elif allowed and ((self.mode=='home' and key==5) or (self.mode=='personal' and key==2)):
                    self.recipient = None
                    self.start_recording(key,'drawing',local_print=True)
                return
            started = self.down.pop(key, None)
            if self.mode in ('arming', 'recording') and key == self.record_key:
                if self.mode == 'arming' or (not self.record_latched and now-self.record_started < .8):
                    self.record_latched = True
                    return
                self.finish_recording()
                return
            if self.mode in ('arming','recording') and key==(4 if self.record_key==5 else 5) and started and started[1]:
                self.finish_recording(discard=True)
                return
            if not started or not started[1] or started[0] != self.revision:
                return
            self.act(key)

    def act(self, key):
        if self.mode == 'home':
            locals_ = self.children(self.station)
            if key < len(locals_):
                self.person = locals_[key]
                self.language = self.mailbox.language(self.person)
                self.mailbox.set_language('@station',self.language)
                self.transition('personal', f'Hello {self.people[self.person]["name"]}. Choose letters, numbers, or a postcard.')
            elif key in (3,4):
                self.house = self.remote_houses()[key-3]
                self.transition('people',f'Who in {self.houses[self.house]["name"]}?')
        elif self.mode == 'personal':
            if key==0:
                self.transition('games','Let’s play! Choose colors, letters, numbers, or riddles.')
            elif key==1:
                self.transition('languages','Choose your language.')
            elif key in (3,4):
                message = self.latest('voice' if key==3 else 'drawing')
                if message:
                    self.current=message
                    self.mail = [m for m in reversed(self.mailbox.inbox(self.person)) if m['kind'] == message['kind']]
                    self.mail.sort(key=lambda m: m['seen'])
                    self.mail_index=0
                    self.current=self.mail[0]
                    if key==3:
                        self.transition('incoming')
                    else:
                        self.transition('incoming')
            elif key == 5:
                self.home()
        elif self.mode == 'languages':
            if key<5:
                self.language=list(LANGUAGES)[key]
                self.mailbox.set_language(self.person,self.language)
                self.mailbox.set_language('@station',self.language)
                self.transition('personal','Your language is English. Let’s play!')
            elif key==5:self.hub()
        elif self.mode == 'houses':
            if key in (0,1):
                self.house = self.remote_houses()[key]
                self.transition('people', f'Who in {self.houses[self.house]["name"]}?')
            elif key == 5:
                self.hub()
        elif self.mode == 'games':
            if key in (0,1,2,3):
                self.start_game(['colors','letters','numbers','riddles'][key])
            elif key == 4:
                reward=self.mailbox.latest_reward(self.person)
                if reward:
                    self.draft=reward
                    self.round={'kind':reward['game']}
                    self.transition('game_win')
            elif key == 5:
                self.hub()
        elif self.mode == 'game':
            if key == 5:
                self.hub()
            elif key == 4:
                if not self.game_correct:
                    self.speak(self.round['prompt'])
            elif key < 4 and not self.game_correct and key not in self.wrong_keys:
                if self.round['choices'][key] == self.round['target']:
                    self.game_correct = True
                    self.game_score += 1
                    if self.game_score >= 5:
                        self.transition('game_win')
                        try:
                            self.draft=self.mailbox.award(self.person,self.people[self.person]['name'],self.round['kind'],self.language)
                        except Exception:
                            self.fail('Your prize could not be saved. Please ask a grown-up for help.')
                            return
                        self.media.cue_sequence([translate('Five stars! You earned a special prize. Press the green button to print it.',self.language)],star=True)
                    else:
                        self.transition('game')
                        self.media.cue_sequence([translate('You earned a star!',self.language)],star=True)
                        self.round_timer=threading.Timer(self.feedback_delay(),self.advance_round,args=(self.revision,))
                        self.round_timer.daemon=True
                        self.round_timer.start()
                else:
                    self.wrong_keys.add(key)
                    self.transition('game')
                    self.media.cue_sequence([translate('Try again. Here is the same question.',self.language),translate(self.round['prompt'],self.language)])
        elif self.mode == 'game_win':
            if key == 0:self.print_draft()
            elif key == 1:
                self.return_mode='game_win'
                self.transition('preview')
            elif key == 4:self.start_game(self.round['kind'])
            elif key == 5:self.hub()
        elif self.mode == 'people':
            people = self.children(self.house)
            if key < len(people):
                self.recipient = people[key]
                if self.person and self.unread(self.person, self.recipient):
                    self.open_mail(self.recipient)
                else:
                    self.compose()
            elif key in (3,5):
                self.home()
        elif self.mode == 'sender':
            people = self.children(self.station)
            if key < len(people):
                self.person = people[key]
                self.compose()
            elif key == 5:
                self.home()
        elif self.mode == 'compose':
            if key == 3:
                self.open_mail(self.recipient)
            elif key == 4:
                self.transition('people')
            elif key == 5:
                self.hub()
        elif self.mode in ('arming', 'recording') and key == 5:
            self.finish_recording(discard=True)
        elif self.mode == 'review':
            if key == 1 and self.draft.get('image'):
                self.return_mode = 'review'
                self.transition('preview', 'Here is your picture. Tap any button to go back.')
            elif key in (1,2):
                self.play(self.draft, 'review')
            elif key in (3,4):
                self.discard()
                self.compose()
            elif key == 5:
                self.send()
        elif self.mode == 'preview':
            if self.return_mode == 'incoming':
                self.mailbox.mark_seen(self.current)
            self.transition(self.return_mode)
        elif self.mode == 'incoming':
            if key == 1 and self.current.get('image'):
                self.return_mode = 'incoming'
                self.transition('preview', 'Tap any button to go back.')
            elif key in (1,2) and self.current.get('audio'):
                self.play(self.current, 'incoming')
            elif key == 3:
                sender = self.current['sender']
                if sender in self.houses:
                    self.house = sender
                    self.recipient = None
                    self.transition('people', f'Who in {self.houses[sender]["name"]}?')
                else:
                    self.recipient = sender
                    self.house = self.people[sender]['house']
                    self.compose()
            elif key == 4 and len(self.mail)>1:
                self.mail_index = (self.mail_index+1) % len(self.mail)
                self.current = self.mail[self.mail_index]
                self.transition('incoming')
            elif key == 5:
                self.hub()
        elif self.mode == 'print_review':
            if key == 1:
                self.return_mode = 'print_review'
                self.transition('preview')
            elif key in (3,4):
                self.home()
            elif key == 5:
                self.print_draft()
        elif self.mode == 'print_done':
            if key==1:
                self.return_mode='print_done'
                self.transition('preview','Here is your picture. Tap any button to go back.')
            elif key==5:
                self.home()
        elif self.mode == 'sent' and key == 5:
            self.hub()
        elif self.mode == 'error':
            if key==3 and self.failed_mode=='printing':
                self.print_draft()
            elif key == 3 and self.failed_mode == 'sending' and self.draft:
                self.send()
            elif key == 3 and self.failed_mode == 'playing':
                self.transition('personal' if self.current else 'review')
            elif key == 3 and self.draft and self.draft.get('duration') and self.draft['kind']=='drawing':
                self.generate()
            elif key in (3,4):
                self.discard()
                self.compose() if self.recipient else self.home()
            elif key == 5:
                self.home()

    def compose(self):
        if hasattr(self.media, 'send_mail') and not self.person:
            self.transition('sender')
            return
        self.note = ''
        self.transition('compose', f'For {self.people[self.recipient]["name"]}. Tap the microphone to talk, or the picture to draw. Tap again when you are done.')

    def open_mail(self, sender=None):
        mail = self.mailbox.inbox(self.person, sender=sender)
        if not mail:
            self.speak('No mail yet.')
            return
        self.mail = sorted(mail, key=lambda m:m['seen'])
        self.mail_index = 0
        self.current = self.mail[0]
        self.transition('incoming', 'There is a postcard for you. Press play to listen, or the picture to see it.')

    def start_recording(self, key, kind, local_print=False):
        self.discard()
        ident = uuid.uuid4().hex
        self.draft = dict(id=ident, sender=self.person or self.station, recipient=self.recipient, kind=kind,
                          audio=str(self.mailbox.root / (ident+'.wav')),local_print=local_print)
        self.record_key = key
        self.record_started = time.monotonic()
        self.record_latched = False
        self.transition('arming')
        token = ident
        try:
            player = self.media.start_guidance(translate(DRAW_PROMPT if kind == 'drawing' else TALK_PROMPT, self.language))
        except Exception:
            self.fail('Oops. Please try again.')
            return
        def ready():
            try:
                if player is not None and player.wait(timeout=30) != 0:
                    raise RuntimeError('Guidance playback failed')
                with self.lock:
                    if self.closed or self.mode != 'arming' or not self.draft or self.draft['id'] != token:
                        return
                    self.media.start_recording(self.draft['audio'])
                self.media.wait_recording_ready()
                with self.lock:
                    if self.mode != 'arming' or not self.draft or self.draft['id'] != token:
                        return
                    self.record_started = time.monotonic()
                    self.transition('recording')
                    def timeout():
                        with self.lock:
                            if self.mode == 'recording' and self.draft and self.draft['id'] == token:
                                self.finish_recording()
                    timer = threading.Timer(15, timeout)
                    timer.daemon = True
                    timer.start()
            except Exception:
                with self.lock:
                    if self.mode == 'arming' and self.draft and self.draft['id'] == token:
                        self.media.stop_audio()
                        self.fail('Oops. Please try again.')
        threading.Thread(target=ready, daemon=True).start()

    def background(self, operation, success):
        token = self.job = uuid.uuid4().hex
        def run():
            try:
                result = operation()
                with self.lock:
                    if self.job==token and not self.closed:
                        success(result)
            except Exception as exc:
                logging.warning('operation_failed type=%s message=%s', type(exc).__name__, exc)
                with self.lock:
                    if self.job==token and not self.closed:
                        self.fail(getattr(exc, 'public_message', None) or ('The printer is unavailable. Your picture is saved; Retry sends this same picture.' if self.mode=='printing' else 'That did not work. Try again, or delete this postcard.'))
        threading.Thread(target=run, daemon=True).start()

    def finish_recording(self, discard=False):
        if self.mode == 'arming':
            self.media.stop_audio()
        path = self.draft['audio']
        self.transition('finishing')
        def success(duration):
            if discard:
                self.discard()
                self.compose() if self.recipient else self.home()
            else:
                self.draft['duration'] = duration
                if self.draft['kind'] == 'drawing':
                    self.generate()
                else:
                    self.transition('review', 'Listen to your note, then press the green button to send.')
        def finish():
            if discard:
                try:
                    self.media.finish_recording(path)
                except Exception:
                    pass
                return 0
            return self.media.finish_recording(path)
        self.background(finish, success)

    def generate(self):
        draft = self.draft
        target = self.mailbox.root / (draft['id']+'.png')
        self.stage = 'Listening to your idea…'
        self.transition('generating', 'I am making your picture. The buttons are resting.')
        def progress(stage):
            with self.lock:
                if self.mode=='generating' and self.draft is draft:
                    self.stage = stage
        def success(prompt):
            draft['image'], draft['prompt'] = str(target), prompt
            if draft.get('local_print'):
                self.transition('print_review', 'Here is your picture. Press the green button to print, or the picture to look closer.')
                self.block_until = time.monotonic()+.8
                return
            self.return_mode = 'review'
            self.transition('preview', 'Here is your picture. Tap any button to see the send button.')
            self.block_until = time.monotonic()+.8
        self.background(lambda:self.media.draw(draft['audio'], target, progress), success)

    def play(self, message, return_mode):
        self.transition('playing')
        def success(_):
            if return_mode in ('incoming','personal'):
                self.mailbox.mark_seen(message)
            self.transition(return_mode)
        self.background(lambda:self.media.play(message['audio']), success)

    def print_draft(self):
        draft=self.draft
        if self.station != 'portugal' and not getattr(self.media,'local_printer',False):
            self.fail('Only the Portugal PaperDrop Epson is configured for printing.')
            self.failed_mode='printing'
            return
        self.transition('printing','Your picture is ready. Sending it to the printer.')
        def success(receipt):
            self.transition('print_done','Your picture has been sent to the printer.')
        self.background(lambda:self.media.print_image(draft['image'],draft['id']),success)

    def deliver_saved(self, ident):
        # Grown-up recovery for a drawing saved before real house delivery existed.
        with self.lock:
            if self.mode != 'home' or not hasattr(self.media,'send_drawing'):
                raise ValueError('Return home before delivering a saved drawing')
            draft = self.mailbox.get(ident)
            if not draft or draft['kind'] != 'drawing' or draft['sender'] != self.family['station']:
                raise ValueError('Not a drawing from this house')
            self.station = self.family['station']
            self.recipient = draft['recipient']
            self.house = self.people[self.recipient]['house']
            self.transition('sending')
            def success(receipt):
                self.delivery = dict(receipt,id=draft['id'])
                self.transition('sent','Your picture is on its way.')
            self.background(lambda:self.media.send_drawing(draft,self.family),success)

    def send(self):
        draft = copy.deepcopy(self.draft)
        draft['sender'] = self.person or self.station
        self.transition('sending')
        remote = hasattr(self.media, 'send_mail') or (draft['kind']=='drawing' and hasattr(self.media,'send_drawing'))
        def success(receipt):
            self.draft = None  # published media now belongs to the mailbox
            self.delivery = dict(receipt,id=draft['id']) if remote else None
            self.transition('sent')
        def deliver():
            receipt = self.media.send_mail(draft,self.family) if hasattr(self.media, 'send_mail') else (self.media.send_drawing(draft,self.family) if remote else self.mailbox.send(draft))
            if remote:self.mailbox.send(dict(draft,delivery=receipt))
            return receipt
        self.background(deliver, success)

    def fail(self, note):
        self.failed_mode = self.mode
        self.note = note
        self.transition('error', 'Oops. Please try again.')

    def close(self):
        if getattr(self, '_update_guard', None):
            self._update_guard.close()
            self._update_guard = None
        with self.lock:
            self.closed = True
            if self.round_timer:self.round_timer.cancel()
            self.job = None
            self.media.close()
