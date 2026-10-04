from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/ruhang365-router/scripts'))
import community_catalog as catalog

spec = importlib.util.spec_from_file_location('snapshot_updater', ROOT / 'scripts/update_catalog_snapshot.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


def payload(version='fixture', schema='1.1.0'):
    return {'schemaVersion': schema, 'catalogVersion': version, 'items': [],
            'contentDigest': '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'}


class Response(io.BytesIO):
    headers = {}
    status = 200

    def __init__(self, data):
        super().__init__(json.dumps(data).encode())


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'snapshot.json'
        self.path.write_text(json.dumps(payload()))

    def run_update(self, opener, *args):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['update', '--output', str(self.path), *args]), \
             patch.object(updater.urllib.request, 'urlopen', side_effect=opener), \
             patch('time.sleep') as sleep, contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = updater.main()
        return code, output.getvalue() + errors.getvalue(), sleep

    def test_two_updaters_cannot_write_between_fingerprint_check_and_replace(self):
        # A pauses after reading the final fingerprint. Without a writer lock,
        # B succeeds here and A silently overwrites B with its older download.
        script = '''
import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('snapshot_updater',sys.argv[1])
updater=importlib.util.module_from_spec(spec); spec.loader.exec_module(updater)
path=Path(sys.argv[2]); state=updater.file_state(path); read_state=updater.file_state
def pause_after_check(path):
    result=read_state(path); print('checked',flush=True); sys.stdin.readline(); return result
updater.file_state=pause_after_check
updater.replace_snapshot(path,json.loads(sys.argv[3]),state)
'''
        initial = updater.file_state(self.path)
        worker = subprocess.Popen([sys.executable, '-c', script, str(ROOT / 'scripts/update_catalog_snapshot.py'),
                                   str(self.path), json.dumps(payload('older'))],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(worker.stdout.readline().strip(), 'checked')
            with self.assertRaisesRegex(ValueError, 'another snapshot updater'):
                updater.replace_snapshot(self.path, payload('newer'), initial)
        finally:
            if worker.poll() is None:
                worker.stdin.write('\n'); worker.stdin.flush()
            stdout, errors = worker.communicate(timeout=10)
            self.assertEqual(worker.returncode, 0, stdout + errors)
        self.assertEqual(json.loads(self.path.read_text())['catalogVersion'], 'older')
        # An explicit fresh reconciliation can then install B; no stale input
        # was reported successful, and the committed newer file never regresses.
        updater.replace_snapshot(self.path, payload('newer'), updater.file_state(self.path))
        self.assertEqual(json.loads(self.path.read_text())['catalogVersion'], 'newer')

    def test_writer_lock_never_follows_a_symlink_or_changes_its_target(self):
        victim = Path(self.temp.name) / 'unrelated.txt'
        victim.write_text('preserve unrelated data')
        (self.path.parent / f'.{self.path.name}.snapshot.lock').symlink_to(victim)
        before = self.path.read_bytes()
        with self.assertRaises((ValueError, OSError)):
            updater.replace_snapshot(self.path, payload('updated'), updater.file_state(self.path))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(victim.read_text(), 'preserve unrelated data')

    def test_busy_writer_is_actionable_and_preserves_snapshot_without_retry(self):
        before = self.path.read_bytes()
        with updater.snapshot_write_lock(self.path):
            code, log, sleep = self.run_update(lambda *a, **k: Response(payload('newer')))
        self.assertEqual(code, 1)
        self.assertIn('concurrent_update', log)
        self.assertEqual(sleep.call_count, 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_304_confirms_validated_snapshot_with_etag(self):
        def opener(request, **kwargs):
            expected = '"' + hashlib.sha256(('fixture:' + payload()['contentDigest']).encode()).hexdigest() + '"'
            self.assertEqual(request.get_header('If-none-match'), expected)
            raise urllib.error.HTTPError(request.full_url, 304, 'not modified', {}, None)
        result = catalog.resolve_catalog('https://example.org', snapshot_path=self.path, opener=opener)
        self.assertEqual((result['source'], result['warning'], result['catalog']), ('online', None, payload()))

    def test_mismatched_response_304_etag_uses_stable_fallback(self):
        for error_response in (False, True):
            with self.subTest(error_response=error_response):
                def opener(request, **kwargs):
                    if error_response:
                        raise urllib.error.HTTPError(request.full_url, 304, '', {'ETag': '"different-release"'}, None)
                    response = Response({})
                    response.status = 304
                    response.headers = {'ETag': '"different-release"'}
                    return response
                result = catalog.resolve_catalog('https://example.org', snapshot_path=self.path, opener=opener)
                self.assertEqual(result['source'], 'offline_fallback')
                self.assertIsNotNone(result['warning'])
                self.assertEqual(result['catalog'], payload())
                before = self.path.stat(), self.path.read_bytes()
                code, log, sleep = self.run_update(opener)
                self.assertEqual(code, 1, log)
                self.assertIn('protocol_error', log)
                self.assertEqual(sleep.call_count, 0)
                self.assertEqual((self.path.stat(), self.path.read_bytes()), before)

    def test_matching_or_absent_304_etag_confirms_snapshot(self):
        expected = '"b02ebfe37f180cc5ba21cca757ede777095bb1ee11b742e8c55141993affb6e5"'
        for error_response in (False, True):
            for etag in (None, expected, 'W/' + expected):
                with self.subTest(error_response=error_response, etag=etag):
                    def opener(request, **kwargs):
                        headers = {} if etag is None else {'ETag': etag}
                        if error_response:
                            raise urllib.error.HTTPError(request.full_url, 304, '', headers, None)
                        response = Response({})
                        response.status = 304
                        response.headers = headers
                        return response
                    result = catalog.resolve_catalog('https://example.org', snapshot_path=self.path, opener=opener)
                    self.assertEqual((result['source'], result['warning']), ('online', None))
                    code, log, _ = self.run_update(opener)
                    self.assertEqual(code, 0, log)
                    self.assertIn('http_status=304', log)

    def test_check_validates_without_creating_missing_output_parent(self):
        self.path = Path(self.temp.name) / 'missing' / 'snapshot.json'
        code, log, _ = self.run_update(lambda *a, **k: Response(payload()), '--check')
        self.assertEqual(code, 0, log)
        self.assertFalse(self.path.parent.exists())

    def test_304_and_equal_200_preserve_file_metadata(self):
        for unchanged in (True, False):
            with self.subTest(unchanged=unchanged):
                before = self.path.stat()
                def opener(request, **kwargs):
                    if unchanged:
                        raise urllib.error.HTTPError(request.full_url, 304, '', {}, None)
                    return Response(payload())
                code, log, _ = self.run_update(opener)
                self.assertEqual(code, 0, log)
                after = self.path.stat()
                self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
                self.assertIn(f'http_status={304 if unchanged else 200}', log)

    def test_retry_exhaustion_is_bounded_and_preserves_original(self):
        before = self.path.read_bytes()
        code, log, sleep = self.run_update(lambda *a, **k: (_ for _ in ()).throw(TimeoutError('SECRET')))
        self.assertEqual(code, 1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIn('network_timeout', log)
        self.assertIn('attempts=3', log)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_check_existing_file_keeps_bytes_and_metadata(self):
        before = self.path.stat(), self.path.read_bytes()
        code, log, _ = self.run_update(lambda *a, **k: Response(payload('updated')), '--check')
        self.assertEqual(code, 0, log)
        self.assertEqual((self.path.stat(), self.path.read_bytes()), before)

    def test_invalid_snapshot_cannot_confirm_304(self):
        self.path.write_text('{"invalid": true}')
        def opener(request, **kwargs):
            self.assertIsNone(request.get_header('If-none-match'))
            raise urllib.error.HTTPError(request.full_url, 304, '', {}, None)
        code, log, _ = self.run_update(opener)
        self.assertEqual(code, 1, log)
        self.assertEqual(self.path.read_text(), '{"invalid": true}')

    def test_default_destination_follows_download_schema(self):
        for schema in ('1.0.0', '1.1.0'):
            with self.subTest(schema=schema), patch.object(updater, 'DEFAULT_CATALOG_PATH', Path(self.temp.name) / 'catalog.json'), \
                 patch.object(updater, 'FULL_CATALOG_PATH', Path(self.temp.name) / 'full.json'), \
                 patch.object(sys, 'argv', ['update']), \
                 patch.object(updater.urllib.request, 'urlopen', return_value=Response(payload(schema=schema))), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(updater.main(), 0)
                destination = updater.FULL_CATALOG_PATH if schema == '1.1.0' else updater.DEFAULT_CATALOG_PATH
                self.assertEqual(json.loads(destination.read_text())['schemaVersion'], schema)

    def test_transient_errors_retry_then_replace_valid_catalog(self):
        failures = [urllib.error.HTTPError('https://example.org', 503, 'SECRET', {}, None), TimeoutError('SECRET')]
        def opener(*args, **kwargs):
            if failures:
                raise failures.pop(0)
            return Response(payload('updated'))
        code, log, sleep = self.run_update(opener)
        self.assertEqual(code, 0, log)
        self.assertEqual(json.loads(self.path.read_text())['catalogVersion'], 'updated')
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
        self.assertIn('attempts=3', log)
        self.assertNotIn('SECRET', log)

    def test_failure_categories_do_not_retry_or_destroy_snapshot(self):
        bad = payload(); bad['contentDigest'] = 'bad'
        for failure, category in [(urllib.error.HTTPError('https://example.org?SECRET', 429, 'SECRET', {}, None), 'http_status=429'),
                                  (Response(bad), 'digest'), (Response({'schemaVersion': '9'}), 'protocol')]:
            with self.subTest(category=category):
                before = self.path.read_bytes()
                def opener(*args, **kwargs):
                    if isinstance(failure, Exception):
                        raise failure
                    return failure
                code, log, sleep = self.run_update(opener)
                self.assertEqual(code, 1)
                self.assertIn(category, log)
                self.assertNotIn('SECRET', log)
                self.assertEqual(self.path.read_bytes(), before)
                self.assertEqual(sleep.call_count, 0)

    def test_download_cannot_overwrite_concurrent_edit(self):
        def opener(*args, **kwargs):
            self.path.write_text('concurrent edit')
            return Response(payload('updated'))
        code, log, _ = self.run_update(opener)
        self.assertEqual(code, 1, log)
        self.assertEqual(self.path.read_text(), 'concurrent edit')

    def test_edit_during_temp_file_flush_is_preserved_and_temp_removed(self):
        with patch.object(updater.os, 'fsync', side_effect=lambda fd: self.path.write_text('late edit')):
            code, log, _ = self.run_update(lambda *a, **k: Response(payload('updated')))
        self.assertEqual(code, 1, log)
        self.assertEqual(self.path.read_text(), 'late edit')
        self.assertEqual({path.name for path in Path(self.temp.name).iterdir()},
                         {self.path.name, f'.{self.path.name}.snapshot.lock'})

    def test_atomic_replace_failure_preserves_original_and_removes_temp(self):
        before = self.path.read_bytes()
        with patch.object(updater.os, 'replace', side_effect=OSError('SECRET')):
            code, log, _ = self.run_update(lambda *a, **k: Response(payload('updated')))
        self.assertEqual(code, 1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual({path.name for path in Path(self.temp.name).iterdir()},
                         {self.path.name, f'.{self.path.name}.snapshot.lock'})
        self.assertNotIn('SECRET', log)

    def test_symlink_and_directory_are_never_overwritten(self):
        original = self.path
        for kind in ('symlink', 'directory'):
            self.path = Path(self.temp.name) / kind
            if kind == 'symlink':
                self.path.symlink_to(original)
            else:
                self.path.mkdir()
            code, log, _ = self.run_update(lambda *a, **k: Response(payload('updated')))
            self.assertEqual(code, 1, log)
            self.assertEqual(json.loads(original.read_text()), payload())
            self.assertTrue(self.path.is_symlink() if kind == 'symlink' else self.path.is_dir())


if __name__ == '__main__':
    unittest.main()
