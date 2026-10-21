"""Explicitly configured application CLIs, dev servers and language servers."""
from pathlib import Path
from ..core.permissions import Permission
from .base import PluginInfo, Tool
from .workbench_tools import schema, S


def register(registry):
    wb = registry.services.get('workbench')
    if not wb:
        return
    def add(name, desc, props, required, handler, permission=Permission.SAFE):
        registry.add(Tool(name, desc, schema(props, required), handler, permission, plugin='developer_tools'))

    def catalog():
        return {'applications': [{'name': k, 'description': v.description} for k, v in registry.cfg.ng.applications.items()],
                'dev_servers': list(registry.cfg.ng.dev_servers), 'language_servers': list(registry.cfg.ng.language_servers)}

    def configured(group, name):
        if name not in group:
            raise ValueError('Nincs ilyen konfigurált adapter.')
        cfg = group[name]
        root = Path(cfg.cwd).expanduser().resolve() if cfg.cwd else wb.root
        if not root.is_dir():
            raise ValueError('A munkamappa nem létezik.')
        return cfg, root

    async def application_run(name, args=None):
        cfg, root = configured(registry.cfg.ng.applications, name)
        return await wb.processes.run(cfg.command, cfg.args + (args or []), str(root), cfg.timeout_seconds)

    async def dev_start(name):
        cfg, root = configured(registry.cfg.ng.dev_servers, name)
        return await wb.processes.start('dev:'+name, cfg.command, cfg.args, str(root))

    async def lsp_query(server, operation, path, language='python', line=0, character=0):
        from ..extensions.lsp import LSPClient
        cfg, root = configured(registry.cfg.ng.language_servers, server)
        key = (server, str(root))
        client = wb.language_servers.get(key)
        if client is None:
            client = wb.language_servers[key] = LSPClient(cfg.command, cfg.args, root)
        return await client.query(operation, path, language, line, character)

    add('application_adapters', 'Konfigurált CLI alkalmazásadapterek, fejlesztői és nyelvi szerverek.', {}, (), catalog)
    add('application_run', 'Konfigurált alkalmazás CLI-jének futtatása argumentumlistával, shell nélkül. Az argumentumok fájlokat módosíthatnak.',
        {'name': S, 'args': {'type': 'array', 'items': S}}, ('name',), application_run, Permission.CAUTION)
    add('dev_server_start', 'Konfigurált fejlesztői szerver indítása; a Jarvis felügyeli és leállításkor bezárja.', {'name': S}, ('name',), dev_start, Permission.CAUTION)
    add('dev_servers', 'Felügyelt folyamatok és korlátozott naplók.', {}, (), wb.processes.status)
    add('dev_server_stop', 'A Jarvis által indított fejlesztői szerver folyamatfájának leállítása.', {'name': S}, ('name',), lambda name: wb.processes.stop('dev:'+name), Permission.CAUTION)
    add('lsp_query', 'Konfigurált helyi nyelvi szerver: szimbólum, definíció, hivatkozás vagy hover. A sor és karakter nullától indul, UTF-16 egységekben.',
        {'server': S, 'operation': {'type': 'string', 'enum': ['symbols', 'definition', 'references', 'hover']}, 'path': S, 'language': S,
         'line': {'type': 'integer', 'minimum': 0}, 'character': {'type': 'integer', 'minimum': 0}}, ('server', 'operation', 'path'), lsp_query, Permission.CAUTION)
    registry.register_plugin(PluginInfo(name='developer_tools', description='Konfigurálható alkalmazás-, fejlesztői szerver- és LSP-adapterek.'))
