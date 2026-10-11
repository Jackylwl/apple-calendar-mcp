"""Launcher regression tests: synthetic executables, no EventKit or calendar access."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='calendar-launcher-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'plugin with spaces'
        (self.root / 'scripts').mkdir(parents=True)
        shutil.copy2(ROOT / 'scripts/start.sh', self.root / 'scripts/start.sh')
        self.state = Path(self.temp.name) / 'private state'
        self.state.mkdir()
        self.config = self.state / 'allowed-calendars.json'
        self.config.write_text('["fixture"]')
        self.env = {**os.environ, 'LOCAL_APPLE_CALENDAR_HOME': str(self.state)}

    def setup_script(self, contents):
        p = self.root / 'scripts/setup.sh'
        p.write_text('#!/bin/sh\nset -eu\n' + contents)
        p.chmod(0o755)

    def launch(self):
        return subprocess.run([str(self.root / 'scripts/start.sh')], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_first_start_stdout_and_reuse(self):
        self.setup_script('''printf 'build log\\n'
printf x >> "$LOCAL_APPLE_CALENDAR_HOME/build-count"
printf '#!/bin/sh\\nprintf protocol-only\\n' > "$LOCAL_APPLE_CALENDAR_HOME/calendar-mcp"
chmod +x "$LOCAL_APPLE_CALENDAR_HOME/calendar-mcp"
''')
        for _ in range(2):
            result = self.launch()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'protocol-only')
        self.assertEqual((self.state / 'build-count').read_text(), 'x')
        self.assertEqual(self.config.read_text(), '["fixture"]')
        self.assertFalse((self.state / '.first-build-lock').exists())

    def test_failed_build_releases_lock_and_can_retry(self):
        self.setup_script('echo build-failed\nexit 7\n')
        for _ in range(2):
            result = self.launch()
            self.assertEqual(result.returncode, 7)
            self.assertEqual(result.stdout, '')
            self.assertIn('build-failed', result.stderr)
            self.assertFalse((self.state / '.first-build-lock').exists())
        self.assertEqual(self.config.read_text(), '["fixture"]')

if __name__ == '__main__':
    unittest.main(verbosity=2)
