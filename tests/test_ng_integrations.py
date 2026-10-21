import asyncio
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

from test_ng_workbench import make
from jarvis.extensions.pairing import Pairing, authorized
from jarvis.extensions.processes import ProcessManager
from jarvis.extensions.lsp import LSPClient
from jarvis.extensions.sources import calendar_events, email_headers
from jarvis.server.app import create_app
from jarvis.utils.shell import run_command


class PairingTests(unittest.TestCase):
    def test_only_hash_persisted_expiry_revocation_and_rotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Pairing(Path(tmp)/'pair.json')
            first = p.create()
            self.assertTrue(p.valid(first['token']))
            self.assertNotIn(first['token'], p.path.read_text())
            second = p.create()
            self.assertFalse(p.valid(first['token']))
            self.assertTrue(p.valid(second['token']))
            with patch('jarvis.extensions.pairing.time.time', return_value=second['expires']+1):
                self.assertFalse(p.valid(second['token']))
            p.revoke()
            self.assertFalse(p.valid(second['token']))

    def test_origin_host_and_remote_auth_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Pairing(Path(tmp)/'pair.json')
            token = p.create()['token']
            def scope(client='127.0.0.1', host='localhost', origin=None, auth=''):
                return SimpleNamespace(client=SimpleNamespace(host=client), url=SimpleNamespace(hostname=host),
                    headers={**({'origin': origin} if origin else {}), **({'authorization': auth} if auth else {})}, cookies={})
            self.assertTrue(authorized(scope(), p))
            self.assertFalse(authorized(scope(origin='https://evil.example'), p))
            self.assertFalse(authorized(scope(host='evil.example'), p))
            self.assertFalse(authorized(scope(client='192.168.1.8', host='192.168.1.2'), p))
            self.assertTrue(authorized(scope(client='192.168.1.8', host='192.168.1.2', origin='http://192.168.1.2:7341', auth='Bearer '+token), p))
            self.assertFalse(authorized(scope(client='192.168.1.8', host='192.168.1.2', origin='https://evil.example', auth='Bearer '+token), p))

    def test_http_and_ws_protected_and_pair_cookie_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, memory, wb, registry, brain, orch = make(Path(tmp))
            agents = SimpleNamespace(list=lambda: [], names=lambda: [])
            app = create_app(cfg, orch, registry, memory, agents)
            # Do not enter lifespan: this is a local API/auth contract test,
            # not a GPU preload / external voice model download.
            local = TestClient(app)
            response = local.post('/api/workbench/pairing')
            self.assertEqual(response.status_code, 200, response.text)
            token = response.json()['token']
            from starlette.testclient import TestClient as StarletteClient
            remote = StarletteClient(app, base_url='http://192.168.1.2', client=('192.168.1.8', 5000))
            self.assertEqual(remote.get('/api/health').status_code, 401)
            self.assertEqual(remote.get('/phone').status_code, 200)
            self.assertEqual(remote.post('/api/phone/pair', json={'token': token}).status_code, 200)
            self.assertEqual(remote.get('/api/health').status_code, 200)
            self.assertEqual(remote.get('/api/workbench/status').status_code, 403)
            with remote.websocket_connect('ws://192.168.1.2/ws') as socket:
                self.assertEqual(socket.receive_json()['type'], 'info')
                self.assertEqual(socket.receive_json()['type'], 'session_state')
                socket.send_json({'type': 'ping'})
                self.assertEqual(socket.receive_json()['type'], 'pong')
            local.delete('/api/workbench/pairing')
            self.assertEqual(remote.get('/api/health').status_code, 401)
            local.close(); remote.close()


class ProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_output_is_bounded_and_process_reaped(self):
        manager = ProcessManager()
        with tempfile.TemporaryDirectory() as tmp:
            result = await manager.run(sys.executable, ['-c', 'print("x"*1000000)'], tmp, 5)
            self.assertEqual(result['returncode'], 0)
            self.assertLessEqual(sum(len(x[1]) for x in result['output']), 204800)
            self.assertEqual(manager.entries, {})

    async def test_timeout_and_cancellation_cleanup(self):
        manager = ProcessManager()
        with tempfile.TemporaryDirectory() as tmp:
            result = await manager.run(sys.executable, ['-c', 'import time; time.sleep(100)'], tmp, .1)
            self.assertTrue(result['timed_out'])
            task = asyncio.create_task(manager.run(sys.executable, ['-c', 'import time; time.sleep(100)'], tmp, 100))
            await asyncio.sleep(.05)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.assertEqual(manager.entries, {})

    async def test_shell_uses_same_supervision(self):
        result = await run_command('echo jarvis', timeout=5)
        self.assertTrue(result.ok)
        self.assertIn('jarvis', result.stdout)

    async def test_lsp_real_framed_process_initialize_symbols_and_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server = root/'lsp.py'
            server.write_text('''import json,sys
while True:
 headers={}
 while True:
  line=sys.stdin.buffer.readline()
  if not line:sys.exit(0)
  if line==b"\\r\\n":break
  k,v=line.decode().split(":",1);headers[k.lower()]=v.strip()
 msg=json.loads(sys.stdin.buffer.read(int(headers["content-length"])))
 if "id" not in msg:
  if msg.get("method")=="exit":sys.exit(0)
  continue
 method=msg.get("method")
 result={"capabilities":{"documentSymbolProvider":True}} if method=="initialize" else [{"name":"hello","kind":12}] if method=="textDocument/documentSymbol" else None
 data=json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":result}).encode()
 sys.stdout.buffer.write(f"Content-Length: {len(data)}\\r\\n\\r\\n".encode()+data);sys.stdout.buffer.flush()
''')
            (root/'source.py').write_text('def hello(): pass')
            client = LSPClient(sys.executable, [str(server)], root)
            result = await client.query('symbols', 'source.py', 'python')
            self.assertEqual(result[0]['name'], 'hello')
            with self.assertRaises(ValueError):
                await client.query('symbols', '/etc/passwd', 'python')
            await client.close()
            self.assertIsNone(client.proc)


class SourceTests(unittest.TestCase):
    def test_ics_recurrence_expansion_with_timezone(self):
        from icalendar import Calendar, Event
        zone = ZoneInfo('Europe/Budapest')
        now = datetime.now(zone).replace(hour=23, minute=55, second=0, microsecond=0)
        cal = Calendar()
        cal.add('prodid', '-//Jarvis Test//HU')
        cal.add('version', '2.0')
        event = Event()
        event.add('uid', 'jarvis-test')
        event.add('summary', 'Magyar ismétlődés')
        event.add('dtstart', now)
        event.add('dtend', now + timedelta(minutes=5))
        event.add('rrule', {'freq': 'daily', 'count': 3})
        cal.add_component(event)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'calendar.ics'
            path.write_bytes(cal.to_ical())
            events = calendar_events([path], 'Europe/Budapest', 7)
            self.assertEqual(len(events), 3)
            self.assertTrue(all(e['title'] == 'Magyar ismétlődés' for e in events))

    def test_mail_reads_headers_without_marking_seen(self):
        calls = []
        class FakeIMAP:
            def login(self, *args): pass
            def select(self, folder, readonly=False):
                calls.append(('readonly', readonly));return 'OK', [b'1']
            def status(self, *args): return 'OK', [b'INBOX (UIDVALIDITY 5 UIDNEXT 3)']
            def uid(self, op, *args):
                calls.append((op, args))
                if op=='search': return 'OK', [b'2']
                return 'OK', [(b'2', b'From: sender@example.com\r\nSubject: =?utf-8?b?w4FydsOtenTFsXLFkQ==?=\r\n\r\n')]
            def logout(self): pass
        config = SimpleNamespace(user_env='TEST_IMAP_USER', password_env='TEST_IMAP_PASS', host='example.invalid', port=993, folder='INBOX')
        with patch.dict('os.environ', {'TEST_IMAP_USER':'user','TEST_IMAP_PASS':'test-password'}), patch('jarvis.extensions.sources.imaplib.IMAP4_SSL', return_value=FakeIMAP()):
            result = email_headers(config)
        self.assertEqual(result['last_uid'], 2)
        self.assertTrue(calls[0][1])
        self.assertTrue(any('BODY.PEEK' in str(c) for c in calls))
        self.assertNotIn('test-password', json.dumps(result))


class SemanticScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_identical_facts_can_be_learned_in_two_projects_without_leaking_to_a_third(self):
        from jarvis.config import Config
        from jarvis.core.semantic_memory import SemanticMemory
        class Embedder:
            async def embed(self, text): return [1.0, 0.0]
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(project_root=Path(tmp))
            memory = SemanticMemory(cfg, Embedder())
            await memory.remember('Közös döntés', meta={'project_id': 'a'})
            self.assertEqual(len(await memory.recall('döntés', project_id='a')), 1)
            self.assertEqual(await memory.recall('döntés', project_id='b'), [])
            await memory.remember('Közös döntés', meta={'project_id': 'b'})
            self.assertEqual(len(await memory.recall('döntés', project_id='b')), 1)
            self.assertEqual(await memory.recall('döntés', project_id='c'), [])
            self.assertEqual(memory.count(), 1)
