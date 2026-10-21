"""Optional LSP stdio client for configured local language servers.

The J2 tool exposes only document symbols, hover, definition and references.
Server initiated requests are answered explicitly; edits/commands from an LSP
server are not applied to the user's files.
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from .processes import group_options, terminate


class LSPClient:
    def __init__(self, command: str, args: list[str], root: Path):
        self.command, self.args, self.root = command, args, root.resolve()
        self.proc = None
        self.reader = self.stderr = None
        self.pending = {}
        self.seq = 0
        self.lock = asyncio.Lock()
        self.write_lock = asyncio.Lock()
        self.capabilities = {}
        self.error = ''

    async def _send(self, message):
        data = json.dumps(message, ensure_ascii=False).encode()
        async with self.write_lock:
            self.proc.stdin.write(f'Content-Length: {len(data)}\r\n\r\n'.encode() + data)
            await self.proc.stdin.drain()

    async def _notify(self, method, params):
        await self._send(dict(jsonrpc='2.0', method=method, params=params))

    async def _request(self, method, params, timeout=15):
        self.seq += 1
        ident = self.seq
        fut = asyncio.get_running_loop().create_future()
        self.pending[ident] = fut
        try:
            await self._send(dict(jsonrpc='2.0', id=ident, method=method, params=params))
            return await asyncio.wait_for(fut, timeout)
        finally:
            self.pending.pop(ident, None)

    async def _read(self):
        try:
            while True:
                header = await self.proc.stdout.readuntil(b'\r\n\r\n')
                values = dict(line.split(':', 1) for line in header.decode('ascii').strip().split('\r\n'))
                size = int(next(v for k, v in values.items() if k.lower() == 'content-length'))
                if not 0 <= size <= 4_000_000:
                    raise ValueError('Túl nagy LSP válasz.')
                message = json.loads(await self.proc.stdout.readexactly(size))
                if 'method' in message:
                    if 'id' in message:
                        if message['method'] == 'workspace/configuration':
                            reply = dict(result=[{} for _ in message.get('params', {}).get('items', [])])
                        else:
                            reply = dict(error={'code': -32601, 'message': 'Unsupported client operation'})
                        await self._send(dict(jsonrpc='2.0', id=message['id'], **reply))
                else:
                    fut = self.pending.get(message.get('id'))
                    if fut and not fut.done():
                        if 'error' in message:
                            fut.set_exception(RuntimeError(str(message['error'])))
                        else:
                            fut.set_result(message.get('result'))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = str(exc)
            for fut in self.pending.values():
                if not fut.done():
                    fut.set_exception(RuntimeError('Az LSP kapcsolat megszakadt: ' + self.error))

    async def start(self):
        if self.proc is not None:
            return
        self.proc = await asyncio.create_subprocess_exec(self.command, *self.args, cwd=self.root,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **group_options())
        async def drain():
            while await self.proc.stderr.read(4096):
                pass
        self.reader = asyncio.create_task(self._read())
        self.stderr = asyncio.create_task(drain())
        try:
            result = await self._request('initialize', {'processId': None, 'rootUri': self.root.as_uri(),
                'capabilities': {'general': {'positionEncodings': ['utf-16']}},
                'workspaceFolders': [{'uri': self.root.as_uri(), 'name': self.root.name}]})
            self.capabilities = result.get('capabilities', {})
            if self.capabilities.get('positionEncoding', 'utf-16') != 'utf-16':
                raise ValueError('A szerver nem UTF-16 pozíciókat használ.')
            await self._notify('initialized', {})
        except BaseException:
            await self.close()
            raise

    async def query(self, operation: str, path: str, language: str, line: int = 0, character: int = 0):
        methods = {'symbols': 'textDocument/documentSymbol', 'hover': 'textDocument/hover',
                   'definition': 'textDocument/definition', 'references': 'textDocument/references'}
        if operation not in methods or line < 0 or character < 0:
            raise ValueError('Érvénytelen LSP művelet vagy pozíció.')
        p = Path(path).expanduser()
        p = (p if p.is_absolute() else self.root / p).resolve(strict=True)
        if not p.is_relative_to(self.root) or not p.is_file() or p.stat().st_size > 1_000_000:
            raise ValueError('Csak a projekten belüli, legfeljebb 1 MB-os fájl olvasható.')
        text = p.read_text(encoding='utf-8')
        uri = p.as_uri()
        async with self.lock:
            await self.start()
            await self._notify('textDocument/didOpen', {'textDocument': {'uri': uri, 'languageId': language, 'version': 1, 'text': text}})
            try:
                params = {'textDocument': {'uri': uri}}
                if operation != 'symbols':
                    params['position'] = dict(line=line, character=character)
                if operation == 'references':
                    params['context'] = dict(includeDeclaration=True)
                return await self._request(methods[operation], params)
            finally:
                if self.proc and self.proc.returncode is None:
                    await self._notify('textDocument/didClose', {'textDocument': {'uri': uri}})

    async def close(self):
        if self.proc and self.proc.returncode is None:
            try:
                if self.reader and not self.reader.done():
                    await self._request('shutdown', None, timeout=1)
                    await self._notify('exit', None)
                    await asyncio.wait_for(self.proc.wait(), 1)
            except Exception:
                pass
            finally:
                await terminate(self.proc)
        for task in (self.reader, self.stderr):
            if task and not task.done():
                task.cancel()
        await asyncio.gather(*(t for t in (self.reader, self.stderr) if t), return_exceptions=True)
        self.proc = None
