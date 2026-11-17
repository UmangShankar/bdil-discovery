"""Regression coverage for complete thoughts, payoff closure and exported audio."""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import v4_local
from v4_handoff import validate, render_with_cutter
from v4_quality import audit_export, audit_words, ending_reasons, payoff_reasons
from v4_tests import cues


class EndingQualityTests(unittest.TestCase):
    def test_dangling_connectors_even_with_fake_punctuation(self):
        for word in ('but', 'and', 'because', 'so', 'or', 'although', 'however', 'which'):
            for punctuation in ('', '.', '!', '...'):
                with self.subTest(word=word, punctuation=punctuation):
                    self.assertTrue(ending_reasons('The NPC escaped ' + word + punctuation))

    def test_dependent_phrases_and_ellipsis(self):
        for text in ('This is why.', 'It means...', 'The difference is because.',
                     'He escaped, which means.', 'The NPC was going to.', 'The NPC escaped—'):
            with self.subTest(text=text):
                self.assertTrue(ending_reasons(text))

    def test_complete_contrast_and_natural_that_ending(self):
        for text in ('The car crashed, but the driver escaped.',
                     'In code, it is a few lines of if this, then that.',
                     'The animation changes so people have different heights.'):
            self.assertFalse(ending_reasons(text), text)
            self.assertFalse(payoff_reasons(text), text)

    def test_question_hype_and_deferred_payoff_rejected(self):
        for text in ('What happens next?', "We'll find out next time.",
                     "Let's see what happens.", "That's insane!", "I don't know.",
                     'Did the driver escape?!', 'Crazy!'):
            self.assertTrue(payoff_reasons(text), text)

    def test_specific_resolution_survives(self):
        self.assertFalse(payoff_reasons('The cop lost sight of him, and the driver escaped.'))

    def test_rank_rejects_connector_and_promised_payoff(self):
        original = cues()[:3]
        for final in ('The NPC crashed and exploded but.',
                      'The NPC crashed and exploded; what happens next?',
                      'The NPC escaped, but we will find out next time.'):
            candidate = [dict(c) for c in original]
            candidate[-1]['text'] = final
            report = v4_local.discover(candidate, 30)
            self.assertEqual(report['candidates'], [])
            self.assertTrue(report['rejected'])

    def test_padding_does_not_capture_next_unfinished_but(self):
        c = cues()[:3] + [{'start':17., 'end':18., 'text':'But'}]
        picks = v4_local.rank(c,30)
        self.assertTrue(picks)
        self.assertEqual(picks[0]['end'],17.)

    def test_padding_stops_short_of_next_sentence(self):
        c = cues()[:3] + [{'start':17.10, 'end':21., 'text':'But now another NPC approaches.'}]
        picks = v4_local.rank(c,30)
        self.assertTrue(picks)
        first = next(p for p in picks if p['actual_payoff'].endswith('escaped!'))
        self.assertLess(first['end'],17.10)

    def test_reviewed_handoff_cannot_bypass_bad_ending(self):
        c = v4_local.rank(cues(),160)[0]
        c.update(review_required=False, semantic_verified=True,reviewed_by='test',verification_coverage=1)
        c['captions'] += ' But.'
        with self.assertRaisesRegex(ValueError,'ending rejected'):
            validate(c,160,reviewed=True)

    def test_actual_export_leak_overrides_clean_planned_captions(self):
        words = [{'start':0.,'end':1.,'word':'Escaped.'},
                 {'start':1.1,'end':1.3,'word':'But.'}]
        result = audit_words(words,2.,payoff='The driver escaped.')
        self.assertFalse(result['passed'])
        self.assertEqual(result['last_word'],'But.')

    def test_word_at_cut_is_held(self):
        result = audit_words([{'start':1.,'end':2.,'word':'Escaped.'}],2.)
        self.assertFalse(result['passed'])
        self.assertTrue(any('touches cut' in r for r in result['reasons']))

    def test_export_complete_word_with_clearance_passes(self):
        result = audit_words([{'start':1.,'end':1.7,'word':'Escaped.'}],2.)
        self.assertTrue(result['passed'])
        self.assertEqual(result['tail_clearance'],.3)

    def test_asr_punctuation_omission_needs_reviewed_matching_ending(self):
        w=[{'start':0.,'end':.4,'word':'He'},
           {'start':.4,'end':1.,'word':'escaped'}]
        self.assertTrue(audit_words(w,2.,payoff='He escaped.')['passed'])
        self.assertFalse(audit_words(w,2.)['passed'])
        self.assertFalse(audit_words(w,2.,payoff='The police arrested him.')['passed'])

    def test_clean_extra_sentence_after_payoff_is_held(self):
        w=[{'start':0.,'end':.5,'word':'Escaped.'},
           {'start':.6,'end':1.,'word':'Subscribe.'}]
        self.assertFalse(audit_words(w,2.,payoff='The driver escaped.')['passed'])

    def test_reviewed_suffix_tolerates_joined_ray_cast_tokenization(self):
        w=[{'start':0.,'end':.1,'word':'Programmers'},
           {'start':.1,'end':.2,'word':'call'},
           {'start':.2,'end':.3,'word':'it'},
           {'start':.3,'end':.4,'word':'a'},
           {'start':.4,'end':.5,'word':'ray'},
           {'start':.5,'end':.7,'word':'cast'}]
        self.assertTrue(audit_words(w,1.,payoff='Programmers call it a raycast.')['passed'])

    def test_no_speech_and_invalid_word_times_do_not_pass(self):
        for words in ([], [{'start':0,'end':99,'word':'Escaped.'}]):
            self.assertFalse(audit_words(words,2.)['passed'])

    def test_final_export_is_transcribed_not_planned_text(self):
        with patch('v4_media.probe',return_value={'duration':2.}), \
             patch('v4_transcript.words',return_value=[{'start':0.,'end':1.,'word':'But.'}]) as transcribe:
            result=audit_export('rendered.mp4',payoff='The driver escaped.')
        transcribe.assert_called_once_with('rendered.mp4','small')
        self.assertFalse(result['passed'])

    def test_failed_audio_audit_blocks_final_render_handoff(self):
        c=v4_local.rank(cues(),160)[0]
        c.update(review_required=False,semantic_verified=True,reviewed_by='test',verification_coverage=1)
        module=SimpleNamespace(
            cut_local=lambda *a:Path('mock-raw.mp4'),
            build_ass=lambda words,hook,duration,path:path.write_text('mock-ass'),
            render=lambda raw,ass,path:path.write_bytes(b'mock-render'))
        spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module:None))
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'final.mp4'
            with patch('importlib.util.spec_from_file_location',return_value=spec), \
                 patch('importlib.util.module_from_spec',return_value=module), \
                 patch('v4_media.probe',return_value={'duration':c['duration']}), \
                 patch('v4_quality.audit_export',return_value={'passed':False,'reasons':['unfinished connective']}) as audit:
                with self.assertRaisesRegex(ValueError,'final export ending rejected'):
                    render_with_cutter('source.mp4',c,'cutter.py',out)
            self.assertFalse(out.exists())
            audit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
