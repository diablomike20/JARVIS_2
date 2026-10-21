"""Renaming from the workspace must preserve persisted project history."""
import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_ng_workbench import make
from jarvis.server.workbench import router


class SessionNameTests(unittest.TestCase):
    def test_rename_preserves_history_and_rejects_invalid_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, memory, wb, registry, brain, orch = make(Path(tmp))
            store = wb.store
            session = store.create_session('Before')
            history = [{'role': 'user', 'content': 'Preserve this'}]
            store.save_session(session['id'], history, 'summary', 'idle')
            renamed = store.rename_session(session['id'], '  Magyar név  ')
            self.assertEqual(renamed['name'], 'Magyar név')
            self.assertEqual(renamed['history'], history)
            self.assertEqual(renamed['summary'], 'summary')
            self.assertEqual(renamed['project_id'], session['project_id'])
            for name in (' ', 'x' * 121):
                with self.assertRaises(ValueError):
                    store.rename_session(session['id'], name)
            with self.assertRaises(ValueError):
                store.rename_session('missing', 'Name')

    def test_api_updates_active_name_and_blocks_busy_or_remote_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, memory, wb, registry, brain, orch = make(Path(tmp))
            app = FastAPI()
            app.state.registry = registry
            app.include_router(router, prefix='/api/workbench')
            path = '/api/workbench/sessions/' + wb.active['id']
            with TestClient(app) as client:
                self.assertEqual(client.patch(path, json={'name': 'Magyar beszélgetés'}).status_code, 200)
                self.assertEqual(wb.active['name'], 'Magyar beszélgetés')
                self.assertEqual(client.patch(path, json={'name': ' '}).status_code, 400)
                self.assertEqual(client.patch(path, json={'name': 'Name'}, headers={'Origin': 'https://evil.example'}).status_code, 403)
                # The route refuses concurrent rename while an agent is using the active session.
                import asyncio
                asyncio.run(wb.lock.acquire())
                try:
                    self.assertEqual(client.patch(path, json={'name': 'Busy'}).status_code, 409)
                finally:
                    wb.lock.release()
