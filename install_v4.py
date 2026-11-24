"""Activate the accepted V4 workflow without replacing cutter rendering helpers."""
import argparse
import ast
from pathlib import Path
import re
import shutil

MARKER = '# V4 default entry point (accepted rollout)'


def backup(path):
    saved = path.with_name(path.name + '.pre-v4.bak')
    if not saved.exists():
        shutil.copy2(path, saved)


def install(target, daily=None):
    target = Path(target).resolve()
    path = target / 'clip.py'
    original = path.read_text()
    changed = original
    if MARKER not in original:
        if original.count('def main() -> None:\n') != 1:
            raise ValueError('unsupported cutter main; no files changed')
        changed = original.replace('def main() -> None:\n', '''def main() -> None:
    # V4 default entry point (accepted rollout)
    discovery = Path(__file__).resolve().parent.parent / "discovery"
    sys.path.insert(0, str(discovery))
    from v4 import legacy_main
    raise SystemExit(legacy_main())

''', 1)
    ast.parse(changed)
    config = target / 'config.yaml'
    text = config.read_text()
    updated, count = re.subn(r'(?m)^  title_template:.*$',
                            '  title_template: "{hook} | GTA VI #Shorts"', text)
    if count != 1:
        raise ValueError('unsupported metadata title template; no files changed')
    daily = Path(daily).resolve() if daily else None
    launcher = Path(__file__).with_name('run_v4_daily.sh')
    if daily and (not daily.is_file() or not launcher.is_file()):
        raise ValueError('daily launcher missing; no files changed')
    if changed != original:
        backup(path)
        path.write_text(changed)
    if updated != text:
        backup(config)
        config.write_text(updated)
    if daily and daily.read_bytes() != launcher.read_bytes():
        backup(daily)
        shutil.copy2(launcher, daily)
        daily.chmod(daily.stat().st_mode | 0o100)
    return {'engine': 'v4', 'cutter': str(path), 'daily': str(daily) if daily else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=Path('../clipper'))
    parser.add_argument('--daily', type=Path)
    args = parser.parse_args()
    print(install(args.target, args.daily))
