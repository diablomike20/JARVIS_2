"""Revocable LAN pairing; only token hashes are persisted."""
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

LOCAL = {'127.0.0.1', '::1', 'localhost', 'testclient'}
LOCAL_HOSTS = LOCAL | {'testserver'}


class Pairing:
    def __init__(self, path: Path):
        self.path = path

    def create(self, ttl_seconds=86400):
        token = secrets.token_urlsafe(32)
        record = {'hash': hashlib.sha256(token.encode()).hexdigest(), 'expires': time.time() + ttl_seconds}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.pair-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(record, f)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return {'token': token, 'expires': record['expires']}

    def valid(self, token: str) -> bool:
        try:
            if not token or len(token) > 500:
                return False
            record = json.loads(self.path.read_text())
            return record['expires'] > time.time() and hmac.compare_digest(record['hash'], hashlib.sha256(token.encode()).hexdigest())
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def revoke(self):
        self.path.unlink(missing_ok=True)


def authorized(scope, pairing):
    client = scope.client.host if scope.client else ''
    origin = scope.headers.get('origin')
    host = scope.url.hostname
    if client in LOCAL:
        return host in LOCAL_HOSTS and (not origin or urlsplit(origin).hostname in LOCAL_HOSTS)
    if origin and urlsplit(origin).hostname != host:
        return False
    if pairing is None:
        return False
    header = scope.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else scope.cookies.get('jarvis_pair', '')
    return pairing.valid(token)
