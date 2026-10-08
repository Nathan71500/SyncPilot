"""Regression for the actual Windows-1252 emitter / UTF-8 collector failure."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'syncpilot/skills'


class EncodingTests(unittest.TestCase):
    def test_every_cli_emits_strict_utf8_with_legacy_windows_environment(self):
        # Accents reproduce the incident; the emoji also cannot be emitted as cp1252.
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / 'réception-🧩.json')
            commands = {
                'syncpilot-codex/scripts/project_sync.py': ['verify', '--input', missing, '--requirement', missing],
                'syncpilot-work/scripts/project_sync.py': ['verify', '--input', missing, '--requirement', missing],
                'syncpilot-decisions/scripts/decision_sync.py': ['align', '--contract', missing, '--ledger', missing, '--environment', 'codex'],
                'syncpilot-dc/scripts/syncpilot_transport.py': ['plan', '--journal', missing, '--discovery', missing],
                'syncpilot-dc/scripts/dc_transport.py': ['confirm', '--plan', missing, '--receipt', missing, '--observation', missing],
                'syncpilot-persistence/scripts/work_persistence.py': ['plan', '--journal', missing, '--observation', missing],
                'syncpilot-dc/scripts/syncpilot_flow.py': ['route', '--contract', missing, '--source', missing, '--candidates', missing, '--destination-environment', 'codex', '--kind', 'decisions'],
                'syncpilot-dc/scripts/syncpilot_codex_bridge.py': ['--request', missing, '--codex', missing],
            }
            environment = {**os.environ, 'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'cp1252:strict'}
            for script, arguments in commands.items():
                with self.subTest(script=script):
                    result = subprocess.run([sys.executable, str(ROOT / script), *arguments],
                                            capture_output=True, text=True, encoding='utf-8',
                                            errors='strict', env=environment, timeout=10)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    output = result.stdout or result.stderr
                    self.assertIn('réception-🧩.json', output)
                    self.assertNotIn('Traceback', output)
                    if result.stdout:
                        self.assertIn('error', json.loads(result.stdout))


if __name__ == '__main__':
    unittest.main()
