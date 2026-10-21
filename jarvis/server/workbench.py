"""Local workbench management API. Reads have no side effects; edits are explicit.

The existing J2 server is a local desktop server. New management routes reject
cross-site origins and remote clients; this does not claim to authenticate the
older, unrelated J2 endpoints or expose the server safely to the Internet.
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


def service(request: Request):
    host = request.client.host if request.client else ''
    if host not in {'127.0.0.1', '::1', 'localhost', 'testclient'}:
        raise HTTPException(403, 'Ez a kezelőfelület csak a helyi gépről érhető el.')
    origin = request.headers.get('origin')
    if origin and urlsplit(origin).hostname not in {'localhost', '127.0.0.1', '::1', 'testserver'}:
        raise HTTPException(403, 'Idegen weboldalról érkező kérés.')
    if request.url.hostname not in {'localhost', '127.0.0.1', '::1', 'testserver'}:
        raise HTTPException(403, 'Ismeretlen kiszolgálónév.')
    wb = request.app.state.registry.services.get('workbench')
    if wb is None:
        raise HTTPException(503, 'Az NG bővítmények ki vannak kapcsolva.')
    return wb


def bad_value(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


class ProjectBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    path: str


class SessionBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    project_id: str = 'default'


class ProfileBody(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(max_length=8000)
    source: str = 'Felhasználói beállítás'
    global_scope: bool = False
    confidence: float = Field(default=1, ge=0, le=1)
    expires: float | None = None


class ReminderBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    due: str
    repeat_seconds: float = Field(default=0, ge=0)


class TaskBody(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    dependencies: list[str] = Field(default_factory=list)
    owner: str = ''


class TaskUpdate(BaseModel):
    status: str
    result: str = ''


@router.get('/status')
async def status(request: Request, wb=Depends(service)):
    return wb.diagnostics(request.app.state.registry)


@router.get('/projects')
async def projects(wb=Depends(service)):
    return wb.store.projects()


@router.post('/projects')
async def project(body: ProjectBody, wb=Depends(service)):
    return bad_value(wb.store.create_project, body.name, body.path)


@router.get('/sessions')
async def sessions(wb=Depends(service)):
    return wb.store.sessions()


@router.post('/sessions')
async def session(body: SessionBody, wb=Depends(service)):
    return bad_value(wb.store.create_session, body.name, body.project_id)


class SessionRenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.patch('/sessions/{sid}')
async def rename_session(sid: str, body: SessionRenameBody, wb=Depends(service)):
    if wb.lock.locked():
        raise HTTPException(409, 'Előbb állítsd le vagy várd meg a futó feladatot.')
    async with wb.lock:
        item = bad_value(wb.store.rename_session, sid, body.name)
        if wb.active['id'] == sid:
            wb.active['name'] = item['name']
        return {'id': sid, 'name': item['name']}


@router.post('/sessions/{sid}/activate')
async def activate(sid: str, request: Request, wb=Depends(service)):
    if wb.lock.locked():
        raise HTTPException(409, 'Előbb állítsd le vagy várd meg a futó feladatot.')
    async with wb.lock:
        bad_value(wb.select, sid, request.app.state.orchestrator)
        return {'ok': True, 'session_id': sid}


@router.get('/history')
async def history(wb=Depends(service)):
    from ..extensions.resilience import public_history
    return public_history(wb.store.session()['history'])


@router.get('/profiles')
async def profiles(wb=Depends(service)):
    return wb.store.profiles(wb.active['project_id'], include_expired=True)


@router.post('/profiles')
async def profile(body: ProfileBody, wb=Depends(service)):
    bad_value(wb.store.set_profile, body.key, body.value, body.source, '' if body.global_scope else wb.active['project_id'], body.confidence, body.expires)
    return {'ok': True}


@router.delete('/profiles/{key}')
async def forget(key: str, global_scope: bool = False, wb=Depends(service)):
    return {'deleted': wb.store.delete_profile(key, '' if global_scope else wb.active['project_id'])}


@router.get('/skills')
async def skills(wb=Depends(service)):
    return wb.skills.list()


@router.post('/skills/refresh')
async def refresh_skills(wb=Depends(service)):
    return wb.skills.refresh()


@router.get('/reminders')
async def reminders(wb=Depends(service)):
    return wb.store.reminders()


@router.post('/reminders')
async def reminder(body: ReminderBody, wb=Depends(service)):
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(body.due.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError('Az időpont időzónaeltolást is tartalmazzon.')
        rid = wb.store.remind(body.text, dt.timestamp(), body.repeat_seconds)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {'id': rid}


@router.delete('/reminders/{rid}')
async def cancel_reminder(rid: str, wb=Depends(service)):
    return {'cancelled': wb.store.cancel_reminder(rid)}


@router.get('/events')
async def events(after: int = 0, wb=Depends(service)):
    return wb.store.notifications(after)


@router.post('/events/{through}/ack')
async def acknowledge(through: int, wb=Depends(service)):
    wb.store.acknowledge(through)
    return {'ok': True}


@router.get('/tasks')
async def tasks(wb=Depends(service)):
    return wb.store.tasks(wb.active['project_id'])


@router.post('/tasks')
async def task(body: TaskBody, wb=Depends(service)):
    return {'id': bad_value(wb.store.task_add, body.title, wb.active['project_id'], body.dependencies, body.owner)}


@router.patch('/tasks/{tid}')
async def update_task(tid: str, body: TaskUpdate, wb=Depends(service)):
    bad_value(wb.store.task_update, tid, wb.active['project_id'], body.status, body.result)
    return {'ok': True}


class VoiceBody(BaseModel):
    provider: str = Field(pattern='^(edge_tts|piper)$')
    voice: str = Field(default='hu-HU-TamasNeural', pattern='^hu-HU-(Tamas|Noemi)Neural$')


@router.get('/voice')
async def voice(request: Request, wb=Depends(service)):
    cfg = request.app.state.cfg
    return dict(provider=cfg.voice.provider, voice=cfg.voice.edge_voice,
                piper_available=cfg.abs_path(cfg.voice.piper_model).is_file(), online=cfg.voice.provider != 'piper')


@router.post('/voice')
async def set_voice(body: VoiceBody, request: Request, wb=Depends(service)):
    from ..extensions.settings import save_voice
    if wb.lock.locked():
        raise HTTPException(409, 'Futó feladat közben nem módosítható a hang.')
    async with wb.lock:
        return bad_value(save_voice, request.app.state.cfg, body.provider, body.voice)


@router.post('/pairing')
async def create_pairing(request: Request, wb=Depends(service)):
    return request.app.state.pairing.create()


@router.delete('/pairing')
async def revoke_pairing(request: Request, wb=Depends(service)):
    request.app.state.pairing.revoke()
    return {'ok': True}
