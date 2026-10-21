"""Atomic, backed-up voice configuration edits; never rewrites credentials."""
import os
import tempfile
from datetime import datetime
from pathlib import Path
import yaml


def save_voice(cfg, provider: str, voice: str):
    if provider == 'piper':
        model = cfg.abs_path(cfg.voice.piper_model)
        if not model.is_file() or not Path(str(model) + '.json').is_file():
            raise ValueError('Hiányzik a Piper hangmodell vagy a JSON kísérőfájl.')
    path = cfg.config_source or cfg.project_root / 'config.yaml'
    path = Path(path)
    original = path.read_bytes()
    raw = yaml.safe_load(original.decode('utf-8-sig')) or {}
    if not isinstance(raw, dict) or not isinstance(raw.get('voice', {}), dict):
        raise ValueError('Hibás konfiguráció.')
    values = dict(provider=provider, edge_voice=voice, piper_enabled=provider == 'piper', edge_rate='+0%', edge_pitch='+0Hz')
    raw.setdefault('voice', {}).update(values)
    backup = cfg.abs_path('data/backups')
    backup.mkdir(parents=True, exist_ok=True)
    (backup / f'config-voice-{datetime.now():%Y%m%d-%H%M%S-%f}.yaml').write_bytes(original)
    fd, tmp = tempfile.mkstemp(prefix='.voice-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)
        if path.read_bytes() != original:
            raise ValueError('Másik folyamat módosította a konfigurációt; próbáld újra.')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    for key, value in values.items():
        setattr(cfg.voice, key, value)
    return {'ok': True, **values}
