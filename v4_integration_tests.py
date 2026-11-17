"""Regression tests for semantic gates, actual codecs, handoff and Sheet safety."""
import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import v4_local as v4
import v4_media as media
from v4_handoff import validate, previews
from v4_sheets import plan, SPREADSHEET
from v4_tests import cues


def passage(texts):
    return [{'start':i*6.,'end':i*6.+5.9,'text':t} for i,t in enumerate(texts)]


class Semantics(unittest.TestCase):
    def test_educational_insight(self):
        c = passage(['Why do GTA NPCs all look the same height?',
                     'The old animation system shared fixed body sizes across every character.',
                     'GTA adjusts animations on the fly so people can have different heights.'])
        p = v4.rank(c,18)
        self.assertTrue(p)
        self.assertEqual(p[0]['category'],'news_explainer')
        self.assertIn('different heights',p[0]['actual_payoff'])

    def test_historical_metaphor(self):
        c = passage(['Why did GTA take so many years to finish?',
                     'Full production started and the pandemic hit the whole studio.',
                     'The developers worked on the map for several years.'])
        self.assertEqual(v4.rank(c,18),[])

    def test_historical_comparison_is_not_action(self):
        c = passage(['Why did GTA physics change?',
                     'GTA 4 brought in Euphoria in 2008.',
                     'It uses physics instead of one canned animation.'])
        p = v4.rank(c,18)
        self.assertTrue(p)
        self.assertNotEqual(p[0]['category'],'gameplay_action')

    def test_music_and_narration_do_not_create_events(self):
        c=passage(['What are we doing in GTA today?',
                   'We drive around the city and talk about the scenery.',
                   'The music is loud and the city looks great.'])
        m=media.analyse(None)
        m.update(audio_times=[0,6,12],audio_values=[0,1,2],motion_times=[1,6,12],motion_values=[0,1,2])
        m['audio']={'status':'ok'};m['motion']={'status':'ok'}
        self.assertEqual(v4.discover(c,18,media=m)['candidates'],[])

    def test_no_payoff(self):
        c=passage(['Wait what just happened in GTA?',
                   'The NPC is driving directly towards the car.',
                   'We are waiting to see what happens next.'])
        self.assertEqual(v4.rank(c,18),[])

    def test_speculation(self):
        c=passage(['Why might GTA NPCs change?', 'Rockstar might change the animation system.',
                   'They might use physics instead of fixed animations.'])
        self.assertEqual(v4.rank(c,18),[])

    def test_empty_and_limit_zero(self):
        self.assertEqual(v4.rank([],100),[])
        self.assertEqual(v4.rank(cues(),100,limit=0),[])

    def test_missing_media(self):
        r=v4.discover(cues(),160,video='/does/not/exist.mp4')
        self.assertEqual(r['stages']['motion']['status'],'failed')
        self.assertTrue(all(p['review_required'] for p in r['candidates']))

    def test_invalid_duration_and_cues(self):
        for d in [0,-1,math.nan,math.inf]:
            with self.assertRaises(ValueError): v4.rank(cues(),d)
        self.assertEqual(v4.rank([{'start':-1,'end':1000,'text':'Wait NPC exploded!'}],20),[])

    def test_fixed_weight_missing_evidence(self):
        m=media.analyse(None)
        a=v4.discover(cues(),160,media=m)['candidates'][0]
        m['audio']={'status':'ok'}; m['motion']={'status':'ok'};m['scene']={'status':'ok'}
        b=v4.discover(cues(),160,media=m)['candidates'][0]
        self.assertEqual(a['score'],b['score'])
        self.assertLess(a['confidence'],b['confidence'])

    def test_json_contract_and_duplicate(self):
        p=v4.rank(cues(),160)
        self.assertEqual(len(p),1)  # repeated identical event is deduplicated
        c=json.loads(json.dumps(p,allow_nan=False))[0]
        for key in ['rank','duration','category','overall_score','hook_score','story_score',
                    'payoff_score','confidence','verification_coverage','reason_for_selection',
                    'actual_payoff','review_required']:
            self.assertIn(key,c)
        validate(c,160)
        with self.assertRaises(ValueError):validate(c,160,reviewed=True)

    def test_missing_subtitles_cli(self):
        import sys
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'result.json'
            p=subprocess.run([sys.executable,'v4_local.py','--duration','20','--out',str(out)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            r=json.loads(out.read_text())
            self.assertEqual(r['candidates'],[])
            self.assertEqual(r['stages']['transcript']['status'],'unavailable')
            self.assertEqual(r['api_cost_usd'],0)
    def test_offline_whisper_never_downloads(self):
        from v4_transcript import transcribe
        with patch('faster_whisper.WhisperModel') as model:
            model.return_value.transcribe.return_value=([],None)
            c,s=transcribe('dummy.mp4','small')
            self.assertTrue(model.call_args.kwargs['local_files_only'])
            self.assertEqual(c,[])
            self.assertEqual(s['status'],'unavailable')
    def test_handoff_invalid_times(self):
        c=v4.rank(cues(),160)[0]
        for a,b in [(-1,20),(0,200),(10,5),(math.nan,20),(0,math.inf),(True,20)]:
            with self.assertRaises(ValueError):validate({**c,'start':a,'end':b},160)


class Sheets(unittest.TestCase):
    def snapshot(self):
        h=['status','tier','score','source','title','creator','url','hook','start','end','captions','id']
        return {'spreadsheet_id':SPREADSHEET,'sheet_name':'backlog','headers':h,'rows':[
            {'row_number':2,'values':['to-cut','','','','','','https://example.test','','','','','yt:test']},
            {'row_number':3,'values':['uploaded','','','','','','https://example.test','','','','','yt:done']}]}
    def report(self,reviewed=False):
        r=v4.discover(cues(),160);r['source_url']='https://example.test'
        if reviewed:
            for c in r['candidates']:c.update(review_required=False,semantic_verified=True,reviewed_by='test reviewer',verification_coverage=1)
        return r
    def test_unverified_held(self):
        p=plan(self.snapshot(),{'https://example.test':self.report()})
        self.assertEqual(p['append_rows'],[]);self.assertEqual(p['legacy_patches'],[])
        self.assertEqual(len(p['held']),1)
    def test_reviewed_multirow_idempotent_and_preserve_manual(self):
        s=self.snapshot();r=self.report(True)
        p=plan(s,{'https://example.test':r})
        self.assertEqual(len(p['append_rows']),1)
        self.assertEqual(len(p['legacy_patches']),1)
        self.assertEqual(p['legacy_patches'][0]['range'],'backlog!H2:K2')
        s['candidate_ids']=[p['append_rows'][0][0]]
        s['rows'][0]['values'][7]='manual hook'
        p=plan(s,{'https://example.test':r})
        self.assertEqual(p['append_rows'],[]);self.assertEqual(p['legacy_patches'],[])
    def test_shifted_live_headers(self):
        s=self.snapshot()
        s['headers'].insert(0,'Date Added')
        for r in s['rows']: r['values'].insert(0,'2026-11-16')
        p=plan(s,{'https://example.test':self.report(True)})
        self.assertEqual(p['legacy_columns'],'I:L')
        self.assertEqual(p['legacy_patches'][0]['range'],'backlog!I2:L2')
    def test_multiple_candidates_use_child_table(self):
        r=self.report(True)
        c=dict(r['candidates'][0]);c.update(start=40.,end=57.25,rank=2)
        r['candidates'].append(c)
        p=plan(self.snapshot(),{'https://example.test':r})
        self.assertEqual(len(p['append_rows']),2)
        self.assertEqual(len(p['legacy_patches']),1)
    def test_schema_and_source_identity(self):
        s=self.snapshot();s['headers'][6]='wrong'
        with self.assertRaises(ValueError):plan(s,{})
        s=self.snapshot();r=self.report(True);r['source_url']='wrong'
        self.assertEqual(plan(s,{'https://example.test':r})['append_rows'],[])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class ActualMedia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)
        cls.video=cls.folder/'h264.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=64x64:rate=5:duration=18',
                        '-f','lavfi','-i','sine=frequency=440:sample_rate=8000:duration=18',
                        '-c:v','libx264','-threads','1','-c:a','aac',str(cls.video)],check=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_audio_steady_tone_and_silence(self):
        t,v,s=media.audio(self.video)
        self.assertEqual(s['status'],'ok'); self.assertLess(sum(v),.05)
        silent=self.folder/'silent.wav'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','anullsrc=r=8000:cl=mono','-t','2',str(silent)],check=True)
        t,v,s=media.audio(silent)
        self.assertTrue(s['silent']);self.assertEqual(max(v),0)
    def test_ffmpeg_fallback(self):
        cap=MagicMock();cap.isOpened.return_value=False
        with patch('cv2.VideoCapture',return_value=cap):
            t,v,c,s=media.frames(self.video)
        self.assertEqual(s['backend'],'ffmpeg');self.assertEqual(s['status'],'ok')
        self.assertGreater(len(t),10);self.assertGreater(max(v),0)
    def test_vp9_and_av1_decoding(self):
        for codec,ext in [('libvpx-vp9','webm'),('libsvtav1','mkv')]:
            dest=self.folder/f'{codec}.{ext}'
            subprocess.run(['ffmpeg','-v','error','-i',str(self.video),'-t','2','-an',
                            '-c:v',codec,'-threads','1',*(['-svtav1-params','lp=1:log-level=0'] if codec=='libsvtav1' else []),str(dest)],check=True,timeout=60)
            t,v,c,s=media.frames(dest,force_ffmpeg=True)
            self.assertEqual(s['status'],'ok',s)
    def test_unsupported_corrupt_media(self):
        p=self.folder/'corrupt.mp4';p.write_text('not a video')
        r=media.analyse(p)
        self.assertEqual(r['motion']['status'],'failed')
        self.assertEqual(r['audio']['status'],'failed')
    def test_preview_playable_and_no_overwrite(self):
        c=v4.rank(cues(),160)[0]
        out=previews(self.video,[c],self.folder/'previews',18)
        self.assertLess(abs(out[0]['duration']-c['duration']),.25)
        with self.assertRaises(ValueError):previews(self.video,[c],self.folder/'previews',18)
    def test_probe_overrides_duration(self):
        m=media.analyse(None);m['probe']=media.probe(self.video)
        r=v4.discover(cues(),9999,media=m)
        self.assertAlmostEqual(r['duration'],18,delta=.1)
        self.assertTrue(all(p['end']<=18 for p in r['candidates']))

if __name__=='__main__':unittest.main()
