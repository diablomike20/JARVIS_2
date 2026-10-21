"""Optional read-only IMAP headers and standards-based ICS calendar sources."""
from __future__ import annotations
import email
import email.policy
import imaplib
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def email_headers(config, after_uid: int | None = None, limit: int = 20):
    user, password = os.environ.get(config.user_env, ''), os.environ.get(config.password_env, '')
    if not user or not password:
        raise ValueError('Az IMAP-fiókhoz megadott környezeti változók hiányoznak.')
    client = imaplib.IMAP4_SSL(config.host, config.port, timeout=10)
    try:
        client.login(user, password)
        status, _ = client.select(config.folder, readonly=True)
        if status != 'OK':
            raise ValueError('Az IMAP-mappa nem érhető el.')
        status, info = client.status(config.folder, '(UIDVALIDITY UIDNEXT)')
        if status != 'OK':
            raise ValueError('Az IMAP UID-állapota nem olvasható.')
        raw = b' '.join(x for x in info if isinstance(x, bytes))
        validity = re.search(rb'UIDVALIDITY\s+(\d+)', raw).group(1).decode()
        next_uid = int(re.search(rb'UIDNEXT\s+(\d+)', raw).group(1))
        start = max(1, after_uid + 1) if after_uid is not None else max(1, next_uid - 100)
        if start >= next_uid:
            return {'uidvalidity': validity, 'last_uid': next_uid - 1, 'messages': []}
        status, data = client.uid('search', None, f'UID {start}:{next_uid-1}')
        if status != 'OK':
            raise ValueError('Az IMAP-keresés sikertelen.')
        ids = data[0].split()[-min(max(limit, 1), 50):] if data and data[0] else []
        out = []
        for ident in ids:
            status, rows = client.uid('fetch', ident, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])')
            if status != 'OK':
                continue
            raw = next((r[1] for r in rows if isinstance(r, tuple) and isinstance(r[1], bytes)), b'')[:64000]
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            out.append({'uid': int(ident), 'from': str(msg.get('from', '')), 'subject': str(msg.get('subject', '')),
                        'date': str(msg.get('date', '')), 'message_id': str(msg.get('message-id', ''))})
        return {'uidvalidity': validity, 'last_uid': next_uid - 1, 'messages': out}
    finally:
        try:
            client.logout()
        except Exception:
            pass


def calendar_events(paths, timezone: str, days: int = 7):
    try:
        from icalendar import Calendar
        import recurring_ical_events
    except ImportError as exc:
        raise ValueError('Az ICS naptárhoz telepítsd a requirements-ng.txt függőségeit.') from exc
    zone = ZoneInfo(timezone)
    start = datetime.now(zone)
    end = start + timedelta(days=min(max(days, 1), 90))
    events = []
    for path in paths:
        if not path.is_file() or path.stat().st_size > 5_000_000:
            raise ValueError('Hiányzó vagy 5 MB-nál nagyobb naptárfájl.')
        calendar = Calendar.from_ical(path.read_bytes())
        for item in recurring_ical_events.of(calendar).between(start, end)[:500]:
            dt = item.decoded('dtstart')
            events.append({'title': str(item.get('summary', '')), 'start': dt.isoformat(),
                           'end': item.decoded('dtend').isoformat() if item.get('dtend') else None,
                           'source': str(path), 'uid': str(item.get('uid', ''))})
    return sorted(events, key=lambda x: x['start'])[:500]
