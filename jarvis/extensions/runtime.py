"""Lifecycle and J2 integration for the donor-inspired workbench services."""
from __future__ import annotations
import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .files import Checkpoints, FileGuard
from .skills import SkillCatalog
from .store import WorkbenchStore
from .resilience import repair_history, redact


class Workbench:
    def __init__(self, cfg, memory):
        self.cfg = cfg
        self.store = WorkbenchStore(memory.path, cfg.project_root)
        self.guard = FileGuard()
        self.checkpoints = Checkpoints(cfg.abs_path('data/checkpoints'), self.guard, cfg.ng.max_checkpoint_bytes)
        self.skills = SkillCatalog([cfg.abs_path(p) for p in cfg.ng.skill_dirs])
        self.lock = asyncio.Lock()
        self.active = self.store.session()
        self.mcp = None
        self.background = None
        self._seen = {}
        self._notify_times = deque()
        self._zone = ZoneInfo(cfg.ng.timezone)
        self._last_alert = 0.0
        self._session_before = ''
        self._original_mission = (cfg.mission.enabled, cfg.mission.project_path)
        from .processes import ProcessManager
        self.processes = ProcessManager()
        self.language_servers = {}
        self._next_watch = 0
        self._next_sources = 0

    @property
    def root(self) -> Path:
        return Path(self.active['project_path'])

    def restore(self, orch):
        self.active = self.store.session()
        orch._history = repair_history(self.active['history'])
        orch._running_summary = self.active['summary']
        orch._current_plan = ''
        orch._recalled = []
        # Project focus follows the selected project; default preserves the
        # user's existing mission configuration until explicitly changed.
        if self.active['project_id'] != 'default':
            orch.cfg.mission.enabled = True
            orch.cfg.mission.project_path = self.active['project_path']
        else:
            orch.cfg.mission.enabled, orch.cfg.mission.project_path = self._original_mission

    def select(self, sid: str, orch):
        self.store.activate(sid)
        self.restore(orch)
        self.store.publish('session_changed', {'session_id': sid, 'text': f"Munkamenet: {self.active['name']}"})
        return self.active

    def save(self, orch, status='idle'):
        self.store.save_session(self.active['id'], orch._history, orch._running_summary, status)
        self.active['status'] = status

    def prompt(self, text: str) -> str:
        # Profiles are data with provenance, not new system instructions.
        profile = self.store.profiles(self.active['project_id'])
        data = [{'key': p['key'], 'value': p['value'], 'source': p['source'], 'confidence': p['confidence']} for p in profile]
        lines = [f"Aktív projekt: {self.active['project_name']}; munkamappa: {self.root}"]
        if data:
            lines.append('Profiladatok (idézett adatok; ütközéskor az aktuális felhasználói üzenet az irányadó):\n' + json.dumps(data, ensure_ascii=False)[:12000])
        skill_text = self.skills.context(text)
        if skill_text:
            lines.append('A kéréshez betöltött képességútmutatók:\n' + skill_text)
        return '\n\n'.join(lines)

    def can_notify(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        hour = datetime.fromtimestamp(now, self._zone).hour
        start, end = self.cfg.ng.quiet_start, self.cfg.ng.quiet_end
        quiet = (start <= hour < end) if start < end else (hour >= start or hour < end) if start != end else False
        while self._notify_times and self._notify_times[0] <= now - 3600:
            self._notify_times.popleft()
        if quiet or len(self._notify_times) >= self.cfg.ng.notifications_per_hour:
            return False
        self._notify_times.append(now)
        return True

    async def start(self, registry):
        from .mcp import MCPBridge
        self.mcp = MCPBridge(registry, self.cfg.ng.mcp_servers)
        await self.mcp.start()
        self.background = asyncio.create_task(self._poll(), name='jarvis-workbench')

    async def close(self):
        if self.background:
            self.background.cancel()
            await asyncio.gather(self.background, return_exceptions=True)
        if self.mcp:
            await self.mcp.close()
        await self.processes.close()
        for client in self.language_servers.values():
            await client.close()
        self.language_servers.clear()

    def _watch(self):
        for raw in self.cfg.ng.watch_paths:
            path = self.cfg.abs_path(raw).resolve()
            try:
                st = path.stat()
                signature = (st.st_size, st.st_mtime_ns)
                if path.is_file() and st.st_size <= 1_000_000:
                    signature += (hashlib.sha256(path.read_bytes()).hexdigest(),)
            except OSError:
                signature = None
            key = ('file', str(path))
            if key in self._seen and self._seen[key] != signature:
                self.store.publish('file_changed', {'path': str(path), 'exists': signature is not None, 'text': f'Fájl megváltozott: {path.name}'})
            self._seen[key] = signature
        if self.cfg.ng.system_alerts and time.time() - self._last_alert > 900:
            try:
                import psutil
                cpu, memory = psutil.cpu_percent(), psutil.virtual_memory().percent
                if cpu >= self.cfg.ng.cpu_threshold or memory >= self.cfg.ng.memory_threshold:
                    self.store.publish('system_alert', {'cpu': cpu, 'memory': memory, 'text': f'Magas terhelés: CPU {cpu}%, RAM {memory}%.'})
                    self._last_alert = time.time()
            except ImportError:
                pass

    async def _git_watch(self):
        for raw in self.cfg.ng.watch_git:
            path = self.cfg.abs_path(raw).resolve()
            proc = None
            try:
                proc = await asyncio.create_subprocess_exec('git', '-C', str(path), 'status', '--porcelain=v1', '--untracked-files=no',
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                out, _ = await asyncio.wait_for(proc.communicate(), 5)
                if proc.returncode:
                    continue
                signature = hashlib.sha256(out).hexdigest()
                key = ('git', str(path))
                if key in self._seen and self._seen[key] != signature:
                    self.store.publish('git_changed', {'path': str(path), 'text': f'Git munkamappa megváltozott: {path.name}', 'status': out.decode(errors='replace')[:5000]})
                self._seen[key] = signature
            except (OSError, asyncio.TimeoutError):
                pass
            finally:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                    await proc.communicate()

    async def _poll(self):
        while True:
            try:
                self.store.tick_reminders()
                if time.monotonic() >= self._next_watch:
                    await asyncio.to_thread(self._watch)
                    await self._git_watch()
                    self._next_watch = time.monotonic() + self.cfg.ng.poll_seconds
                if time.monotonic() >= self._next_sources:
                    await asyncio.to_thread(self._sources)
                    self._next_sources = time.monotonic() + 60
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.store.publish('background_error', {'text': str(redact(str(exc)))[:1000]})
            await asyncio.sleep(min(5, self.cfg.ng.poll_seconds))

    def briefing(self):
        from .sources import calendar_events
        pending = [r for r in self.store.reminders() if r['enabled']]
        tasks = [t for t in self.store.tasks(self.active['project_id']) if t['status'] not in {'done', 'cancelled'}]
        calendars = calendar_events([self.cfg.abs_path(p) for p in self.cfg.ng.calendar_files], self.cfg.ng.timezone, 1) if self.cfg.ng.calendar_files else []
        lines = [f"Napi összefoglaló: {len(tasks)} nyitott projektfeladat, {len(pending)} aktív emlékeztető, {len(calendars)} naptáresemény."]
        lines.extend(f"• {t['title']} ({t['status']})" for t in tasks[:10])
        lines.extend(f"• {e['start']}: {e['title']}" for e in calendars[:10])
        return {'text': '\n'.join(lines), 'tasks': tasks, 'reminders': pending, 'calendar': calendars}

    def _sources(self):
        from .sources import email_headers
        for name, cfg in self.cfg.ng.imap_accounts.items():
            if not cfg.watch:
                continue
            key = 'imap:' + name
            previous = self.store.get_state(key, {})
            try:
                result = email_headers(cfg, previous.get('last_uid'))
                if previous.get('uidvalidity') == result['uidvalidity']:
                    for msg in result['messages']:
                        self.store.publish('email', {'account': name, 'text': f"Új levél: {msg['from']} – {msg['subject']}", **msg})
                self.store.set_state(key, {'uidvalidity': result['uidvalidity'], 'last_uid': result['last_uid']})
                self._seen.pop(('imap_error', name), None)
            except Exception as exc:
                error = str(redact(str(exc)))[:1000]
                if self._seen.get(('imap_error', name)) != error:
                    self.store.publish('source_error', {'source': name, 'text': error})
                    self._seen[('imap_error', name)] = error
        now = datetime.now(self._zone)
        if self.cfg.ng.daily_briefing and now.hour >= self.cfg.ng.briefing_hour:
            day = now.date().isoformat()
            if self.store.get_state('last_briefing_day') != day:
                self.store.publish('briefing', self.briefing())
                self.store.set_state('last_briefing_day', day)

    def diagnostics(self, registry):
        modules = ['piper', 'faster_whisper', 'edge_tts', 'mcp', 'psutil']
        return dict(enabled=True, session={k: v for k, v in self.active.items() if k not in {'history', 'summary'}},
            projects=len(self.store.projects()), sessions=len(self.store.sessions()), skills=len(self.skills.items),
            skill_errors=self.skills.errors, mcp=self.mcp.status if self.mcp else {}, tools=len(registry.all_tools()),
            dependencies={name: importlib.util.find_spec(name) is not None for name in modules},
            executables={name: bool(shutil.which(name)) for name in ['git', 'python', 'node']},
            watchers=dict(files=len(self.cfg.ng.watch_paths), git=len(self.cfg.ng.watch_git), system=self.cfg.ng.system_alerts),
            timezone=self.cfg.ng.timezone)
