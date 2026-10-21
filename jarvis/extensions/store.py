"""Versioned workbench state in the existing JARVIS SQLite database.

Legacy tables are never renamed or deleted. Session history is separate from
legacy rolling messages, so projects cannot accidentally recall each other.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS ng_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ng_projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,path TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ng_sessions(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES ng_projects(id),name TEXT NOT NULL,
 history TEXT NOT NULL DEFAULT '[]',summary TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'idle',updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ng_profiles(project_id TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,source TEXT NOT NULL,
 confidence REAL NOT NULL,updated REAL NOT NULL,expires REAL,PRIMARY KEY(project_id,key));
CREATE TABLE IF NOT EXISTS ng_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,payload TEXT NOT NULL,
 created REAL NOT NULL,read_at REAL);
CREATE TABLE IF NOT EXISTS ng_reminders(id TEXT PRIMARY KEY,text TEXT NOT NULL,due REAL NOT NULL,
 interval_s REAL NOT NULL DEFAULT 0,enabled INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ng_tasks(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,
 dependencies TEXT NOT NULL,owner TEXT NOT NULL DEFAULT '',result TEXT NOT NULL DEFAULT '',updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ng_team_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,team TEXT NOT NULL,sender TEXT NOT NULL,
 recipient TEXT NOT NULL,text TEXT NOT NULL,created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ng_events_kind ON ng_events(kind,seq);
"""


def uid() -> str:
    return uuid.uuid4().hex


class WorkbenchStore:
    def __init__(self, path: Path, root: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as c:
            c.executescript(SCHEMA)
            c.execute("INSERT OR IGNORE INTO ng_meta VALUES('schema_version','1')")
            c.execute("INSERT OR IGNORE INTO ng_projects VALUES('default','Alapértelmezett',?,?)", (str(root.resolve()), time.time()))
            c.execute("INSERT OR IGNORE INTO ng_sessions(id,project_id,name,updated) VALUES('default','default','Alapértelmezett',?)", (time.time(),))
            c.execute("INSERT OR IGNORE INTO ng_meta VALUES('active_session','default')")
            # Running state after an unclean stop is evidence, never permission
            # to replay tools whose external side effects may already have run.
            rows = c.execute("SELECT id FROM ng_sessions WHERE status='running'").fetchall()
            for row in rows:
                c.execute("UPDATE ng_sessions SET status='interrupted' WHERE id=?", (row['id'],))
                self._event(c, 'recovery', {'session_id': row['id'], 'text': 'Megszakadt munkamenet; az eszközműveleteket nem ismételtem meg.'})

    @contextmanager
    def connection(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            with c:
                yield c
        finally:
            c.close()

    def projects(self) -> list[dict]:
        with self.connection() as c:
            return [dict(r) for r in c.execute('SELECT * FROM ng_projects ORDER BY created')]

    def get_state(self, key: str, default=None):
        with self.connection() as c:
            row = c.execute('SELECT value FROM ng_meta WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_state(self, key: str, value):
        with self.connection() as c:
            c.execute('INSERT INTO ng_meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(value)))

    def create_project(self, name: str, path: str) -> dict:
        p = Path(path).expanduser().resolve(strict=True)
        if not p.is_dir():
            raise ValueError('A projekt útvonala könyvtár legyen.')
        name = name.strip()
        if not name or len(name) > 120:
            raise ValueError('A projektnév 1–120 karakter legyen.')
        item = dict(id=uid(), name=name, path=str(p), created=time.time())
        with self.connection() as c:
            c.execute('INSERT INTO ng_projects VALUES(:id,:name,:path,:created)', item)
        return item

    def sessions(self, project_id: str | None = None) -> list[dict]:
        with self.connection() as c:
            rows = c.execute('SELECT id,project_id,name,status,updated FROM ng_sessions WHERE (? IS NULL OR project_id=?) ORDER BY updated DESC', (project_id, project_id))
            return [dict(r) for r in rows]

    def create_session(self, name: str, project_id: str = 'default') -> dict:
        if not name.strip() or len(name) > 120:
            raise ValueError('A munkamenet neve 1–120 karakter legyen.')
        with self.connection() as c:
            if not c.execute('SELECT 1 FROM ng_projects WHERE id=?', (project_id,)).fetchone():
                raise ValueError('Ismeretlen projekt.')
            sid = uid()
            c.execute('INSERT INTO ng_sessions(id,project_id,name,updated) VALUES(?,?,?,?)', (sid, project_id, name.strip(), time.time()))
        return self.session(sid)

    def session(self, sid: str | None = None) -> dict:
        with self.connection() as c:
            sid = sid or c.execute("SELECT value FROM ng_meta WHERE key='active_session'").fetchone()[0]
            row = c.execute('SELECT s.*,p.path AS project_path,p.name AS project_name FROM ng_sessions s JOIN ng_projects p ON p.id=s.project_id WHERE s.id=?', (sid,)).fetchone()
            if row is None:
                raise ValueError('Ismeretlen munkamenet.')
            out = dict(row)
            out['history'] = json.loads(out['history'])
            return out

    def rename_session(self, sid: str, name: str) -> dict:
        name = name.strip()
        if not name or len(name) > 120:
            raise ValueError('A munkamenet neve 1–120 karakter legyen.')
        with self.connection() as c:
            changed = c.execute('UPDATE ng_sessions SET name=? WHERE id=?', (name, sid))
            if changed.rowcount != 1:
                raise ValueError('Ismeretlen munkamenet.')
        return self.session(sid)

    def activate(self, sid: str) -> dict:
        out = self.session(sid)
        if not Path(out['project_path']).is_dir():
            raise ValueError('A projekt könyvtára már nem érhető el.')
        with self.connection() as c:
            c.execute("UPDATE ng_meta SET value=? WHERE key='active_session'", (sid,))
        return out

    def save_session(self, sid: str, history: list[dict], summary: str, status: str = 'idle') -> None:
        with self.connection() as c:
            c.execute('UPDATE ng_sessions SET history=?,summary=?,status=?,updated=? WHERE id=?', (json.dumps(history, ensure_ascii=False), summary, status, time.time(), sid))

    def set_profile(self, key: str, value: Any, source: str, project_id: str = '', confidence: float = 1.0, expires: float | None = None) -> None:
        if not key.strip() or len(key) > 120 or not source.strip():
            raise ValueError('Kulcs és forrás szükséges.')
        if not 0 <= confidence <= 1:
            raise ValueError('A megbízhatóság 0 és 1 közötti érték.')
        if len(json.dumps(value)) > 8000:
            raise ValueError('Túl hosszú profilbejegyzés.')
        with self.connection() as c:
            c.execute('INSERT INTO ng_profiles VALUES(?,?,?,?,?,?,?) ON CONFLICT(project_id,key) DO UPDATE SET value=excluded.value,source=excluded.source,confidence=excluded.confidence,updated=excluded.updated,expires=excluded.expires',
                      (project_id, key.strip(), json.dumps(value, ensure_ascii=False), source, confidence, time.time(), expires))

    def profiles(self, project_id: str = '', include_expired: bool = False) -> list[dict]:
        with self.connection() as c:
            rows = c.execute("SELECT * FROM ng_profiles WHERE (project_id='' OR project_id=?) AND (? OR expires IS NULL OR expires>?) ORDER BY project_id,key", (project_id, include_expired, time.time()))
            return [{**dict(r), 'value': json.loads(r['value'])} for r in rows]

    def delete_profile(self, key: str, project_id: str = '') -> bool:
        with self.connection() as c:
            return c.execute('DELETE FROM ng_profiles WHERE project_id=? AND key=?', (project_id, key)).rowcount > 0

    @staticmethod
    def _event(c, kind, payload):
        c.execute('INSERT INTO ng_events(kind,payload,created) VALUES(?,?,?)', (kind, json.dumps(payload, ensure_ascii=False), time.time()))

    def publish(self, kind: str, payload: dict) -> None:
        with self.connection() as c:
            self._event(c, kind, payload)
            c.execute("DELETE FROM ng_events WHERE seq <= (SELECT COALESCE(MAX(seq),0)-2000 FROM ng_events) AND (read_at IS NOT NULL OR kind IN ('chat_finished','session_changed'))")

    def notifications(self, after: int = 0) -> list[dict]:
        with self.connection() as c:
            rows = c.execute("SELECT * FROM ng_events WHERE seq>? AND kind NOT IN ('chat_finished','session_changed') ORDER BY seq DESC LIMIT 100", (after,)).fetchall()
            return [{**dict(r), 'payload': json.loads(r['payload'])} for r in rows][::-1]

    def events(self, after: int = 0, limit: int = 100) -> list[dict]:
        with self.connection() as c:
            return [{**dict(r), 'payload': json.loads(r['payload'])} for r in c.execute('SELECT * FROM ng_events WHERE seq>? ORDER BY seq LIMIT ?', (after, min(max(limit, 1), 200)))]

    def acknowledge(self, through: int) -> None:
        with self.connection() as c:
            c.execute('UPDATE ng_events SET read_at=? WHERE seq<=? AND read_at IS NULL', (time.time(), through))

    def remind(self, text: str, due: float, interval_s: float = 0) -> str:
        import math
        if not text.strip() or len(text) > 2000 or not math.isfinite(due) or due <= 0:
            raise ValueError('Érvényes szöveg és időpont szükséges.')
        if not math.isfinite(interval_s) or interval_s < 0 or (0 < interval_s < 60):
            raise ValueError('Az ismétlés legalább 60 másodperc legyen.')
        rid = uid()
        with self.connection() as c:
            c.execute('INSERT INTO ng_reminders VALUES(?,?,?,?,1,?)', (rid, text.strip(), due, interval_s, time.time()))
        return rid

    def reminders(self) -> list[dict]:
        with self.connection() as c:
            return [dict(r) for r in c.execute('SELECT * FROM ng_reminders ORDER BY due')]

    def cancel_reminder(self, rid: str) -> bool:
        with self.connection() as c:
            return c.execute('UPDATE ng_reminders SET enabled=0 WHERE id=?', (rid,)).rowcount > 0

    def tick_reminders(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            rows = c.execute('SELECT * FROM ng_reminders WHERE enabled=1 AND due<=?', (now,)).fetchall()
            for row in rows:
                self._event(c, 'reminder', {'id': row['id'], 'text': row['text'], 'due': row['due']})
                interval = row['interval_s']
                if interval:
                    # Missed repeats coalesce; never flood on next startup.
                    due = row['due'] + (int((now - row['due']) // interval) + 1) * interval
                    c.execute('UPDATE ng_reminders SET due=? WHERE id=?', (due, row['id']))
                else:
                    c.execute('UPDATE ng_reminders SET enabled=0 WHERE id=?', (row['id'],))
            return len(rows)

    def tasks(self, project_id: str) -> list[dict]:
        with self.connection() as c:
            return [{**dict(r), 'dependencies': json.loads(r['dependencies'])} for r in c.execute('SELECT * FROM ng_tasks WHERE project_id=? ORDER BY updated', (project_id,))]

    def task_add(self, title: str, project_id: str, dependencies: list[str] | None = None, owner: str = '') -> str:
        if not title.strip():
            raise ValueError('A feladat neve üres.')
        dependencies = list(dict.fromkeys(dependencies or []))
        with self.connection() as c:
            for dep in dependencies:
                if not c.execute('SELECT 1 FROM ng_tasks WHERE id=? AND project_id=?', (dep, project_id)).fetchone():
                    raise ValueError('A függő feladat nem ebben a projektben található.')
            tid = uid()
            c.execute('INSERT INTO ng_tasks VALUES(?,?,?,?,?,?,?,?)', (tid, project_id, title, 'pending', json.dumps(dependencies), owner, '', time.time()))
            return tid

    def task_update(self, tid: str, project_id: str, status: str, result: str = '') -> None:
        if status not in {'pending', 'running', 'done', 'failed', 'cancelled'}:
            raise ValueError('Ismeretlen feladatállapot.')
        with self.connection() as c:
            row = c.execute('SELECT * FROM ng_tasks WHERE id=? AND project_id=?', (tid, project_id)).fetchone()
            if not row:
                raise ValueError('Ismeretlen feladat.')
            if status in {'running', 'done'}:
                for dep in json.loads(row['dependencies']):
                    r = c.execute('SELECT status FROM ng_tasks WHERE id=?', (dep,)).fetchone()
                    if not r or r[0] != 'done':
                        raise ValueError('Előbb fejezd be a függő feladatokat.')
            c.execute('UPDATE ng_tasks SET status=?,result=?,updated=? WHERE id=?', (status, result, time.time(), tid))

    def message(self, team: str, sender: str, recipient: str, text: str) -> None:
        with self.connection() as c:
            c.execute('INSERT INTO ng_team_messages(team,sender,recipient,text,created) VALUES(?,?,?,?,?)', (team, sender, recipient, text, time.time()))

    def messages(self, team: str) -> list[dict]:
        with self.connection() as c:
            return [dict(r) for r in c.execute('SELECT * FROM ng_team_messages WHERE team=? ORDER BY id DESC LIMIT 100', (team,))][::-1]
