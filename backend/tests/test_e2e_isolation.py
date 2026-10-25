import os
from pathlib import Path
import subprocess
import sys
import unittest


class BrowserHarnessIsolationTests(unittest.TestCase):
    def test_entrypoint_refuses_missing_test_marker(self):
        environment = {**os.environ, 'E2E_TEST_MODE': ''}
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('e2e_server.py'))], env=environment, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires isolated test mode', result.stderr)

    def test_entrypoint_refuses_normal_database_before_connecting(self):
        environment = {**os.environ, 'E2E_TEST_MODE': 'isolated-e2e-only', 'DATABASE_URL': 'postgresql://test@invalid.example/appointments'}
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('e2e_server.py'))], env=environment, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('refuses non-test databases', result.stderr)

    def test_normal_app_has_no_test_login_or_expiry_routes(self):
        from main import app
        self.assertFalse(any(path.startswith('/__e2e/') for path in app.openapi()['paths']))
