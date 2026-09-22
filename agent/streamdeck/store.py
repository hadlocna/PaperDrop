"""Local bench transport. No remote delivery or print is implied by a receipt."""
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
        self.db.execute('CREATE TABLE IF NOT EXISTS rewards (id TEXT PRIMARY KEY, person TEXT NOT NULL, number INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(person, number))')
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
            self.db.execute('INSERT OR IGNORE INTO mail (id,sender,recipient,created,payload) VALUES (?,?,?,?,?)',
                            (draft['id'], draft['sender'], draft['recipient'], time.time(), json.dumps(draft)))
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

    def get(self, ident):
        with self.lock:
            row = self.db.execute('SELECT payload FROM mail WHERE id=?', (ident,)).fetchone()
        return json.loads(row[0]) if row else None

    def inbox(self, person, sender=None, unread=False):
        with self.lock:
            rows = self.db.execute('SELECT payload,seen FROM mail WHERE recipient=? ORDER BY created', (person,)).fetchall()
        return [dict(json.loads(p), seen=bool(seen)) for p, seen in rows
                if (not unread or not seen) and (sender is None or json.loads(p)['sender'] == sender)]

    def mark_seen(self, message):
        with self.lock, self.db:
            self.db.execute('UPDATE mail SET seen=1 WHERE id=?', (message['id'],))

    def close(self):
        self.db.close()
