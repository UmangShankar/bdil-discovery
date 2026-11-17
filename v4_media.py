"""Bounded-memory local evidence extraction; failures are data, not success."""
import array
import math
import shutil
import subprocess
import tempfile
import time


def probe(video):
    import json
    if not shutil.which('ffprobe'):
        raise ValueError('ffprobe unavailable')
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                        '-of', 'json', str(video)], capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise ValueError('ffprobe could not read media')
    data = json.loads(p.stdout)
    duration = float(data.get('format', {}).get('duration', 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('media duration unavailable')
    return {'duration': duration, 'streams': [
        {k: s[k] for k in ('codec_type', 'codec_name', 'width', 'height') if k in s}
        for s in data.get('streams', [])]}


def _decode(cmd, size, consume):
    if not shutil.which('ffmpeg'):
        return {'status': 'unavailable', 'reason': 'ffmpeg unavailable', 'samples': 0}
    count = 0
    with tempfile.TemporaryFile() as errors:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors)
        try:
            while True:
                raw = p.stdout.read(size)
                if len(raw) != size:
                    break
                consume(count, raw)
                count += 1
        finally:
            p.stdout.close()
            p.wait()
        errors.seek(0)
        error = errors.read(1500).decode(errors='replace').strip()
    return {'status': 'ok' if count and p.returncode == 0 and not error else 'failed',
            'samples': count, 'reason': error or (f'decoder exit {p.returncode}' if p.returncode else ''),
            'backend': 'ffmpeg'}


def audio(video):
    times, levels = [], []
    def consume(i, raw):
        a = array.array('h', raw)
        rms = math.sqrt(sum(x*x for x in a) / len(a)) / 32768
        times.append(i * .5)
        levels.append(rms)
    stage = _decode(['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(video), '-vn',
                     '-ac', '1', '-ar', '8000', '-f', 's16le', '-'], 8000, consume)
    stage.update({'silent': bool(levels) and max(levels) < .0001,
                  'interpretation': 'RMS changes only; speech/music/events are not classified'})
    # An onset, rather than the loudest normal sentence in every window.
    changes = [0.] + [(levels[i] - levels[i-1]) if levels[i] > max(.02,levels[i-1]*1.4) else 0. for i in range(1, len(levels))] if levels else []
    return times, changes, stage


def frames(video, interval=1., force_ffmpeg=False):
    """Try OpenCV, then FFmpeg for missing/partial decoding (including AV1)."""
    import numpy as np
    times, motion, cuts = [], [], []
    last = None
    def consume(t, frame):
        nonlocal last
        if last is not None:
            diff = float(np.abs(frame.astype(float)-last.astype(float)).mean()) / 255
            times.append(t)
            motion.append(diff)
            if diff >= .27:
                cuts.append(t)
        last = frame
    fallback = 'requested' if force_ffmpeg else ''
    if not force_ffmpeg:
        try:
            import cv2
            cap = cv2.VideoCapture(str(video))
            try:
                total = float(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = float(cap.get(cv2.CAP_PROP_FPS))
                expected = total / fps if fps > 0 else 0
                t = 0.
                while cap.isOpened():
                    cap.set(cv2.CAP_PROP_POS_MSEC, t*1000)
                    ok, frame = cap.read()
                    if not ok:
                        break
                    consume(t, cv2.cvtColor(cv2.resize(frame, (160,90)), cv2.COLOR_BGR2GRAY))
                    t += interval
            finally:
                cap.release()
            if times and expected > 0 and t >= expected - 2*interval:
                return times, motion, cuts, {'status':'ok', 'backend':'opencv', 'samples':len(times)+1}
            fallback = 'OpenCV unavailable or incomplete decoding'
        except (ImportError, RuntimeError, ValueError) as exc:
            fallback = type(exc).__name__
        times, motion, cuts, last = [], [], [], None
    stage = _decode(['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(video),
                     '-an', '-vf', f'fps=1/{interval},scale=160:90', '-pix_fmt', 'gray',
                     '-f', 'rawvideo', '-'], 160*90,
                    lambda i, raw: consume(i*interval, np.frombuffer(raw, np.uint8).reshape(90,160)))
    stage['fallback_reason'] = fallback
    return times, motion, cuts, stage


def analyse(video):
    unavailable = {'status':'unavailable', 'reason':'no local media', 'samples':0}
    result = {'audio':dict(unavailable), 'motion':dict(unavailable), 'scene':dict(unavailable),
              'audio_times':[], 'audio_values':[], 'motion_times':[], 'motion_values':[], 'scene_times':[]}
    if video is None:
        return result
    try:
        result['probe'] = probe(video)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        for stage in ('audio','motion','scene'):
            result[stage] = {'status':'failed','reason':str(exc), 'samples':0}
        return result
    started = time.monotonic()
    try:
        at, av, a = audio(video)
        a['processing_seconds'] = round(time.monotonic()-started,3)
        if a['status']=='ok' and len(at)*.5 < result['probe']['duration']-1:
            a.update(status='failed',reason='incomplete audio coverage')
        result.update(audio=a, audio_times=at, audio_values=av)
    except (OSError, subprocess.SubprocessError) as exc:
        result['audio'] = {'status':'failed','reason':str(exc),'samples':0}
    started = time.monotonic()
    try:
        mt, mv, cuts, m = frames(video)
        m['processing_seconds'] = round(time.monotonic()-started,3)
        if m['status']=='ok' and len(mt)+1 < result['probe']['duration']-2:
            m.update(status='failed',reason='incomplete video coverage')
        result.update(motion=m, motion_times=mt, motion_values=mv, scene_times=cuts)
        result['scene'] = {**m, 'method':'1fps grayscale cut proposals; precision +/-1s', 'cuts':len(cuts)}
    except (ImportError, OSError, subprocess.SubprocessError) as exc:
        result['motion'] = {'status':'failed','reason':str(exc),'samples':0}
        result['scene'] = dict(result['motion'])
    return result
