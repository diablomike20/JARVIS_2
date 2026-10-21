"""J2 tools for the adapted NG workbench. All mutations use J2 permissions."""
from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from ..core.permissions import Permission
from .base import PluginInfo, Tool


def schema(properties=None, required=()):
    return {'type': 'object', 'properties': properties or {}, 'required': list(required), 'additionalProperties': False}


S = {'type': 'string'}


def register(registry):
    wb = registry.services.get('workbench')
    if wb is None:
        return
    store = wb.store

    def add(name, description, properties, required, handler, permission=Permission.SAFE):
        registry.add(Tool(name=name, description=description, parameters=schema(properties, required), handler=handler, permission=permission, plugin='workbench_tools'))

    add('projects_list', 'Mentett projektek listázása.', {}, (), store.projects)
    add('project_create', 'Projekt regisztrálása létező munkamappával.', {'name': S, 'path': S}, ('name', 'path'), store.create_project, Permission.CAUTION)
    add('sessions_list', 'Mentett munkamenetek listázása. Váltás a felületen vagy /session paranccsal.', {}, (), store.sessions)
    add('session_create', 'Új munkamenet létrehozása az aktív vagy megadott projektben.', {'name': S, 'project_id': S}, ('name',),
        lambda name, project_id='': store.create_session(name, project_id or wb.active['project_id']), Permission.CAUTION)
    add('profile_list', 'Érvényes globális és aktuális projektprofil megtekintése.', {}, (), lambda: store.profiles(wb.active['project_id']))

    def profile_set(key, value, source, scope='project', confidence=1.0):
        if scope not in {'project', 'global'}:
            raise ValueError('scope: project vagy global')
        store.set_profile(key, value, source, '' if scope == 'global' else wb.active['project_id'], confidence)
        return {'saved': key}

    add('profile_set', 'Profiladat mentése forrással. Csak a felhasználó által közölt vagy igazolt tényt ments.',
        {'key': S, 'value': S, 'source': S, 'scope': {'type': 'string', 'enum': ['project', 'global']}, 'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1}},
        ('key', 'value', 'source'), profile_set, Permission.CAUTION)
    add('profile_delete', 'Profilbejegyzés végleges törlése.', {'key': S, 'global_scope': {'type': 'boolean'}}, ('key',),
        lambda key, global_scope=False: {'deleted': store.delete_profile(key, '' if global_scope else wb.active['project_id'])}, Permission.CAUTION)
    add('skills_list', 'Elérhető SKILL.md képességcsomagok listázása.', {}, (), wb.skills.list)
    add('skill_read', 'Képességcsomag útmutatójának explicit betöltése.', {'name': S}, ('name',), wb.skills.read)
    add('skills_refresh', 'Helyi képességcsomagok újraolvasása; nem futtat kódot.', {}, (), wb.skills.refresh)
    add('tool_search', 'Regisztrált eszközök keresése és teljes paraméterséma lekérése.', {'query': S}, ('query',),
        lambda query: [dict(name=t.name, description=t.description, parameters=t.parameters, permission=t.permission.value)
                       for t in registry.all_tools() if query.casefold() in (t.name + ' ' + t.description).casefold()][:20])

    def reminder_create(text, due, repeat_seconds=0):
        dt = datetime.fromisoformat(due.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError('Időzóna szükséges, például 2026-10-22T09:00:00+02:00.')
        rid = store.remind(text, dt.timestamp(), repeat_seconds)
        return {'id': rid, 'due': dt.isoformat(), 'repeat_seconds': repeat_seconds, 'note': 'A Jarvis futása közben jelez; leállítás után a következő indításkor pótolja.'}

    add('reminder_create', 'Tartós emlékeztető létrehozása ISO időponttal és kötelező időzónaeltolással. Ismétlés eltelt másodpercben.',
        {'text': S, 'due': S, 'repeat_seconds': {'type': 'number', 'minimum': 0}}, ('text', 'due'), reminder_create, Permission.CAUTION)
    add('reminders_list', 'Tartós emlékeztetők listázása.', {}, (), store.reminders)
    add('reminder_cancel', 'Emlékeztető kikapcsolása.', {'id': S}, ('id',), lambda id: {'cancelled': store.cancel_reminder(id)}, Permission.CAUTION)
    add('tasks_list', 'Az aktív projekt függőséges feladatlistája.', {}, (), lambda: store.tasks(wb.active['project_id']))
    add('task_add', 'Feladat felvétele meglévő feladatazonosítókra hivatkozó függőségekkel.',
        {'title': S, 'dependencies': {'type': 'array', 'items': S}, 'owner': S}, ('title',),
        lambda title, dependencies=None, owner='': {'id': store.task_add(title, wb.active['project_id'], dependencies, owner)}, Permission.CAUTION)
    add('task_update', 'Feladatállapot és eredmény rögzítése. Függő feladatok előtt nem indítható.',
        {'id': S, 'status': {'type': 'string', 'enum': ['pending', 'running', 'done', 'failed', 'cancelled']}, 'result': S}, ('id', 'status'),
        lambda id, status, result='': store.task_update(id, wb.active['project_id'], status, result) or {'updated': id}, Permission.CAUTION)
    add('checkpoint_create', 'Explicit felsorolt projektfájlok mentése; nem teljes gépmentés. Titkok, symlinkek kizárva.',
        {'paths': {'type': 'array', 'items': S, 'minItems': 1, 'maxItems': 100}, 'label': S}, ('paths',),
        lambda paths, label='': wb.checkpoints.capture(wb.root, paths, label), Permission.CAUTION)
    add('checkpoints_list', 'Az aktív projekt fájlmentéseinek listája.', {}, (), lambda: wb.checkpoints.list(wb.root))
    add('checkpoint_preview', 'Visszaállítás előnézete; felsorolja a felülírandó fájlokat és visszaadja a szükséges tokent.', {'id': S}, ('id',),
        lambda id: wb.checkpoints.preview(id, wb.root))
    add('checkpoint_restore', 'Fájlok visszaállítása az előnézet tokenjével; előtte újabb mentést készít.', {'id': S, 'token': S}, ('id', 'token'),
        lambda id, token: wb.checkpoints.restore(id, wb.root, token), Permission.DANGEROUS)
    add('workbench_status', 'Projekt, képességek, MCP és függőségek állapota; titkok nélkül.', {}, (), lambda: wb.diagnostics(registry))
    add('team_messages', 'Egy agentcsapat tartós belső üzenetei.', {'team': S}, ('team',), store.messages)
    add('daily_briefing', 'Nyitott projektfeladatok, emlékeztetők és konfigurált helyi ICS-naptár összefoglalója.', {}, (), wb.briefing)
    from ..extensions.sources import email_headers, calendar_events
    def mail_headers(account, limit=20):
        if account not in registry.cfg.ng.imap_accounts:
            raise ValueError('Ismeretlen IMAP-fiók.')
        return email_headers(registry.cfg.ng.imap_accounts[account], limit=limit)
    add('mail_headers', 'Konfigurált IMAP-fiók friss levélfejlécei; nem jelöli olvasottnak és nem küld levelet.',
        {'account': S, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50}}, ('account',), mail_headers)
    add('calendar_upcoming', 'Konfigurált helyi ICS-naptár következő eseményei, ismétlődésekkel.', {'days': {'type': 'integer', 'minimum': 1, 'maximum': 90}}, (),
        lambda days=7: calendar_events([registry.cfg.abs_path(p) for p in registry.cfg.ng.calendar_files], registry.cfg.ng.timezone, days))
    from ..extensions.team import run_team
    add('team_run', 'Saját kontextussal dolgozó agentcsapat indítása. Függőségek névvel. Alapból olvasási eszközök; további eszközök csak explicit tools listából, a rendes jogosultságokkal. Nem telepít vagy vált modellt.',
        {'tasks': {'type': 'array', 'minItems': 1, 'maxItems': registry.cfg.ng.max_agents, 'items': schema(
            {'label': S, 'goal': S, 'role': S, 'depends_on': {'type': 'array', 'items': S}, 'tools': {'type': 'array', 'items': S}}, ('label', 'goal'))}},
        ('tasks',), lambda tasks: run_team(registry, tasks), Permission.CAUTION)
    registry.register_plugin(PluginInfo(name='workbench_tools', description='NG projektmemória, képességek, emlékeztetők és visszaállítás.', permissions_needed=[Permission.SAFE, Permission.CAUTION, Permission.DANGEROUS]))
