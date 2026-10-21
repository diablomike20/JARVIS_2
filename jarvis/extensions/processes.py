"""Owned subprocesses with bounded output, deadlines and process-tree cleanup.

This is process supervision, not OS sandboxing. Commands come from explicit
configuration; no shell interpolation or automatic package installation.
"""
from __future__ import annotations
import asyncio
import os
import signal
import subprocess
from collections import deque


async def terminate(proc):
    if os.name == 'nt':
        if proc.returncode is not None:
            return
        # Windows process groups do not terminate children by themselves.
        try:
            killer = await asyncio.create_subprocess_exec('taskkill', '/PID', str(proc.pid), '/T', '/F', stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await asyncio.wait_for(killer.wait(), 5)
        except (OSError, asyncio.TimeoutError):
            proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    await proc.wait()


def group_options():
    return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}


class ProcessManager:
    def __init__(self):
        self.entries = {}
        self._lock = asyncio.Lock()

    async def start(self, name: str, command: str, args: list[str], cwd: str, env: dict | None = None):
        async with self._lock:
            previous = self.entries.get(name)
            if previous and previous['process'].returncode is None:
                raise ValueError('Ez a folyamat már fut.')
            if previous:
                await asyncio.gather(*previous['readers'], return_exceptions=True)
            proc = await asyncio.create_subprocess_exec(command, *args, cwd=cwd, env=env,
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **group_options())
            entry = {'process': proc, 'output': deque(maxlen=100), 'cwd': cwd, 'readers': []}
            self.entries[name] = entry
            async def drain(stream, channel):
                while True:
                    block = await stream.read(2048)
                    if not block:
                        break
                    entry['output'].append((channel, block.decode(errors='replace')))
            entry['readers'] = [asyncio.create_task(drain(proc.stdout, 'stdout')), asyncio.create_task(drain(proc.stderr, 'stderr'))]
            return self.status(name)

    def status(self, name: str | None = None):
        from .resilience import redact
        def item(key, value):
            return dict(name=key, pid=value['process'].pid, returncode=value['process'].returncode,
                        running=value['process'].returncode is None, cwd=value['cwd'], output=redact(list(value['output'])))
        if name is not None:
            if name not in self.entries:
                raise ValueError('Ismeretlen folyamat.')
            return item(name, self.entries[name])
        return [item(k, v) for k, v in list(self.entries.items())]

    async def stop(self, name: str):
        if name not in self.entries:
            raise ValueError('Ismeretlen folyamat.')
        entry = self.entries[name]
        await terminate(entry['process'])
        try:
            await asyncio.wait_for(asyncio.gather(*entry['readers'], return_exceptions=True), 2)
        except asyncio.TimeoutError:
            for task in entry['readers']:
                task.cancel()
            await asyncio.gather(*entry['readers'], return_exceptions=True)
        return self.status(name)

    async def run(self, command: str, args: list[str], cwd: str, timeout: float = 60, env: dict | None = None):
        import uuid
        name = 'command:' + uuid.uuid4().hex
        await self.start(name, command, args, cwd, env)
        entry = self.entries[name]
        try:
            try:
                await asyncio.wait_for(asyncio.gather(entry['process'].wait(), *entry['readers']), timeout)
                return self.status(name)
            except asyncio.TimeoutError:
                await self.stop(name)
                return {**self.status(name), 'timed_out': True}
        finally:
            await self.stop(name)
            self.entries.pop(name, None)

    async def close(self):
        for name in list(self.entries):
            await self.stop(name)
        self.entries.clear()
