"""Optional stdio MCP bridge. SDK contexts are owned by one actor task.

No remote server is started unless explicitly present in configuration.
Failures never disable the J2 chat. Calls are not automatically retried.
"""
from __future__ import annotations
import asyncio
import hashlib
import os
import re
from datetime import timedelta
from ..plugins.base import Tool
from ..core.permissions import Permission
from .resilience import redact


def tool_name(server: str, name: str) -> str:
    raw = f'mcp_{server}_{name}'
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', raw)
    return safe[:51] + '_' + hashlib.sha256(raw.encode()).hexdigest()[:12]


class MCPBridge:
    def __init__(self, registry, configs):
        self.registry = registry
        self.configs = configs
        self.tasks = []
        self.queues = {}
        self.status = {}
        self.owned_tools = []

    async def start(self):
        ready = []
        for name, cfg in self.configs.items():
            if not cfg.enabled:
                continue
            event = asyncio.Event()
            ready.append((event, cfg.timeout_seconds))
            self.queues[name] = asyncio.Queue(maxsize=32)
            self.tasks.append(asyncio.create_task(self._actor(name, cfg, event), name=f'mcp:{name}'))
        if ready:
            await asyncio.gather(*(self._ready(e, t) for e, t in ready))

    @staticmethod
    async def _ready(event, timeout):
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout + 2)
        except asyncio.TimeoutError:
            pass

    async def _actor(self, name, cfg, ready):
        self.status[name] = dict(state='connecting')
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            env = {k: os.environ[k] for k in cfg.env_vars if k in os.environ}
            params = StdioServerParameters(command=cfg.command, args=cfg.args, env=env, cwd=cfg.cwd or None)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=cfg.timeout_seconds)) as session:
                    await asyncio.wait_for(session.initialize(), cfg.timeout_seconds)
                    cursor = None
                    count = 0
                    while True:
                        result = await asyncio.wait_for(session.list_tools(cursor=cursor), cfg.timeout_seconds)
                        for remote in result.tools:
                            remote_name = remote.name
                            local = tool_name(name, remote_name)
                            if self.registry.get(local):
                                raise ValueError('MCP eszköznévütközés.')
                            async def invoke(_name=remote_name, _server=name, **args):
                                return await self.call(_server, _name, args)
                            self.registry.add(Tool(name=local, description=f'[MCP {name}] {remote.description or remote_name}',
                                parameters=remote.inputSchema, handler=invoke, permission=Permission.CAUTION, plugin=f'mcp:{name}'))
                            self.owned_tools.append(local)
                            count += 1
                            if count > 200:
                                raise ValueError('Túl sok MCP eszköz.')
                        cursor = result.nextCursor
                        if not cursor:
                            break
                    self.status[name] = dict(state='ready', tools=count)
                    ready.set()
                    while True:
                        remote, args, fut = await self.queues[name].get()
                        if fut.cancelled():
                            continue
                        try:
                            result = await asyncio.wait_for(session.call_tool(remote, args), cfg.timeout_seconds)
                            if result.isError:
                                raise RuntimeError(str(redact(result.model_dump()))[:3000])
                            if not fut.done():
                                fut.set_result(result.model_dump(mode='json'))
                        except Exception as exc:
                            if not fut.done():
                                fut.set_exception(RuntimeError(str(redact(str(exc)))[:2000]))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.status[name] = dict(state='error', error=str(redact(str(exc)))[:2000])
        finally:
            ready.set()
            # Queue futures must not remain hung when transport disappears.
            queue = self.queues[name]
            while not queue.empty():
                _, _, fut = queue.get_nowait()
                if not fut.done():
                    fut.set_exception(RuntimeError('Az MCP kapcsolat lezárult.'))

    async def call(self, server: str, name: str, args: dict):
        if self.status.get(server, {}).get('state') != 'ready':
            raise RuntimeError('Az MCP szerver nem érhető el.')
        future = asyncio.get_running_loop().create_future()
        self.queues[server].put_nowait((name, args, future))
        # No retry: timed-out remote side effects may already have happened.
        return await asyncio.wait_for(future, self.configs[server].timeout_seconds + 2)

    async def close(self):
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        for name in self.owned_tools:
            self.registry.remove(name)
        for name in self.status:
            self.status[name] = dict(state='closed')
        self.tasks.clear()
        self.owned_tools.clear()
