"""History repair, bounded repeat detection and audit redaction."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from collections import Counter

SECRET_KEYS = re.compile(r'(?i)(api[_-]?key|password|passwd|secret|access[_-]?token|refresh[_-]?token|authorization|cookie)')


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if SECRET_KEYS.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(x) for x in value]
    if isinstance(value, str):
        value = re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/-]+', r'\1[REDACTED]', value)
        value = re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[REDACTED]', value)
        value = re.sub(r'(?i)((?:api[_-]?key|password|secret|token)\s*[=:]\s*)[^\s,;"\']+', r'\1[REDACTED]', value)
        value = re.sub(r'(?i)(https?://)[^/@\s]+:[^/@\s]+@', r'\1[REDACTED]@', value)
        return value
    return value


def repair_history(history: list[dict]) -> list[dict]:
    """Repair native tool pairs without replaying an interrupted operation.

    Each assistant tool-call message must be immediately followed by exactly
    one result per call id. Orphan results are removed. Missing results state
    explicitly that the external outcome is unknown.
    """
    out = []
    i = 0
    while i < len(history):
        msg = copy.deepcopy(history[i])
        i += 1
        if msg.get('role') == 'tool':
            continue
        out.append(msg)
        calls = msg.get('tool_calls') if msg.get('role') == 'assistant' else None
        if not calls:
            continue
        results = {}
        while i < len(history) and history[i].get('role') == 'tool':
            result = history[i]
            results[result.get('tool_call_id')] = result
            i += 1
        for call in calls:
            cid = call.get('id')
            if not cid:
                continue
            out.append(copy.deepcopy(results.get(cid) or dict(role='tool', tool_call_id=cid,
                content='A végrehajtás megszakadt. Az eredmény és a külső mellékhatás bizonytalan; ne ismételd meg ellenőrzés nélkül.')))
    return out


class RepeatGuard:
    def __init__(self, limit: int = 3):
        self.counts = Counter()
        self.limit = limit
        self.results = {}

    @staticmethod
    def signature(name: str, args: dict) -> str:
        return hashlib.sha256((name + json.dumps(args, sort_keys=True, default=str)).encode()).hexdigest()

    def check(self, name: str, args: dict) -> None:
        signature = self.signature(name, args)
        self.counts[signature] += 1
        if self.counts[signature] > self.limit:
            raise PermissionError('Ugyanaz az eszközhívás ismétlődik előrelépés nélkül; változtass a megközelítésen.')

    def outcome(self, name: str, args: dict, result):
        signature = self.signature(name, args)
        value = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
        if self.results.get(signature) != value:
            self.counts[signature] = 0
        self.results[signature] = value


def public_history(history: list[dict]) -> list[dict]:
    out = []
    for item in history:
        role, text = item.get('role'), item.get('content')
        if role not in {'user', 'assistant'} or not isinstance(text, str) or item.get('tool_calls'):
            continue
        if text.startswith(('<tool_result', '(internal protocol')):
            continue
        if role == 'assistant':
            text = re.sub(r'<(?:thinking|think)>.*?(?:</(?:thinking|think)>|$)', '', text, flags=re.S | re.I)
            text = re.sub(r'<tool_call>.*?(?:</tool_call>|$)', '', text, flags=re.S | re.I)
        if text.strip():
            out.append({'role': role, 'content': text.strip()})
    return out


def error_summary(exc: Exception) -> dict:
    import httpx
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in {401, 403}:
            return {'code': 'authentication', 'text': 'A modellszolgáltató elutasította a hozzáférést. Ellenőrizd a beállított fiókot és jogosultságot.', 'retryable': False}
        if code == 429:
            return {'code': 'rate_limit', 'text': 'A modellszolgáltató használati vagy sebességkorlátot jelzett. A feladat állapota megmaradt.', 'retryable': True}
        if code >= 500:
            return {'code': 'provider_unavailable', 'text': 'A modellszolgáltató hibát jelzett. A feladat állapota megmaradt.', 'retryable': True}
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return {'code': 'timeout', 'text': 'A válasz nem érkezett meg időben. Mellékhatásos műveletet nem ismételtem meg automatikusan.', 'retryable': True}
    if isinstance(exc, httpx.ConnectError):
        return {'code': 'connection', 'text': 'A beállított modellszerver nem érhető el. Ellenőrizd, hogy fut-e és helyes-e a címe.', 'retryable': True}
    return {'code': 'runtime', 'text': str(redact(str(exc)))[:2000], 'retryable': False}
