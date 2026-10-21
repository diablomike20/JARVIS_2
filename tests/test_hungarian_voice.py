"""Exercise config -> HTTP contracts without downloading STT models or calling a provider."""
import io
import tempfile
import sys
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jarvis.config import Config
from jarvis.server import routes


class HungarianVoiceTests(unittest.TestCase):
    def client(self, **voice):
        cfg = Config(voice=voice)
        app = FastAPI()
        app.state.cfg = cfg
        app.state.orchestrator = None
        app.state.memory = None
        app.state.registry = SimpleNamespace(plugins=lambda: [], all_tools=lambda: [])
        app.state.agents = SimpleNamespace(names=lambda: [])
        app.include_router(routes.router, prefix="/api")
        return TestClient(app), cfg

    def test_saved_edge_voice_is_used_when_request_omits_voice(self):
        calls = []
        class FakeTTS:
            def __init__(self, text, **kwargs): calls.append((text, kwargs))
            async def stream(self): yield {"type": "audio", "data": b"fake-mp3"}
        client, _ = self.client(provider="edge_tts", edge_voice="hu-HU-TamasNeural")
        with client, patch("edge_tts.Communicate", FakeTTS):
            response = client.post("/api/tts", json={"text": "Szia, magyarul beszélek."})
        self.assertEqual(response.content, b"fake-mp3")
        self.assertEqual(calls[0][1]["voice"], "hu-HU-TamasNeural")
        self.assertEqual(response.headers["Content-Language"], "hu-HU")

    def test_piper_endpoint_returns_wav_and_hungarian_metadata(self):
        client, _ = self.client(provider="piper")
        wav = io.BytesIO()
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\0\0" * 220)
        with client, patch.object(routes, "_synthesize_with_piper", return_value=wav.getvalue()) as synth:
            response = client.post("/api/tts", json={"text": "Árvíztűrő tükörfúrógép."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-JARVIS-TTS"], "piper")
        self.assertEqual(response.headers["Content-Language"], "hu-HU")
        self.assertEqual(synth.call_args.args[0], "Árvíztűrő tükörfúrógép.")

    def test_whisper_receives_hungarian_language_and_prompt(self):
        calls = []
        class FakeWhisper:
            def transcribe(self, path, **kwargs):
                calls.append(kwargs)
                return iter([SimpleNamespace(text="Szia Jarvis, nyisd meg a fájlt.")]), None
        client, _ = self.client(stt_language="hu", stt_initial_prompt="Magyar beszéd.")
        with client, patch.object(routes, "_get_whisper_model", return_value=FakeWhisper()):
            response = client.post("/api/stt", files={"audio": ("speech.webm", b"mock-audio", "audio/webm")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls[0]["language"], "hu")
        self.assertEqual(calls[0]["initial_prompt"], "Magyar beszéd.")
        self.assertIn("nyisd meg", response.json()["text"])

    def test_empty_audio_and_empty_tts_report_error(self):
        client, _ = self.client()
        with client:
            self.assertEqual(client.post("/api/stt", files={"audio": ("empty.webm", b"")}).status_code, 400)
            self.assertEqual(client.post("/api/tts", json={"text": " "}).status_code, 400)

    def test_status_requires_model_and_sidecar(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder)/"hu_HU-imre-medium.onnx"
            model.write_bytes(b"not-loaded-by-status")
            client, _ = self.client(provider="piper", piper_model=str(model))
            package = ModuleType("piper")
            package.__path__ = []
            with client, patch.dict(sys.modules, {"piper": package, "piper.voice": ModuleType("piper.voice")}):
                self.assertNotEqual(client.get("/api/tts/status").json()["provider"], "piper")
                Path(str(model)+".json").write_text("{}")
                status = client.get("/api/tts/status").json()
                self.assertEqual(status["provider"], "piper")
                self.assertEqual(status["lang"], "hu-HU")


if __name__ == "__main__": unittest.main()
