"""Create dated, portable delivery packages; a portrait thumbnail is mandatory."""
import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from zoneinfo import ZoneInfo


def short_slug(title):
    title = re.sub(r'#\w+', '', str(title))
    plain = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-z0-9]+', '-', plain.lower()).strip('-')[:55].rstrip('-')
    if not slug:
        raise ValueError('a readable short title is required')
    return slug


def package_date(value=None):
    if value is None:
        return datetime.now(ZoneInfo('Europe/London')).date().isoformat()
    return date.fromisoformat(str(value)).isoformat()


def thumbnail_size(path):
    path = Path(path)
    if path.suffix.lower() not in ('.jpg', '.jpeg', '.png') or not path.is_file() or not path.stat().st_size:
        raise ValueError('a real JPG or PNG Shorts thumbnail is required')
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', 'stream=width,height', '-of', 'json', str(path)],
                       capture_output=True, text=True, check=True, timeout=30)
    streams = json.loads(p.stdout).get('streams', [])
    if not streams or (streams[0].get('width'), streams[0].get('height')) != (1080, 1920):
        raise ValueError('Shorts thumbnail must be 1080x1920 (9:16 portrait)')
    return 1080, 1920


def validate_metadata(meta):
    for key in ('title', 'description'):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise ValueError(f'package metadata requires {key}')
    if len(meta['title']) > 100 or len(meta['description']) > 5000:
        raise ValueError('title/description exceeds upload limits')
    if not isinstance(meta.get('tags'), list) or not meta['tags'] or not all(isinstance(t, str) and t.strip() for t in meta['tags']):
        raise ValueError('package metadata requires tags')
    review = meta.get('payoff_review', {})
    if not isinstance(review, dict) or not all(isinstance(review.get(k), str) and review[k].strip()
            for k in ('setup', 'resolution', 'why_it_resolves', 'reviewed_by')):
        raise ValueError('package requires a complete payoff_review')
    if not isinstance(meta.get('ending_audit'), dict) or meta['ending_audit'].get('passed') is not True:
        raise ValueError('package requires a passed final ending audit')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def build_package(video, thumbnail, metadata, root=None, short_title=None, day=None,
                  captions=None, thumbnail_prompt=None):
    """One delivery folder per clip; revisions get _v2, _v3, never overwrite."""
    from v4_media import probe
    video, thumbnail = Path(video).resolve(), Path(thumbnail).resolve()
    if not video.is_file() or video.suffix.lower() != '.mp4' or not video.stat().st_size:
        raise ValueError('a finished MP4 is required')
    meta = json.loads(json.dumps(metadata, allow_nan=False))
    # New deliveries follow the accepted branding rule; old packages remain valid.
    if isinstance(meta.get('title'), str) and meta['title'].strip() and not re.search(r'\bGTA VI\b', meta['title']):
        meta['title'] = 'GTA VI | ' + meta['title']
    meta['workflow_version'] = 'v4'
    validate_metadata(meta)
    if meta.get('file'):
        reference = Path(meta['file'])
        reference = reference if reference.is_absolute() else video.parent/reference
        if reference.resolve() != video:
            raise ValueError('metadata points to a different video')
    thumbnail_size(thumbnail)
    media = probe(video)
    v = next((s for s in media['streams'] if s.get('codec_type') == 'video'), {})
    if not v.get('width') or not v.get('height') or v['width']*16 != v['height']*9:
        raise ValueError('finished Shorts video must be 9:16 portrait')
    for item in (captions, thumbnail_prompt):
        if item is not None and not Path(item).is_file():
            raise ValueError('optional captions/prompt file does not exist')
    day = package_date(day)
    name = short_slug(short_title or meta['title']) + '_' + day
    root = Path(root) if root is not None else Path(__file__).resolve().parent/'packages'
    root.mkdir(parents=True, exist_ok=True)
    version = 1
    while True:
        target = root/(name if version == 1 else f'{name}_v{version}')
        try:
            target.mkdir()
            break
        except FileExistsError:
            version += 1
    thumb_name = 'thumbnail.png' if thumbnail.suffix.lower() == '.png' else 'thumbnail.jpg'
    try:
        shutil.copyfile(video, target/'video.mp4')
        shutil.copyfile(thumbnail, target/thumb_name)
        if captions:
            shutil.copyfile(captions, target/'captions.ass')
        if thumbnail_prompt:
            shutil.copyfile(thumbnail_prompt, target/'THUMBNAIL-PROMPT.txt')
        meta.update(file='video.mp4', thumbnail=thumb_name, package_date=day,
                    package_name=target.name, duration=media['duration'])
        (target/'metadata.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
        (target/'ending-audit.json').write_text(json.dumps(meta['ending_audit'], indent=2, ensure_ascii=False)+'\n')
        (target/'payoff-review.json').write_text(json.dumps(meta['payoff_review'], indent=2, ensure_ascii=False)+'\n')
        keywords = meta.get('keywords') or meta['tags']
        visibility = meta.get('requested_privacy', 'private').capitalize()
        details = (f"VIDEO FILE\nvideo.mp4\n\nTHUMBNAIL\n{thumb_name} (1080x1920, 9:16)\n\n"
                   f"TITLE\n{meta['title']}\n\nDESCRIPTION\n{meta['description']}\n\n"
                   f"TAGS (comma-separated)\n{', '.join(meta['tags'])}\n\n"
                   f"PRIMARY KEYWORDS\n{', '.join(keywords)}\n\n"
                   f"OTHER PREPARED SETTINGS\nCategory: Gaming\nLanguage: English\nVisibility: {visibility}\n"
                   f"Schedule: {meta.get('publish_at') or 'None'}\n")
        (target/'UPLOAD-DETAILS.txt').write_text(details)
        (target/'README.txt').write_text(
            f"{meta['title']}\nPackage date: {day} (Europe/London)\n\n"
            f"Video: video.mp4\nThumbnail: {thumb_name} — 1080x1920 portrait\n"
            "Upload text: UPLOAD-DETAILS.txt\nMetadata: metadata.json\n"
            "Quality records: payoff-review.json and ending-audit.json\n\n"
            "Packaging does not upload, publish, or change visibility.\n")
        files = {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in target.iterdir() if p.is_file()}
        manifest = {'schema_version': 1, 'workflow_version': 'v4', 'package_name': target.name, 'date': day,
                    'timezone': 'Europe/London', 'title': meta['title'], 'short_title': short_title or meta['title'],
                    'video': 'video.mp4', 'thumbnail': thumb_name, 'thumbnail_width': 1080,
                    'thumbnail_height': 1920, 'thumbnail_required': True, 'duration': media['duration'],
                    'files': files, 'quality_passed': True, 'source': meta.get('source'),
                    'uploaded': bool(meta.get('upload', False))}
        (target/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
        validate_package(target)
        return target.resolve()
    except Exception:
        (target/'PACKAGE-INCOMPLETE.txt').write_text('Build failed. This folder is not a completed delivery package.\n')
        raise


def validate_package(folder):
    folder = Path(folder)
    m = json.loads((folder/'manifest.json').read_text())
    required = ['video.mp4', m['thumbnail'], 'metadata.json', 'UPLOAD-DETAILS.txt',
                'README.txt', 'ending-audit.json', 'payoff-review.json']
    if ((folder/'PACKAGE-INCOMPLETE.txt').exists() or not m.get('thumbnail_required')
            or m.get('quality_passed') is not True or m.get('package_name') != folder.name):
        raise ValueError('package is incomplete')
    for name in required:
        if Path(name).name != name or not (folder/name).is_file() or not (folder/name).stat().st_size:
            raise ValueError(f'package is missing {name}')
    thumbnail_size(folder/m['thumbnail'])
    validate_metadata(json.loads((folder/'metadata.json').read_text()))
    for name, info in m['files'].items():
        if Path(name).name != name or digest(folder/name) != info['sha256']:
            raise ValueError(f'package file changed: {name}')
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--video', type=Path, required=True)
    ap.add_argument('--thumbnail', type=Path, required=True)
    ap.add_argument('--metadata', type=Path, required=True)
    ap.add_argument('--short-title', required=True)
    ap.add_argument('--date', help='ISO package date; defaults to today in Europe/London')
    ap.add_argument('--root', type=Path)
    ap.add_argument('--captions', type=Path)
    ap.add_argument('--thumbnail-prompt', type=Path)
    a = ap.parse_args()
    try:
        print(build_package(a.video, a.thumbnail, json.loads(a.metadata.read_text()),
                            root=a.root, short_title=a.short_title, day=a.date,
                            captions=a.captions, thumbnail_prompt=a.thumbnail_prompt))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        ap.exit(2, f'Package held: {exc}\n')


if __name__ == '__main__':
    main()
