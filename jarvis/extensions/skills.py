"""Read-only SKILL.md discovery with proper YAML, bounded files and HU triggers."""
from __future__ import annotations
import re
import unicodedata
from pathlib import Path
import yaml


def normalized(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


class SkillCatalog:
    def __init__(self, roots: list[Path]):
        self.roots = roots
        self.items: dict[str, dict] = {}
        self.errors: list[dict] = []
        self.refresh()

    def refresh(self) -> list[dict]:
        self.items = {}
        self.errors = []
        for root in self.roots:
            root = root.expanduser().resolve()
            if not root.is_dir():
                continue
            for path in sorted(root.glob('*/SKILL.md'))[:100]:
                try:
                    if not path.resolve().is_relative_to(root) or path.stat().st_size > 64000:
                        raise ValueError('Külső hivatkozás vagy túl nagy fájl.')
                    text = path.read_text(encoding='utf-8-sig')
                    m = re.match(r'\A---\s*\n(.*?)\n---\s*\n(.*)\Z', text, re.S)
                    if not m:
                        raise ValueError('Hiányzó YAML fejléc.')
                    meta = yaml.safe_load(m[1])
                    if not isinstance(meta, dict):
                        raise ValueError('Hibás fejléc.')
                    name = str(meta.get('name') or path.parent.name)
                    if not re.fullmatch(r'[\w.-]{1,64}', name):
                        raise ValueError('Hibás képességnév.')
                    if name in self.items:
                        raise ValueError('Ismétlődő képességnév.')
                    triggers = meta.get('triggers', [])
                    if isinstance(triggers, str):
                        triggers = [x.strip() for x in triggers.split(',') if x.strip()]
                    if not isinstance(triggers, list) or not all(isinstance(t, str) for t in triggers):
                        raise ValueError('A triggers szövegek listája legyen.')
                    self.items[name] = dict(name=name, description=str(meta.get('description', ''))[:1000], triggers=triggers, body=m[2], path=str(path))
                except (OSError, ValueError, yaml.YAMLError) as exc:
                    self.errors.append({'path': str(path), 'error': str(exc)})
        return self.list()

    def list(self) -> list[dict]:
        return [{k: v for k, v in item.items() if k != 'body'} for item in self.items.values()]

    def read(self, name: str) -> dict:
        if name not in self.items:
            raise ValueError('Ismeretlen képesség.')
        return dict(self.items[name])

    def context(self, text: str, budget: int = 12000) -> str:
        n = normalized(text)
        parts = []
        for item in self.items.values():
            explicit = f"${item['name']}".casefold() in text.casefold()
            if explicit or any(normalized(t) in n for t in item['triggers'] if t):
                part = f"\nKépesség: {item['name']}\n{item['body']}"
                if len(part) <= budget:
                    parts.append(part)
                    budget -= len(part)
        return '\n'.join(parts)
