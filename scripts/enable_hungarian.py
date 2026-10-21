"""Merge Hungarian settings into an existing config without changing model/API settings."""
from __future__ import annotations
import argparse
import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
import yaml

VOICE_SETTINGS = {
    "language": "hu-HU", "stt_language": "hu",
    "stt_initial_prompt": "Magyar beszéd. Jarvis, nyisd meg a fájlt, keress az interneten, készíts képet.",
    "provider": "edge_tts", "piper_enabled": False,
    "piper_model": "data/voices/hu_HU-imre-medium.onnx", "piper_speaker": 0,
    "piper_length_scale": 1.0, "piper_noise_scale": 0.55,
    "piper_noise_w_scale": 0.72, "piper_volume": 1.0,
    "edge_voice": "hu-HU-TamasNeural", "edge_rate": "+0%", "edge_pitch": "+0Hz",
    "riva_enabled": False,
}

def enable(config_path: Path) -> Path:
    original = config_path.read_bytes()
    raw = yaml.safe_load(original.decode("utf-8-sig")) or {}
    if not isinstance(raw, dict): raise ValueError("A config.yaml nem YAML-objektum.")
    for section in ("A", "voice"):
        if section in raw and not isinstance(raw[section], dict):
            raise ValueError(f"Hibás konfigurációs szakasz: {section}")
    raw.setdefault("A", {})["language"] = "hu"
    raw.setdefault("voice", {}).update(VOICE_SETTINGS)
    backup = config_path.with_name("config.before-hu-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".yaml")
    backup.write_bytes(original)
    fd, temporary = tempfile.mkstemp(prefix=".config-hu-", suffix=".yaml", dir=config_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            yaml.safe_dump(raw, stream, allow_unicode=True, sort_keys=False)
        os.replace(temporary, config_path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return backup

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("config",type=Path)
    args=parser.parse_args()
    backup=enable(args.config)
    print("Magyar nyelv és hang beállítva. A korábbi konfiguráció biztonsági másolata elkészült.")
