"""Optional offline-only speech recovery. Never downloads a model."""
from pathlib import Path


def transcribe(video, model='small'):
    from faster_whisper import WhisperModel
    engine = WhisperModel(str(model),device='cpu',compute_type='int8',cpu_threads=2,
                          local_files_only=True)
    segments, info = engine.transcribe(str(video),vad_filter=True,language='en',
                                       condition_on_previous_text=False,beam_size=1)
    cues, dropped = [], 0
    for s in segments:
        if (not s.text.strip() or s.no_speech_prob >= .6 or s.end-s.start > 20
                or len(s.text.split())/max(.1,s.end-s.start) < .5):
            dropped += 1
            continue
        cues.append({'start':round(s.start,3),'end':round(s.end,3),'text':s.text.strip()})
    return cues, {'status':'ok' if cues else 'unavailable','method':'faster-whisper local cached model',
                  'model':str(model),'cues':len(cues),'dropped_segments':dropped,'language':'en',
                  'limitation':'ASR can hallucinate or mishear; compare audio during review'}


def words(video, model='small', *, vad_filter=True, beam_size=1,
          no_speech_threshold=.6, include_probability=False):
    from faster_whisper import WhisperModel
    engine = WhisperModel(str(model),device='cpu',compute_type='int8',cpu_threads=2,
                          local_files_only=True)
    segments,_ = engine.transcribe(str(video),language='en',vad_filter=vad_filter,
                                   word_timestamps=True,condition_on_previous_text=False,
                                   beam_size=beam_size,no_speech_threshold=no_speech_threshold)
    return [{'start':w.start,'end':w.end,'word':w.word.strip(),
             **({'probability':float(w.probability)} if include_probability else {})}
            for s in segments if no_speech_threshold is None or s.no_speech_prob < no_speech_threshold
            for w in (s.words or []) if w.word.strip()]
