"""Persistent per-child mailbox; cloud delivery and print receipts are separate."""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path


class Mailbox:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.root / 'mail.sqlite', check_same_thread=False)
        self.db.execute('''CREATE TABLE IF NOT EXISTS mail (
            id TEXT PRIMARY KEY, sender TEXT NOT NULL, recipient TEXT NOT NULL,
            created REAL NOT NULL, seen INTEGER NOT NULL DEFAULT 0, payload TEXT NOT NULL)''')
        self.db.execute('CREATE TABLE IF NOT EXISTS preferences (person TEXT PRIMARY KEY, language TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS mail_notifications (id TEXT PRIMARY KEY, recipient TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS recording_preferences (person TEXT PRIMARY KEY, seconds INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS rewards (id TEXT PRIMARY KEY, person TEXT NOT NULL, number INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(person, number))')
        # Repair older rows only where a completed print is already recorded.
        printed = [(ident,) for ident, payload in self.db.execute('SELECT id,payload FROM mail WHERE seen=0')
                   if json.loads(payload).get('printed') is True]
        self.db.executemany('UPDATE mail SET seen=1 WHERE id=?', printed)
        self.db.executemany('DELETE FROM mail_notifications WHERE id=?', printed)
        self.db.commit()

    def award(self, person, name, game, language):
        from rewards import render_reward
        with self.lock, self.db:
            number = self.db.execute('SELECT COALESCE(MAX(number),0)+1 FROM rewards WHERE person=?', (person,)).fetchone()[0]
            ident = uuid.uuid4().hex
            reward = dict(id=ident, person=person, number=number, game=game, language=language,
                          kind='drawing', reward=True, local_print=True,
                          image=str(self.root/'rewards'/(ident+'.png')))
            render_reward(reward, name, reward['image'])
            self.db.execute('INSERT INTO rewards VALUES (?,?,?,?)', (ident, person, number, json.dumps(reward)))
            return reward

    def latest_reward(self, person):
        with self.lock:
            row = self.db.execute('SELECT payload FROM rewards WHERE person=? ORDER BY number DESC LIMIT 1', (person,)).fetchone()
            return json.loads(row[0]) if row else None

    def send(self, draft):
        with self.lock, self.db:
            inserted = self.db.execute('INSERT OR IGNORE INTO mail (id,sender,recipient,created,payload) VALUES (?,?,?,?,?)',
                            (draft['id'], draft['sender'], draft['recipient'], time.time(), json.dumps(draft)))
            if inserted.rowcount and (draft.get('remote') or draft.get('cloud_message') or draft.get('remote_notice')):
                self.db.execute('INSERT OR IGNORE INTO mail_notifications VALUES (?,?)', (draft['id'], draft['recipient']))
        return {'id': draft['id'], 'status': 'saved_locally', 'transport': 'local-bench'}

    def language(self, person):
        with self.lock:
            row=self.db.execute('SELECT language FROM preferences WHERE person=?',(person,)).fetchone()
        return row[0] if row else 'en'

    def set_language(self, person, language):
        from languages import LANGUAGES
        if language not in LANGUAGES:raise ValueError('Unknown language')
        with self.lock,self.db:
            self.db.execute('INSERT INTO preferences VALUES (?,?) ON CONFLICT(person) DO UPDATE SET language=excluded.language',(person,language))

    def recording_seconds(self, person):
        with self.lock:
            row = self.db.execute('SELECT seconds FROM recording_preferences WHERE person=?', (person,)).fetchone()
        return row[0] if row and row[0] in (10, 15, 30, 60) else 30

    def set_recording_seconds(self, person, seconds):
        if type(seconds) is not int or seconds not in (10, 15, 30, 60):
            raise ValueError('Unknown recording time')
        with self.lock, self.db:
            self.db.execute('INSERT INTO recording_preferences VALUES (?,?) ON CONFLICT(person) DO UPDATE SET seconds=excluded.seconds', (person, seconds))

    def get(self, ident):
        with self.lock:
            row = self.db.execute('SELECT payload,seen FROM mail WHERE id=?', (ident,)).fetchone()
        return dict(json.loads(row[0]), seen=bool(row[1])) if row else None

    def inbox(self, person, sender=None, unread=False):
        with self.lock:
            rows = self.db.execute('SELECT payload,seen FROM mail WHERE recipient IN (?,?) ORDER BY created',
                                   (person, getattr(self, 'shared_recipient', person))).fetchall()
        return [dict(json.loads(p), seen=bool(seen)) for p, seen in rows
                if (not unread or not seen) and (sender is None or json.loads(p)['sender'] == sender)]

    def mark_seen(self, message):
        with self.lock, self.db:
            self.db.execute('UPDATE mail SET seen=1 WHERE id=?', (message['id'],))
            self.db.execute('DELETE FROM mail_notifications WHERE id=?', (message['id'],))

        message['seen'] = True

        if getattr(self, 'on_read', None):
            self.on_read(message)

    def begin_print_attempt(self, message):
        with self.lock, self.db:
            current = self.get(message['id'])
            if not current:
                raise ValueError('Message not in mailbox')
            if not current.get('print_attempt'):
                # Preserve the original receipt for the first copy, including upgrades.
                current['print_attempt'] = uuid.uuid4().hex if current.get('printed') else message['id']
                self.db.execute('UPDATE mail SET payload=? WHERE id=?', (json.dumps(current), message['id']))
            return current['print_attempt']

    def mark_printed(self, message):
        with self.lock, self.db:
            current = self.get(message['id'])
            if not current:
                raise ValueError('Message not in mailbox')
            current['printed'] = True
            current['seen'] = True
            self.db.execute('UPDATE mail SET payload=?,seen=1 WHERE id=?', (json.dumps(current), message['id']))
            self.db.execute('DELETE FROM mail_notifications WHERE id=?', (message['id'],))
        message.update(printed=True, seen=True)
        if getattr(self, 'on_print', None):
            self.on_print(current)
        # A receipt-storage failure must keep Retry tied to the completed copy.
        # Only a fully acknowledged action may create a new Print Again ID.
        attempt = current.get('print_attempt')
        if attempt:
            with self.lock, self.db:
                latest = self.get(message['id'])
                if latest.get('print_attempt') == attempt:
                    latest.pop('print_attempt')
                    self.db.execute('UPDATE mail SET payload=? WHERE id=?', (json.dumps(latest), message['id']))
            message.pop('print_attempt', None)

    def notifications(self):
        with self.lock:
            return self.db.execute('SELECT id,recipient FROM mail_notifications ORDER BY rowid').fetchall()

    def acknowledge_notifications(self, ids):
        with self.lock, self.db:
            self.db.executemany('DELETE FROM mail_notifications WHERE id=?', [(ident,) for ident in ids])

    def close(self):
        self.db.close()
