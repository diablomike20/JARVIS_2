"""Separate agent contexts with durable tasks and messages, using the J2 brain.

Workers default to read-only tools. Explicit per-worker tool lists can add
write tools, with confirmation futures forwarded to the existing J2 UI.
"""
from __future__ import annotations
import asyncio
from ..core.events import EventKind
from ..core.hooks import HookRegistry
from ..core.orchestrator import Orchestrator
from ..core.permissions import Permission
from ..plugins.registry import PluginRegistry
from .store import uid

READ_TOOLS = {'read_file', 'list_dir', 'search_files', 'stat', 'web_search', 'image_search', 'video_search',
              'system_info', 'list_processes', 'workbench_status', 'skills_list', 'skill_read', 'tool_search'}


class QuietMemory:
    def append_message(self, *args, **kwargs):
        pass


async def run_team(registry, tasks: list[dict]):
    from ..core.task_progress import report, current_reporter
    from ..core.events import Event
    sink = current_reporter()
    wb = registry.services['workbench']
    parent = registry.services['orchestrator']
    if not 1 <= len(tasks) <= wb.cfg.ng.max_agents:
        raise ValueError(f'1–{wb.cfg.ng.max_agents} agent adható meg.')
    tasks = [{**t, 'label': str(t.get('label', '')).strip(), 'goal': str(t.get('goal', '')).strip(),
              'depends_on': [str(d).strip() for d in t.get('depends_on', [])]} for t in tasks]
    labels = [str(t.get('label', '')).strip() for t in tasks]
    if not all(labels) or len(set(labels)) != len(labels):
        raise ValueError('Minden agentnek egyedi név kell.')
    for task in tasks:
        if not str(task.get('goal', '')).strip():
            raise ValueError('Minden agentnek feladat kell.')
        if any(dep not in labels for dep in task.get('depends_on', [])):
            raise ValueError('Ismeretlen függőség.')
        for name in task.get('tools', []):
            if name in {'team_run', 'parallel_tasks', 'agent_backend_run'} or not registry.get(name):
                raise ValueError(f'Nem engedélyezhető csapateszköz: {name}')
    # Validate the whole DAG before starting any worker or writing task state.
    pending = {label: set(t.get('depends_on', [])) for label, t in zip(labels, tasks)}
    visited = set()
    while pending:
        ready = [k for k, deps in pending.items() if deps <= visited]
        if not ready:
            raise ValueError('Körkörös agentfüggőség.')
        visited.update(ready)
        for label in ready:
            del pending[label]
    team_id = uid()
    completed = {label: asyncio.Event() for label in labels}
    outcomes = {}
    task_ids = {}
    remaining = list(tasks)
    while remaining:
        for task in list(remaining):
            if all(dep in task_ids for dep in task.get('depends_on', [])):
                task_ids[task['label']] = wb.store.task_add(task['goal'], wb.active['project_id'],
                    [task_ids[dep] for dep in task.get('depends_on', [])], owner=f'{team_id}:{task["label"]}')
                remaining.remove(task)
    if sink:
        sink(Event(EventKind.INFO, text=f'Agentcsapat: {len(tasks)} munkatárs', payload={'swarm': True, 'swarm_run_id': team_id,
            'tasks': [{'id': f'{team_id}:{label}', 'label': label, 'tool': 'agent'} for label in labels]}))

    async def worker(task):
        label = task['label']
        tid = task_ids[label]
        try:
            for dep in task.get('depends_on', []):
                await completed[dep].wait()
                if not outcomes[dep]['ok']:
                    raise RuntimeError(f'A függő agent hibás: {dep}')
            wb.store.task_update(tid, wb.active['project_id'], 'running')
            report(f'{label}: elindult')
            child_registry = PluginRegistry(parent.cfg, services={})
            for tool in registry.all_tools():
                if (tool.name in READ_TOOLS and tool.permission is Permission.SAFE) or tool.name in task.get('tools', []):
                    child_registry.add(tool)
            child = Orchestrator(parent.cfg, parent.brain, child_registry, QuietMemory(), parent.permissions, parent.actions, HookRegistry(), semantic=None)
            # Disable auxiliary planning/summary/semantic paths without changing
            # the shared config: their feature check requires semantic != None.
            child._history = [dict(role='user', content='Csapatmunka: ' + str(task.get('role', label)) + '. Csak a kijelölt részfeladatot végezd. A szülő beszélgetéséhez nincs hozzáférésed.\n' + wb.prompt(''))]
            for dep in task.get('depends_on', []):
                msg = outcomes[dep]['result']
                wb.store.message(team_id, dep, label, msg)
                child._history.append(dict(role='user', content=f'Idézett eredmény ({dep}):\n{msg}'))
            final = []
            async def execute():
                async for event in child.handle_user_message(task['goal']):
                    if event.kind is EventKind.CONFIRMATION:
                        if sink:
                            event.swarm_id, event.swarm_label = f'{team_id}:{label}', label
                            sink(event)
                        elif event.confirm_future and not event.confirm_future.done():
                            event.confirm_future.set_result(False)
                    elif event.kind is EventKind.ASSISTANT:
                        final.append(event.text)
                    elif event.kind is EventKind.ERROR:
                        raise RuntimeError(event.text)
                    elif sink and event.kind in {EventKind.TOOL_PROPOSED, EventKind.TOOL_RESULT, EventKind.TASK_START, EventKind.TASK_END, EventKind.TASK_PROGRESS, EventKind.MEDIA}:
                        event.swarm_id, event.swarm_label = f'{team_id}:{label}', label
                        sink(event)
            await asyncio.wait_for(execute(), wb.cfg.ng.agent_timeout_seconds)
            if not final:
                raise RuntimeError('Az agent nem adott végső választ.')
            result = '\n'.join(final)[-16000:]
            outcomes[label] = dict(ok=True, result=result)
            wb.store.message(team_id, label, 'coordinator', result)
            wb.store.task_update(tid, wb.active['project_id'], 'done', result)
            report(f'{label}: kész')
        except asyncio.CancelledError:
            wb.store.task_update(tid, wb.active['project_id'], 'cancelled')
            outcomes[label] = dict(ok=False, result='Megszakítva')
            raise
        except Exception as exc:
            outcomes[label] = dict(ok=False, result=str(exc))
            wb.store.task_update(tid, wb.active['project_id'], 'failed', str(exc))
            report(f'{label}: {exc}')
        finally:
            completed[label].set()

    workers = [asyncio.create_task(worker(task), name=f'agent:{task["label"]}') for task in tasks]
    try:
        await asyncio.gather(*workers)
    finally:
        for worker_task in workers:
            if not worker_task.done():
                worker_task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    if sink:
        sink(Event(EventKind.INFO, text='Agentcsapat befejezve', payload={'swarm': True, 'swarm_run_id': team_id,
            'summary': [{'label': k, **v} for k, v in outcomes.items()]}))
    return {'team_id': team_id, 'agents': outcomes, 'mode': 'explicit_tools', 'note': 'Alapból olvasási eszközök; a külön megadott eszközök rendes J2 jogosultságkezeléssel futnak.'}
