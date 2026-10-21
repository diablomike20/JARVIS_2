import importlib.util
from pathlib import Path
import tempfile
import unittest
import yaml

spec=importlib.util.spec_from_file_location("enable_hungarian",Path(__file__).parents[1]/"scripts/enable_hungarian.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ConfigMergeTests(unittest.TestCase):
    def test_model_and_custom_settings_survive_repeated_merge(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"config.yaml"
            original={"model":{"api_key":"local-test-only","endpoint":"http://example.invalid","model":"custom"},
                      "A":{"persona":"saját személyiség"},"voice":{"wake_word":"Szia Jarvis"},
                      "custom_plugin":{"enabled":True}}
            path.write_text(yaml.safe_dump(original),encoding="utf-8")
            backup=module.enable(path)
            self.assertEqual(yaml.safe_load(backup.read_text()),original)
            module.enable(path)
            actual=yaml.safe_load(path.read_text())
            self.assertEqual(actual["model"],original["model"])
            self.assertEqual(actual["A"]["persona"],original["A"]["persona"])
            self.assertEqual(actual["voice"]["wake_word"],"Szia Jarvis")
            self.assertEqual(actual["custom_plugin"],original["custom_plugin"])
            self.assertEqual(actual["voice"]["stt_language"],"hu")

    def test_invalid_yaml_does_not_overwrite_config(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"config.yaml";before="voice: [unterminated"
            path.write_text(before)
            with self.assertRaises(yaml.YAMLError): module.enable(path)
            self.assertEqual(path.read_text(),before)
