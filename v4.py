"""Default V4 entry point: prepare sources, discover, render, package and verify.

Preparation creates review jobs; it never marks a backlog row clipped or uploads.
Reviewed editorial cuts use the same V4 quality and package contracts.
"""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import uuid
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
JOBS = HERE / 'v4_test' / 'jobs'


def run_stage(module, arguments, log):
    with Path(log).open('w') as stream:
        subprocess.run([sys.executable, str(HERE / module), *map(str, arguments)],
                       stdout=stream, stderr=subprocess.STDOUT, check=True)


def prepare(*, url=None, video=None, vtt=None, root=JOBS, whisper_model=None,
            editorial=None):
    if bool(url) == bool(video):
        raise ValueError('provide one public URL or local video')
    if url and (urlparse(url).scheme not in ('https', 'http') or not urlparse(url).hostname):
        raise ValueError('source must be a public HTTP(S) URL')
    if video and not Path(video).is_file():
        raise ValueError('local video does not exist')
    if vtt and not Path(vtt).is_file():
        raise ValueError('VTT file does not exist')
    from v4_package import package_date
    folder = Path(root).resolve() / package_date() / ('job-' + uuid.uuid4().hex[:12])
    folder.mkdir(parents=True, exist_ok=False)
    job = {'workflow_version': 'v4', 'source_url': url, 'status': 'preparing',
           'editorial_request': editorial or {}, 'uploaded': False}
    record = folder / 'job.json'
    record.write_text(json.dumps(job, indent=2))
    try:
        if url:
            common = ['--no-playlist', '--js-runtimes', 'node',
                      '--remote-components', 'ejs:github', '-o', str(folder / 'source.%(ext)s')]
            run_stage_yt = lambda args, log: run_stage_yt_dlp(args, folder / log)
            run_stage_yt([*common, '--write-info-json', '-f',
                          'bv*[width<=1280][height<=1280][vcodec^=avc1]+ba/b[width<=1280][height<=1280]',
                          '--merge-output-format', 'mp4', url], 'download.log')
            video = folder / 'source.mp4'
            if not video.is_file():
                raise ValueError('download did not produce source.mp4; inspect download.log')
            try:
                run_stage_yt([*common, '--skip-download', '--write-auto-subs',
                              '--sub-langs', 'en-orig', '--sub-format', 'vtt', url], 'captions.log')
            except subprocess.CalledProcessError:
                job['caption_note'] = 'Caption download failed; local ASR or editorial review required.'
            captions = sorted(folder.glob('source*.vtt'))
            vtt = captions[0] if captions else None
        video = Path(video).resolve()
        arguments = ['--video', video, '--out', folder / 'candidates.json',
                     '--previews', folder / 'previews', '--evidence-cache', folder / 'evidence.json']
        if url:
            arguments += ['--source-url', url]
        if vtt:
            arguments += ['--vtt', Path(vtt).resolve()]
        if whisper_model:
            arguments += ['--whisper-model', whisper_model, '--transcript-cache', folder / 'transcript.json']
        run_stage('v4_local.py', arguments, folder / 'discovery.log')
        report = json.loads((folder / 'candidates.json').read_text())
        if report.get('engine') != 'v4-local':
            raise ValueError('unexpected discovery engine')
        job.update(source_video=str(video), candidate_report='candidates.json',
                   candidate_count=len(report['candidates']),
                   status='review-ready' if report['candidates'] else 'editorial-review-required')
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        job.update(status='failed', error=str(exc))
        raise
    finally:
        record.write_text(json.dumps(job, indent=2) + '\n')
    return folder


def run_stage_yt_dlp(arguments, log):
    with Path(log).open('w') as stream:
        subprocess.run([sys.executable, '-m', 'yt_dlp', *map(str, arguments)],
                       stdout=stream, stderr=subprocess.STDOUT, check=True)


def prepare_backlog(path, root=JOBS, whisper_model=None):
    """Read selected rows, reusing prepared sources; never rewrite Sheet/CSV state."""
    root = Path(root)
    existing = {}
    for record in sorted(root.glob('*/job-*/job.json')):
        job = json.loads(record.read_text())
        if job.get('status') in ('review-ready', 'editorial-review-required'):
            existing[job.get('source_url')] = record.parent
    results = []
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            if row.get('status') != 'to-cut' or 'SPOILER' in (row.get('flags') or ''):
                continue
            url = row.get('url', '').strip()
            request = {k: row[k] for k in ('start', 'end', 'hook', 'title') if row.get(k)}
            try:
                # An explicit editorial selection can change while the URL stays the same.
                prior = existing.get(url)
                if prior and json.loads((prior / 'job.json').read_text()).get('editorial_request') != request:
                    prior = None
                folder = prior or prepare(url=url, root=root, whisper_model=whisper_model, editorial=request)
                existing[url] = folder
                results.append({'source_url': url, 'job': str(folder), 'reused': bool(prior)})
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                results.append({'source_url': url, 'status': 'failed', 'error': str(exc)})
    return results


def legacy_main(argv=None):
    """Compatibility route for clip.py; never enter V3's selection/upload code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', nargs='?')
    parser.add_argument('--file', type=Path)
    parser.add_argument('--vtt', type=Path)
    parser.add_argument('--backlog', type=Path)
    parser.add_argument('--jobs-root', type=Path, default=JOBS)
    parser.add_argument('--whisper-model')
    for name in ('start', 'end', 'hook', 'title'):
        parser.add_argument('--' + name)
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--publish-at')
    args = parser.parse_args(argv)
    if args.upload or args.publish_at:
        parser.error('V4 preparation does not upload. Upload only completed, reviewed V4 packages when requested.')
    try:
        if args.backlog:
            result = prepare_backlog(args.backlog, args.jobs_root, args.whisper_model)
        else:
            request = {k: getattr(args, k) for k in ('start', 'end', 'hook', 'title') if getattr(args, k)}
            result = {'workflow_version': 'v4', 'job': str(prepare(url=args.url, video=args.file,
                      vtt=args.vtt, root=args.jobs_root, whisper_model=args.whisper_model, editorial=request))}
        print(json.dumps(result, indent=2))
        if isinstance(result, list) and any(x.get('status') == 'failed' for x in result):
            return 1
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, 'V4 preparation failed: ' + str(exc) + '\n')


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    commands = {'discover': 'v4_local.py', 'render': 'v4_handoff.py', 'package': 'v4_package.py'}
    if args and args[0] in commands:
        return subprocess.call([sys.executable, str(HERE / commands[args[0]]), *args[1:]])
    if args and args[0] == 'verify':
        from v4_package import validate_package
        if len(args) != 2:
            raise SystemExit('usage: v4.py verify PACKAGE_FOLDER')
        print(json.dumps(validate_package(args[1]), indent=2))
        return 0
    if args and args[0] == 'prepare':
        args.pop(0)
    return legacy_main(args)


if __name__ == '__main__':
    raise SystemExit(main())
