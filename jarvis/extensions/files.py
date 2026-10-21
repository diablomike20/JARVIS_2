"""Content-hash edit guards and explicitly scoped, conflict-checked snapshots.

This protects cooperating JARVIS writers, not a filesystem sandbox or a lock
against arbitrary external programs. Checkpoints exclude secrets and symlinks.
"""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
import threading
import uuid
import contextvars
from pathlib import Path

file_owner = contextvars.ContextVar('jarvis_file_owner', default='default')


def digest(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f'Nem fájl: {path}')
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class FileGuard:
    def __init__(self):
        self._observed: dict[Path, str | None] = {}
        self._locks: dict[Path, threading.RLock] = {}
        self._lock = threading.RLock()

    def lock(self, path: Path):
        with self._lock:
            return self._locks.setdefault(path.resolve(), threading.RLock())

    def observe(self, path: Path) -> str | None:
        path = path.resolve()
        with self.lock(path):
            value = digest(path)
            self._observed[(file_owner.get(), path)] = value
            return value

    def write(self, path: Path, content: str, expected: str | None = None, require_read: bool = True) -> int:
        path = path.expanduser().resolve()
        with self.lock(path):
            before = digest(path)
            observed_key = (file_owner.get(), path)
            if expected is not None and before != expected:
                raise ValueError('A fájl tartalma megváltozott; olvasd be újra.')
            if expected is None and before is not None and require_read and observed_key not in self._observed:
                raise ValueError('Módosítás előtt olvasd be a fájlt a read_file eszközzel.')
            if expected is None and observed_key in self._observed and before != self._observed[observed_key]:
                raise ValueError('Másik folyamat módosította a fájlt; olvasd be újra.')
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix='.jarvis-', dir=path.parent)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
                    f.write(content)
                if path.exists():
                    os.chmod(name, path.stat().st_mode)
                # Check again immediately before replacement. Non-cooperating
                # external writers can still race the final OS operation.
                if digest(path) != before:
                    raise ValueError('Ütközés mentés közben; a célfájlt nem írtam felül.')
                os.replace(name, path)
                # A successful write consumes the read observation. Another
                # concurrent call from this same owner must not inherit it
                # and overwrite content assembled before this write.
                self._observed.pop(observed_key, None)
                return len(content)
            finally:
                if os.path.exists(name):
                    os.unlink(name)


class Checkpoints:
    def __init__(self, directory: Path, guard: FileGuard, max_bytes: int = 20_000_000):
        self.directory = directory.resolve()
        self.guard = guard
        self.max_bytes = max_bytes

    @staticmethod
    def _safe(root: Path, rel: str) -> Path:
        raw = Path(rel)
        if raw.is_absolute() or '..' in raw.parts or not raw.parts:
            raise ValueError('Csak projekten belüli relatív fájlútvonal adható meg.')
        if any(part.startswith('.env') or part in {'.git', 'node_modules', 'venv', '.venv', '__pycache__'} for part in raw.parts):
            raise ValueError('Kizárt fájl vagy könyvtár.')
        path = root / raw
        for ancestor in [path, *path.parents]:
            if ancestor == root.parent:
                break
            if ancestor.is_symlink():
                raise ValueError('Szimbolikus hivatkozás nem menthető.')
        if not path.resolve().is_relative_to(root):
            raise ValueError('Projekten kívüli útvonal.')
        return path

    def capture(self, root: Path, paths: list[str], label: str = '') -> dict:
        root = root.resolve(strict=True)
        if not root.is_dir() or not paths or len(paths) > 100:
            raise ValueError('1–100 fájl és létező projektmappa szükséges.')
        ident = uuid.uuid4().hex
        target = self.directory / ident
        records = []
        total = 0
        blobs: dict[str, bytes] = {}
        for rel in dict.fromkeys(str(Path(p)) for p in paths):
            path = self._safe(root, rel)
            if path.exists() and not path.is_file():
                raise ValueError('Egyenként add meg a fájlokat, ne könyvtárat.')
            if path.exists() and path.stat().st_size + total > self.max_bytes:
                raise ValueError('A mentés meghaladná a méretkorlátot.')
            data = path.read_bytes() if path.exists() else None
            total += len(data or b'')
            if total > self.max_bytes:
                raise ValueError('Túl nagy mentés.')
            key = str(len(records))
            if data is not None:
                blobs[key] = data
            records.append(dict(path=rel, blob=key, sha256=hashlib.sha256(data).hexdigest() if data is not None else None, mode=path.stat().st_mode if path.exists() else None))
        target.mkdir(parents=True)
        for key, data in blobs.items():
            (target / key).write_bytes(data)
        item = dict(id=ident, root=str(root), label=label[:200], files=records, bytes=total)
        (target / 'manifest.json').write_text(json.dumps(item, ensure_ascii=False), encoding='utf-8')
        return item

    def _load(self, ident: str) -> dict:
        if len(ident) != 32 or any(x not in '0123456789abcdef' for x in ident):
            raise ValueError('Érvénytelen mentésazonosító.')
        return json.loads((self.directory / ident / 'manifest.json').read_text(encoding='utf-8'))

    def list(self, root: Path) -> list[dict]:
        if not self.directory.exists():
            return []
        out = []
        for path in sorted(self.directory.glob('*/manifest.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
            item = json.loads(path.read_text(encoding='utf-8'))
            if item['root'] == str(root.resolve()):
                out.append(item)
        return out

    def preview(self, ident: str, root: Path) -> dict:
        item = self._load(ident)
        if item['root'] != str(root.resolve()):
            raise ValueError('Másik projekt mentése.')
        changes = []
        for entry in item['files']:
            path = self._safe(root.resolve(), entry['path'])
            current = digest(path)
            if current != entry['sha256']:
                changes.append(dict(path=entry['path'], current_sha256=current, restore_sha256=entry['sha256']))
        token = hashlib.sha256(json.dumps(changes, sort_keys=True).encode()).hexdigest()
        return dict(id=ident, changes=changes, token=token, scope='Csak a felsorolt fájlok; külső műveletek nem vonhatók vissza.')

    def restore(self, ident: str, root: Path, token: str) -> dict:
        preview = self.preview(ident, root)
        if token != preview['token']:
            raise ValueError('A fájlok megváltoztak az előnézet óta; kérj új előnézetet.')
        item = self._load(ident)
        entries = {x['path']: x for x in item['files']}
        # Validate every blob before changing the first target file.
        for change in preview['changes']:
            entry = entries[change['path']]
            if entry['sha256'] is not None:
                data = (self.directory / ident / entry['blob']).read_bytes()
                if hashlib.sha256(data).hexdigest() != entry['sha256']:
                    raise ValueError('Sérült mentés; nem írtam át célfájlt.')
        # Save current contents first so restore itself can be undone.
        undo = self.capture(root, [x['path'] for x in preview['changes']], 'Visszaállítás előtti mentés') if preview['changes'] else None
        for change in preview['changes']:
            path = self._safe(root.resolve(), change['path'])
            entry = entries[change['path']]
            with self.guard.lock(path):
                if digest(path) != change['current_sha256']:
                    raise ValueError('Ütközés visszaállítás közben; az előző módosítások az undo mentésben vannak.')
                if entry['sha256'] is None:
                    path.unlink(missing_ok=True)
                else:
                    data = (self.directory / ident / entry['blob']).read_bytes()
                    if hashlib.sha256(data).hexdigest() != entry['sha256']:
                        raise ValueError('Sérült mentés.')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    fd, tmp = tempfile.mkstemp(prefix='.jarvis-restore-', dir=path.parent)
                    try:
                        with os.fdopen(fd, 'wb') as f:
                            f.write(data)
                        if entry.get('mode') is not None:
                            os.chmod(tmp, entry['mode'])
                        os.replace(tmp, path)
                    finally:
                        if os.path.exists(tmp):
                            os.unlink(tmp)
                self.guard.observe(path)
        return dict(restored=len(preview['changes']), undo_id=undo['id'] if undo else None)
