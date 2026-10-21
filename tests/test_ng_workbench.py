import asyncio
import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jarvis.config import Config, load_config
from jarvis.core.brain import BrainReply, ToolCall
from jarvis.core.events import EventKind
from jarvis.core.hooks import HookRegistry
from jarvis.core.logger import ActionLog
from jarvis.core.memory import Memory
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.permissions import Permission, PermissionManager, PermissionRequest, Decision
from jarvis.extensions.files import FileGuard, Checkpoints, file_owner
from jarvis.extensions.resilience import repair_history, redact
from jarvis.extensions.runtime import Workbench
from jarvis.extensions.skills import SkillCatalog
from jarvis.extensions.store import WorkbenchStore
from jarvis.plugins.base import Tool
from jarvis.plugins.registry import PluginRegistry
from jarvis.plugins import file_tools, workbench_tools
from jarvis.server.workbench import router


class FakeBrain:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.prompts = []

    def build_system_prompt(self, persona, tools):
        return persona + '\n' + tools

    async def chat_stream(self, messages, tool_schemas=None, on_delta=None):
        self.active += 1
        self.max_active = max(self.active, self.max_active)
        self.prompts.append(messages)
        try:
            await asyncio.sleep(.01)
            return BrainReply(text='Elvégeztem az ellenőrzést.')
        finally:
            self.active -= 1


def make(root):
    cfg = Config(project_root=root, ultimate={'enabled': False}, ng={'quiet_start': 0, 'quiet_end': 0})
    mem = Memory(cfg)
    wb = Workbench(cfg, mem)
    registry = PluginRegistry(cfg, services={'workbench': wb, 'memory': mem})
    brain = FakeBrain()
    orch = Orchestrator(cfg, brain, registry, mem, PermissionManager(cfg), ActionLog(cfg))
    registry.services['orchestrator'] = orch
    registry.services['cfg'] = cfg
    wb.restore(orch)
    file_tools.register(registry)
    workbench_tools.register(registry)
    return cfg, mem, wb, registry, brain, orch


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = WorkbenchStore(self.root / 'memory.db', self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_tables_survive_and_migration_is_idempotent(self):
        with self.store.connection() as c:
            c.execute('CREATE TABLE legacy(value TEXT)')
            c.execute("INSERT INTO legacy VALUES('megmarad')")
        other = WorkbenchStore(self.store.path, self.root)
        self.assertEqual(len(other.projects()), 1)
        with other.connection() as c:
            self.assertEqual(c.execute('SELECT value FROM legacy').fetchone()[0], 'megmarad')

    def test_projects_sessions_do_not_mix_and_persist(self):
        project = self.store.create_project('Router', str(self.root))
        session = self.store.create_session('Javítás', project['id'])
        self.store.save_session(session['id'], [{'role': 'user', 'content': 'titkos router döntés'}], 'összegzés')
        self.assertEqual(self.store.session('default')['history'], [])
        self.store.activate(session['id'])
        other = WorkbenchStore(self.store.path, self.root)
        self.assertEqual(other.session()['summary'], 'összegzés')
        self.assertEqual(other.session()['history'][0]['content'], 'titkos router döntés')

    def test_missing_project_rejected(self):
        with self.assertRaises(ValueError):
            self.store.create_session('Hibás', 'missing')
        with self.assertRaises(OSError):
            self.store.create_project('Hibás', str(self.root / 'missing'))

    def test_crash_marks_recovery_without_replaying(self):
        self.store.save_session('default', [{'role': 'user', 'content': 'munka'}], '', 'running')
        other = WorkbenchStore(self.store.path, self.root)
        self.assertEqual(other.session()['status'], 'interrupted')
        self.assertEqual(other.events()[0]['kind'], 'recovery')

    def test_profiles_have_scope_source_expiration_and_deletion(self):
        self.store.set_profile('név', 'Miklós', 'felhasználó')
        self.store.set_profile('döntés', 'A', 'projekt', 'a')
        self.store.set_profile('lejárt', 'régi', 'forrás', expires=time.time() - 1)
        self.assertEqual({p['key'] for p in self.store.profiles('b')}, {'név'})
        self.assertEqual({p['key'] for p in self.store.profiles('a')}, {'név', 'döntés'})
        self.store.set_profile('döntés', 'B', 'új forrás', 'a')
        self.assertEqual(next(p for p in self.store.profiles('a') if p['key'] == 'döntés')['value'], 'B')
        self.assertTrue(self.store.delete_profile('döntés', 'a'))

    def test_reminders_atomic_restart_dedup_and_missed_repeat_coalescing(self):
        rid = self.store.remind('Ellenőrizd', 100, 60)
        self.assertEqual(self.store.tick_reminders(400), 1)
        other = WorkbenchStore(self.store.path, self.root)
        self.assertEqual(other.tick_reminders(400), 0)
        self.assertEqual(other.reminders()[0]['due'], 460)
        self.assertEqual(len(other.events()), 1)
        self.assertTrue(other.cancel_reminder(rid))
        self.assertEqual(other.tick_reminders(1000), 0)
        with self.assertRaises(ValueError):
            self.store.remind('Hiba', float('nan'))

    def test_task_dependencies_enforced_and_scoped(self):
        first = self.store.task_add('Előkészítés', 'default')
        second = self.store.task_add('Befejezés', 'default', [first])
        with self.assertRaises(ValueError):
            self.store.task_update(second, 'default', 'done')
        with self.assertRaises(ValueError):
            self.store.task_update(first, 'other', 'done')
        self.store.task_update(first, 'default', 'done')
        self.store.task_update(second, 'default', 'done', 'ellenőrizve')
        self.assertTrue(all(t['status'] == 'done' for t in self.store.tasks('default')))


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.guard = FileGuard()
        self.cp = Checkpoints(self.root / 'snapshots', self.guard, 1000)

    def tearDown(self):
        self.tmp.cleanup()

    def test_edit_requires_read_and_detects_external_change(self):
        p = self.root / 'a.txt'
        p.write_text('első')
        with self.assertRaises(ValueError):
            self.guard.write(p, 'új')
        self.guard.observe(p)
        p.write_text('másik folyamat')
        with self.assertRaises(ValueError):
            self.guard.write(p, 'felülírás')
        self.assertEqual(p.read_text(), 'másik folyamat')
        self.guard.observe(p)
        self.guard.write(p, 'sikeres')
        self.assertEqual(p.read_text(), 'sikeres')

    def test_agent_reads_are_not_shared(self):
        p = self.root / 'a.txt'
        p.write_text('első')
        token = file_owner.set('a')
        self.guard.observe(p)
        file_owner.set('b')
        self.guard.observe(p)
        self.guard.write(p, 'b módosította')
        file_owner.set('a')
        with self.assertRaises(ValueError):
            self.guard.write(p, 'a régi tartalma')
        file_owner.reset(token)

    def test_checkpoint_preview_token_restore_and_undo(self):
        p = self.root / 'a.txt'
        p.write_text('eredeti')
        snap = self.cp.capture(self.root, ['a.txt', 'új.txt'])
        p.write_text('módosított')
        (self.root / 'új.txt').write_text('új')
        preview = self.cp.preview(snap['id'], self.root)
        p.write_text('közben változott')
        with self.assertRaises(ValueError):
            self.cp.restore(snap['id'], self.root, preview['token'])
        preview = self.cp.preview(snap['id'], self.root)
        result = self.cp.restore(snap['id'], self.root, preview['token'])
        self.assertEqual(p.read_text(), 'eredeti')
        self.assertFalse((self.root / 'új.txt').exists())
        undo = self.cp.preview(result['undo_id'], self.root)
        self.cp.restore(result['undo_id'], self.root, undo['token'])
        self.assertEqual(p.read_text(), 'közben változott')
        self.assertTrue((self.root / 'új.txt').exists())

    def test_checkpoint_secrets_escape_symlink_and_size_rejected(self):
        for rel in ['../x', '.env', '.git/config', '/tmp/x']:
            with self.assertRaises(ValueError, msg=rel):
                self.cp.capture(self.root, [rel])
        p = self.root / 'large'
        p.write_bytes(b'x' * 1001)
        with self.assertRaises(ValueError):
            self.cp.capture(self.root, ['large'])
        link = self.root / 'link'
        try:
            link.symlink_to(p)
        except OSError:
            return  # Windows may require Developer Mode for symlinks.
        with self.assertRaises(ValueError):
            self.cp.capture(self.root, ['link'])


class ResilienceTests(unittest.TestCase):
    def test_missing_native_result_repaired_and_orphan_removed(self):
        history = [{'role': 'tool', 'tool_call_id': 'orphan', 'content': 'x'},
                   {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'a'}, {'id': 'b'}]},
                   {'role': 'tool', 'tool_call_id': 'a', 'content': 'kész'}, {'role': 'user', 'content': 'következő'}]
        fixed = repair_history(history)
        self.assertEqual(len(fixed), 4)
        self.assertEqual(fixed[1]['content'], 'kész')
        self.assertIn('bizonytalan', fixed[2]['content'])
        self.assertEqual(repair_history(fixed), fixed)

    def test_audit_redacts_nested_and_inline_credentials(self):
        output = json.dumps(redact({'args': {'api_key': 'private', 'nested': ['Bearer foobar', 'token=abcdef']}, 'error': 'https://user:pass@example.com/path sk-proj-abcdefghijklmnop'}))
        for value in ['private', 'foobar', 'abcdef', 'user:pass', 'sk-proj-']:
            self.assertNotIn(value, output)

    def test_scoped_permissions_deny_wins_and_expired_grant_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(permissions={'mode': 'confirm', 'rules': [
                {'tool': 'write_file', 'effect': 'allow', 'root': tmp},
                {'tool': 'delete', 'effect': 'allow', 'expires': time.time() - 1},
                {'tool': 'write_file', 'effect': 'deny', 'root': str(Path(tmp) / 'protected')}]})
            perms = PermissionManager(cfg)
            req = lambda tool, path: PermissionRequest(tool, {'path': path}, Permission.CAUTION, '')
            self.assertEqual(perms.evaluate(req('write_file', str(Path(tmp)/'a'))), Decision.ALLOW)
            self.assertEqual(perms.evaluate(req('write_file', str(Path(tmp)/'protected'/'a'))), Decision.DENY)
            self.assertEqual(perms.evaluate(req('write_file', '/other')), Decision.ASK)
            self.assertEqual(perms.evaluate(req('delete', str(Path(tmp)/'a'))), Decision.ASK)

    def test_skill_yaml_hungarian_triggers_explicit_read_and_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'hu').mkdir()
            (root/'hu'/'SKILL.md').write_text('---\nname: pelda\ndescription: Magyar\ntriggers:\n  - árvíztűrő\n---\nPontos útmutató.', encoding='utf-8')
            (root/'bad').mkdir()
            (root/'bad'/'SKILL.md').write_text('hibás')
            cat = SkillCatalog([root])
            self.assertIn('Pontos útmutató', cat.context('Arvizturo feladat'))
            self.assertIn('Pontos útmutató', cat.context('$pelda'))
            self.assertEqual(cat.context('más feladat'), '')
            self.assertEqual(len(cat.errors), 1)


class APIAndSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg, _, self.wb, registry, _, self.orch = make(self.root)
        app = FastAPI()
        app.state.registry = registry
        app.state.orchestrator = self.orch
        app.state.cfg = self.cfg
        app.include_router(router, prefix='/api/workbench')
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_project_session_profile_reminder_task_round_trip(self):
        p = self.client.post('/api/workbench/projects', json={'name': 'Router', 'path': str(self.root)}).json()
        s = self.client.post('/api/workbench/sessions', json={'name': 'Munka', 'project_id': p['id']}).json()
        self.assertEqual(self.client.post(f'/api/workbench/sessions/{s["id"]}/activate').status_code, 200)
        self.assertEqual(self.wb.active['project_id'], p['id'])
        self.assertEqual(self.client.post('/api/workbench/profiles', json={'key': 'cél', 'value': 'magyar'}).status_code, 200)
        self.assertEqual(self.client.get('/api/workbench/profiles').json()[0]['value'], 'magyar')
        self.assertEqual(self.client.post('/api/workbench/reminders', json={'text': 'teszt', 'due': '2026-10-22T09:00:00+02:00'}).status_code, 200)
        self.assertEqual(self.client.post('/api/workbench/reminders', json={'text': 'teszt', 'due': '2026-10-22T09:00:00'}).status_code, 400)
        t = self.client.post('/api/workbench/tasks', json={'title': 'Első'}).json()
        self.assertEqual(self.client.patch('/api/workbench/tasks/'+t['id'], json={'status': 'done'}).status_code, 200)

    def test_cross_site_and_remote_clients_blocked(self):
        self.assertEqual(self.client.post('/api/workbench/profiles', headers={'Origin': 'https://evil.example'}, json={'key': 'x', 'value': 'y'}).status_code, 403)
        self.assertEqual(self.client.get('/api/workbench/status', headers={'Host': 'evil.example'}).status_code, 403)

    def test_voice_save_preserves_custom_configuration_and_creates_backup(self):
        import yaml
        original = {'model': {'model': 'custom', 'api_key_env': 'MY_KEY'}, 'A': {'persona': 'Saját személyiség'}, 'voice': {'wake_word': 'Hello Jarvis'}, 'custom': {'keep': True}}
        (self.root/'config.yaml').write_text(yaml.safe_dump(original, allow_unicode=True), encoding='utf-8')
        self.cfg.config_source = self.root/'config.yaml'
        response = self.client.post('/api/workbench/voice', json={'provider': 'edge_tts', 'voice': 'hu-HU-TamasNeural'})
        self.assertEqual(response.status_code, 200, response.text)
        saved = yaml.safe_load((self.root/'config.yaml').read_text())
        self.assertEqual(saved['model'], original['model'])
        self.assertEqual(saved['A'], original['A'])
        self.assertEqual(saved['custom'], original['custom'])
        self.assertEqual(saved['voice']['wake_word'], 'Hello Jarvis')
        self.assertEqual(self.cfg.voice.provider, 'edge_tts')
        self.assertEqual(len(list((self.root/'data/backups').glob('*.yaml'))), 1)
        self.assertEqual(self.client.post('/api/workbench/voice', json={'provider': 'piper'}).status_code, 400)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg, self.mem, self.wb, self.registry, self.brain, self.orch = make(self.root)

    async def asyncTearDown(self):
        await self.wb.close()
        self.tmp.cleanup()

    async def consume(self, text):
        return [event async for event in self.orch.handle_user_message(text)]

    async def test_concurrent_clients_serialized_and_history_survives_restart(self):
        await asyncio.gather(self.consume('Árvíztűrő első kérdés.'), self.consume('Tükörfúrógép második kérdés.'))
        self.assertEqual(self.brain.max_active, 1)
        history = self.wb.store.session()['history']
        self.assertEqual(sum(m['role'] == 'user' for m in history), 2)
        _, _, wb2, _, _, orch2 = make(self.root)
        self.assertEqual(orch2._history, self.orch._history)
        session = wb2.store.create_session('Külön')
        wb2.select(session['id'], orch2)
        self.assertEqual(orch2._history, [])
        await wb2.close()

    async def test_cancelled_tool_does_not_keep_running(self):
        cancelled = asyncio.Event()
        started = asyncio.Event()
        async def slow():
            started.set()
            try:
                await asyncio.sleep(100)
            finally:
                cancelled.set()
        self.registry.add(Tool('slow', '', {}, slow))
        async def execute():
            return [e async for e in self.orch._invoke_tool(ToolCall('slow', {}))]
        task = asyncio.create_task(execute())
        await started.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertTrue(cancelled.is_set())
        self.assertIsNone(self.orch.busy_tool)

    async def test_pre_hook_arguments_rechecked_by_permissions(self):
        self.cfg.permissions.rules = []
        self.orch.permissions = PermissionManager(Config(permissions={'denylist': ['forbidden']}))
        ran = []
        self.registry.add(Tool('test_hook', '', {}, lambda path: ran.append(path)))
        self.orch.hooks.add_pre(lambda name, args: {'path': 'forbidden'})
        events = [e async for e in self.orch._invoke_tool(ToolCall('test_hook', {'path': 'safe'}, call_id='native'))]
        self.assertEqual(ran, [])
        self.assertTrue(any(e.payload.get('denied') for e in events))
        self.assertEqual(self.orch._history[-1]['tool_call_id'], 'native')

    async def test_quiet_hours_and_notification_budget(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        self.cfg.ng.quiet_start, self.cfg.ng.quiet_end = 22, 8
        self.cfg.ng.notifications_per_hour = 1
        now = datetime(2026, 10, 21, 23, tzinfo=ZoneInfo('Europe/Budapest')).timestamp()
        self.assertFalse(self.wb.can_notify(now))
        day = now + 12 * 3600
        self.assertTrue(self.wb.can_notify(day))
        self.assertFalse(self.wb.can_notify(day + 1))
        self.assertTrue(self.wb.can_notify(day + 3601))

    async def test_file_watcher_publishes_changes_only_after_baseline(self):
        p = self.root/'watched.txt'
        p.write_text('eredeti')
        self.cfg.ng.watch_paths = [str(p)]
        self.wb._watch()
        self.assertEqual(self.wb.store.events(), [])
        p.write_text('módosított')
        self.wb._watch()
        self.assertEqual(self.wb.store.events()[0]['kind'], 'file_changed')

    async def test_mcp_real_stdio_list_call_error_close(self):
        from jarvis.extensions.mcp import MCPBridge
        from jarvis.config import MCPServerConfig
        server = self.root/'server.py'
        server.write_text('from mcp.server.fastmcp import FastMCP\nm=FastMCP("test")\n@m.tool()\ndef add(a:int,b:int)->int:\n return a+b\n@m.tool()\ndef fail()->str:\n raise ValueError("hiba")\nm.run(transport="stdio")\n')
        bridge = MCPBridge(self.registry, {'test': MCPServerConfig(enabled=True, command=sys.executable, args=[str(server)], timeout_seconds=5)})
        await bridge.start()
        self.assertEqual(bridge.status['test']['state'], 'ready', bridge.status)
        tool = next(t for t in self.registry.all_tools() if t.name.startswith('mcp_test_add'))
        result = await tool.invoke({'a': 2, 'b': 3})
        self.assertIn('5', json.dumps(result))
        with self.assertRaises(RuntimeError):
            await bridge.call('test', 'fail', {})
        await bridge.close()
        self.assertIsNone(self.registry.get(tool.name))

    async def test_broken_mcp_does_not_stop_chat(self):
        from jarvis.extensions.mcp import MCPBridge
        from jarvis.config import MCPServerConfig
        bridge = MCPBridge(self.registry, {'bad': MCPServerConfig(enabled=True, command='/no/such/program', timeout_seconds=1)})
        await bridge.start()
        self.assertEqual(bridge.status['bad']['state'], 'error')
        events = await self.consume('Árvíztűrő próbakérdés.')
        self.assertTrue(any(e.kind is EventKind.ASSISTANT for e in events))
        await bridge.close()

    async def test_team_separate_contexts_dependency_messages_and_confirmation_forwarding(self):
        class TeamBrain(FakeBrain):
            async def chat_stream(self, messages, tool_schemas=None, on_delta=None):
                self.prompts.append(messages)
                if any(m.get('role') == 'tool' for m in messages):
                    return BrainReply(text='A fájlt elkészítettem.')
                return BrainReply(text='', tool_calls=[ToolCall('write_file', {'path': str(self_root/'agent.txt'), 'content': 'kész'}, call_id='w1')])
        self_root = self.root
        self.orch.brain = TeamBrain()
        self.registry.services['orchestrator'] = self.orch
        approvals = []
        call = ToolCall('team_run', {'tasks': [{'label': 'író', 'goal': 'Hozd létre az agent.txt fájlt.', 'tools': ['write_file']}]})
        async for event in self.orch._invoke_tool(call):
            if event.kind is EventKind.CONFIRMATION:
                approvals.append(event.confirm_req.tool)
                event.confirm_future.set_result(True)
        self.assertIn('team_run', approvals)
        self.assertIn('write_file', approvals)
        self.assertEqual((self.root/'agent.txt').read_text(), 'kész')
        self.assertEqual(self.wb.store.tasks('default')[0]['status'], 'done')
        self.assertFalse(any('parent private secret' in str(m) for m in self.orch.brain.prompts))

    async def test_team_dag_cycle_rejected_before_model_or_state_changes(self):
        from jarvis.extensions.team import run_team
        with self.assertRaises(ValueError):
            await run_team(self.registry, [{'label': 'a', 'goal': 'a', 'depends_on': ['b']}, {'label': 'b', 'goal': 'b', 'depends_on': ['a']}])
        self.assertEqual(self.wb.store.tasks('default'), [])
        self.assertEqual(self.brain.prompts, [])


class AdditionalRegressionTests(unittest.TestCase):
    def test_changed_results_reset_repeat_guard(self):
        from jarvis.extensions.resilience import RepeatGuard
        guard = RepeatGuard(2)
        for result in ['one', 'two', 'three', 'four']:
            guard.check('read', {'path': 'a'})
            guard.outcome('read', {'path': 'a'}, result)
        guard.check('read', {'path': 'a'})
        guard.outcome('read', {'path': 'a'}, 'four')
        guard.check('read', {'path': 'a'})
        guard.outcome('read', {'path': 'a'}, 'four')
        with self.assertRaises(PermissionError):
            guard.check('read', {'path': 'a'})

    def test_public_history_hides_internal_tool_and_thinking_messages(self):
        from jarvis.extensions.resilience import public_history
        history = [dict(role='user', content='Kérdés'), dict(role='assistant', content='<thinking>internal</thinking>Válasz'),
                   dict(role='assistant', content='<tool_call>{"x":1}</tool_call>'), dict(role='tool', content='eredmény'),
                   dict(role='user', content='<tool_result>internal</tool_result>'), dict(role='user', content='(internal protocol — x)')]
        self.assertEqual(public_history(history), [dict(role='user', content='Kérdés'), dict(role='assistant', content='Válasz')])

    def test_hungarian_durable_facts_and_negative_request(self):
        from jarvis.core.orchestrator import _extract_durable_fact
        self.assertEqual(_extract_durable_fact('Jegyezd meg, hogy a router projekt OpenWrt alapú.'), ('fact', 'a router projekt OpenWrt alapú.'))
        self.assertEqual(_extract_durable_fact('A nevem Miklós.')[0], 'fact')
        self.assertEqual(_extract_durable_fact('Jobban szeretem a magyar válaszokat.')[0], 'preference')
        self.assertIsNone(_extract_durable_fact('Ne jegyezd meg a következő mondatot.'))

    def test_provider_errors_are_classified_without_exposing_credentials(self):
        import httpx
        from jarvis.extensions.resilience import error_summary
        request = httpx.Request('GET', 'https://example.invalid')
        exc = httpx.HTTPStatusError('api_key=do-not-print', request=request, response=httpx.Response(429, request=request))
        result = error_summary(exc)
        self.assertEqual(result['code'], 'rate_limit')
        self.assertTrue(result['retryable'])
        self.assertNotIn('do-not-print', json.dumps(result))

    def test_system_log_filter_redacts_exception_values(self):
        import logging
        from jarvis.core.logger import RedactingFilter
        try:
            raise ValueError('token=do-not-print')
        except ValueError:
            record = logging.LogRecord('test', logging.ERROR, '', 1, 'failure', (), sys.exc_info())
        RedactingFilter().filter(record)
        self.assertNotIn('do-not-print', record.getMessage())
        self.assertIsNone(record.exc_info)


class NativeProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_native_tool_always_has_matching_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, wb, _, _, orch = make(Path(tmp))
            events = [e async for e in orch._invoke_tool(ToolCall('missing', {}, call_id='native-missing'))]
            self.assertEqual(orch._history[-1]['role'], 'tool')
            self.assertEqual(orch._history[-1]['tool_call_id'], 'native-missing')
            self.assertFalse(events[-1].payload['ok'])
            await wb.close()

    async def test_write_consumes_read_observation_even_for_same_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root/'a.txt'
            path.write_text('eredeti')
            guard = FileGuard()
            guard.observe(path)
            guard.write(path, 'első módosítás')
            with self.assertRaises(ValueError):
                guard.write(path, 'régi tartalomból második módosítás')
            self.assertEqual(path.read_text(), 'első módosítás')
