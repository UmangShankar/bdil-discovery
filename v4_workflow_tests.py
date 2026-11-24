"""Accepted-default routing and non-destructive rollout regressions."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install_v4
import v4


class WorkflowTests(unittest.TestCase):
    def test_subcommands_route_only_to_v4(self):
        for command, module in [('discover', 'v4_local.py'), ('render', 'v4_handoff.py'), ('package', 'v4_package.py')]:
            with patch('v4.subprocess.call', return_value=0) as call:
                self.assertEqual(v4.main([command, '--help']), 0)
                self.assertEqual(Path(call.call_args.args[0][1]).name, module)

    def test_legacy_upload_is_rejected_before_preparation(self):
        with patch('v4.prepare') as prepare, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                v4.legacy_main(['https://youtube.com/watch?v=example', '--upload'])
            prepare.assert_not_called()

    def test_local_prepare_records_v4_and_zero_candidate_editorial_path(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            video = root / 'source.mp4'
            video.write_bytes(b'original video')
            def discovery(module, arguments, log):
                self.assertEqual(module, 'v4_local.py')
                output = Path(arguments[arguments.index('--out') + 1])
                output.write_text(json.dumps({'engine': 'v4-local', 'candidates': []}))
            with patch('v4.run_stage', side_effect=discovery), patch('v4.run_stage_yt_dlp') as download:
                folder = v4.prepare(video=video, root=root / 'jobs', editorial={'start': '10', 'end': '25'})
                download.assert_not_called()
            job = json.loads((folder / 'job.json').read_text())
            self.assertEqual(job['workflow_version'], 'v4')
            self.assertEqual(job['status'], 'editorial-review-required')
            self.assertEqual(job['editorial_request']['start'], '10')
            self.assertFalse(job['uploaded'])
            self.assertEqual(video.read_bytes(), b'original video')

    def test_failed_preparation_is_recorded_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            with patch('v4.run_stage_yt_dlp', side_effect=OSError('offline')):
                with self.assertRaises(OSError):
                    v4.prepare(url='https://youtube.com/watch?v=example', root=root)
            job = json.loads(next(root.glob('*/job-*/job.json')).read_text())
            self.assertEqual(job['status'], 'failed')
            self.assertFalse(job['uploaded'])

    def test_backlog_preserves_completed_rows_and_reuses_review_jobs(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            csv = root / 'backlog.csv'
            original = 'status,url,hook\nuploaded,https://example.test/done,done\nto-cut,https://example.test/new,hook\n'
            csv.write_text(original)
            folder = root / 'jobs' / '2026-11-24' / 'job-existing'
            folder.mkdir(parents=True)
            (folder / 'job.json').write_text(json.dumps({'source_url': 'https://example.test/new',
                'status': 'review-ready', 'editorial_request': {'hook': 'hook'}}))
            with patch('v4.prepare') as prepare:
                rows = v4.prepare_backlog(csv, root / 'jobs')
                prepare.assert_not_called()
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]['reused'])
            self.assertEqual(csv.read_text(), original)

    def test_changed_editorial_request_is_not_reused(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            csv = root / 'backlog.csv'
            csv.write_text('status,url,hook\nto-cut,https://example.test/new,new hook\n')
            folder = root / 'jobs' / '2026-11-24' / 'job-existing'
            folder.mkdir(parents=True)
            (folder / 'job.json').write_text(json.dumps({'source_url': 'https://example.test/new',
                'status': 'review-ready', 'editorial_request': {'hook': 'old hook'}}))
            with patch('v4.prepare', return_value=root / 'new-job') as prepare:
                rows = v4.prepare_backlog(csv, root / 'jobs')
                prepare.assert_called_once()
            self.assertFalse(rows[0]['reused'])

    def test_installer_is_idempotent_and_preserves_renderer_and_other_settings(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            cutter = root / 'clipper'
            cutter.mkdir()
            source = 'from pathlib import Path\nimport sys\ndef render():\n    return "original renderer"\ndef main() -> None:\n    print("legacy")\n'
            (cutter / 'clip.py').write_text(source)
            settings = 'layout:\n  zoom: 1.35\nmetadata:\n  title_template: "{hook} #Shorts"\n'
            (cutter / 'config.yaml').write_text(settings)
            daily = root / 'run_daily.sh'
            daily.write_text('#!/bin/sh\npython clip.py --upload\n')
            install_v4.install(cutter, daily)
            first = (cutter / 'clip.py').read_text()
            self.assertIn('return "original renderer"', first)
            self.assertIn('from v4 import legacy_main', first)
            self.assertIn('zoom: 1.35', (cutter / 'config.yaml').read_text())
            self.assertIn('GTA VI', (cutter / 'config.yaml').read_text())
            self.assertNotIn('--upload', daily.read_text())
            self.assertEqual((cutter / 'clip.py.pre-v4.bak').read_text(), source)
            install_v4.install(cutter, daily)
            self.assertEqual((cutter / 'clip.py').read_text(), first)
            self.assertEqual((cutter / 'clip.py.pre-v4.bak').read_text(), source)

    def test_unsupported_installer_does_not_partially_change_files(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root / 'clip.py').write_text('print("custom cutter")\n')
            (root / 'config.yaml').write_text('metadata: {}\n')
            with self.assertRaises(ValueError):
                install_v4.install(root)
            self.assertEqual((root / 'clip.py').read_text(), 'print("custom cutter")\n')
            self.assertFalse((root / 'clip.py.pre-v4.bak').exists())


if __name__ == '__main__':
    unittest.main()
