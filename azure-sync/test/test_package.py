"""Regression for Flex Consumption rejecting umask-077 ZIP entries with mode 600."""
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class PackageTests(TestCase):
    def test_restricted_sources_produce_readable_zip_without_secrets(self):
        builder = load('package')
        with TemporaryDirectory() as directory:
            root = Path(directory)
            old = os.umask(0o077)
            try:
                (root / 'src').mkdir()
                for name in ['host.json', 'package.json', 'package-lock.json', 'src/functions.js', 'src/service.js', 'src/store.js', 'settings.json', 'local.settings.json']:
                    (root / name).write_text(name)
                self.assertEqual((root / 'host.json').stat().st_mode & 0o777, 0o600)
                builder.package(root, root / 'deploy.zip')
                self.assertEqual((root / 'settings.json').stat().st_mode & 0o777, 0o600)
            finally:
                os.umask(old)
            with ZipFile(root / 'deploy.zip') as archive:
                self.assertNotIn('settings.json', archive.namelist())
                self.assertNotIn('local.settings.json', archive.namelist())
                for entry in archive.infolist():
                    self.assertEqual(entry.create_system, 3)
                    self.assertEqual((entry.external_attr >> 16) & 0o777, 0o755 if entry.is_dir() else 0o644)
                    if not entry.is_dir(): self.assertEqual(archive.read(entry).decode(), entry.filename)

    def test_deployment_is_not_reported_ready_on_http_503(self):
        health = load('check-health')
        from urllib.error import HTTPError
        with patch.object(health, 'urlopen', side_effect=HTTPError('https://test.azurewebsites.net',503,'not running',{},None)):
            self.assertFalse(health.check('test.azurewebsites.net', attempts=1))
        with self.assertRaises(ValueError): health.check('')

    def test_ready_requires_actual_healthy_api_response(self):
        health = load('check-health')
        from io import BytesIO
        class Response(BytesIO):
            status = 200
        for data, expected in [({'ready':False},False),({'ready':True},False),({'ready':True,'service':'flash-cards-sync'},True)]:
            with patch.object(health,'urlopen',return_value=Response(json.dumps(data).encode())):
                self.assertEqual(health.check('test.azurewebsites.net', attempts=1), expected)

if __name__ == '__main__': main()
