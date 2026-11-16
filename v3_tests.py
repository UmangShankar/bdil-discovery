"""V3 zero-network regression tests for transcript parsing and hook boundaries."""
import unittest
from smart_hooks import parse_vtt, validate

SAMPLE = """WEBVTT

00:00:01.000 --> 00:00:03.000
GTA 6 NPCs could fight back.

00:00:03.000 --> 00:00:05.000
They might call the police.

00:00:05.000 --> 00:00:07.000
They might call the police.
"""

class V3Tests(unittest.TestCase):
    def test_read_english_vtt_and_deduplicate(self):
        cues = parse_vtt(SAMPLE)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[1]["end"], 7)
    def test_payoff_within_cut(self):
        cues = [{"start": 1, "end": 3, "text": "Setup"},
                {"start": 15, "end": 19, "text": "Payoff"}]
        self.assertIsNotNone(validate({"start": 1, "end": 19.4,
             "hook": "What if NPCs could call police?", "payoff_cue": 1},cues,25))
    def test_premature_cut_rejected(self):
        cues = [{"start": 1, "end": 3, "text": "Setup"},
                {"start": 15, "end": 21, "text": "Payoff"}]
        self.assertIsNone(validate({"start": 1, "end": 19,
             "hook": "What if NPCs could call police?", "payoff_cue": 1},cues,25))

if __name__ == "__main__":
    unittest.main()
