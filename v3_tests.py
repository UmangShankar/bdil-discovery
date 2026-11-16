"""V3 zero-network regression tests for transcript parsing and hook boundaries."""
import unittest
from smart_hooks import parse_vtt, validate, rewrite_invalid_hook, build_windows, choose_window
from unittest.mock import patch, Mock

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
        self.assertEqual(cues[1]["end"], 5)
    def test_real_youtube_rolling_captions(self):
        sample = """WEBVTT

00:00:00.000 --> 00:00:02.110 align:start position:0%
GTA<00:00:00.520><c> 6</c><00:00:00.880><c> is</c>

00:00:02.110 --> 00:00:02.120 align:start position:0%
GTA 6 is

00:00:02.120 --> 00:00:04.630 align:start position:0%
GTA 6 is
amazing<00:00:04.200><c> today.</c>
"""
        cues = parse_vtt(sample)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["text"], "GTA 6 is")
        self.assertEqual(cues[1]["text"], "amazing today.")
        self.assertNotIn("align:start", str(cues))

    def test_payoff_within_cut(self):
        cues = [{"start": 1, "end": 3, "text": "Setup"},
                {"start": 15, "end": 19, "text": "Payoff."}]
        self.assertIsNotNone(validate({"start": 1, "end": 19.4,
             "hook": "What if NPCs could call police?", "payoff_cue": 1},cues,25))
    def test_mid_sentence_end_is_snapped_forward(self):
        cues = [{"start": 1, "end": 3, "text": "Setup"},
                {"start": 15, "end": 21, "text": "Payoff."}]
        chosen = validate({"start": 1, "end": 19,
            "hook": "What if NPCs could call police?", "payoff_cue": 1}, cues, 25)
        self.assertIsNotNone(chosen)
        self.assertAlmostEqual(chosen["end"], 21.35)

    def test_mid_cue_sentence_is_split(self):
        s = """WEBVTT

00:04:52.160 --> 00:04:54.750
911 on you. This is a huge improvement
"""
        cues = parse_vtt(s)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["text"], "911 on you.")
        self.assertEqual(cues[1]["text"], "This is a huge improvement")
        self.assertLess(cues[0]["end"], cues[1]["end"])

    def test_short_suggestion_recovers_full_setup(self):
        cues = [
            {"start": 560.0, "end": 563.9, "text": "Previous statement."},
            {"start": 564.0, "end": 569.9, "text": "In GTA 5, traffic was easily blocked."},
            {"start": 570.0, "end": 577.0, "text": "But GTA 6 drivers might find another route."},
        ]
        candidate = {"start": 570.0, "end": 577.3,
                     "hook": "NPC traffic could finally get smarter!",
                     "payoff_cue": 2}
        chosen = validate(candidate, cues, 674)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["start"], 564.0)
        self.assertAlmostEqual(chosen["end"], 577.35)

    def test_short_suggestion_without_full_setup_is_rejected(self):
        cues = [{"start": 566.0, "end": 569.9, "text": "Incomplete setup"},
                {"start": 570.0, "end": 577.0, "text": "The ending is here."}]
        self.assertIsNone(validate({"start": 570, "end": 577,
            "hook": "NPC traffic could finally get smarter!",
            "payoff_cue": 1}, cues, 674))

    def test_hook_retry_preserves_timestamps(self):
        cues = [{"start": 100, "end": 105, "text": "Setup."},
                {"start": 105, "end": 119, "text": "NPCs could call the police."}]
        candidate = {"start": 100, "end": 119, "payoff_cue": 1, "hook": "Hi"}
        response = Mock()
        response.json.return_value = {"choices":[{"message":{"content":'{"hook":"GTA 6 NPCs could call the police?!"}'}}]}
        with patch("smart_hooks.requests.post", return_value=response) as post:
            result = rewrite_invalid_hook(candidate, cues, "GTA6", "dummy")
        self.assertEqual(result["start"], 100)
        self.assertEqual(result["end"], 119)
        self.assertEqual(result["hook"], "GTA 6 NPCs could call the police?!")
        self.assertEqual(post.call_count, 1)
        self.assertIsNotNone(validate(result, cues, 130))

    def test_valid_hook_does_not_call_api(self):
        candidate = {"start": 100, "end": 119, "hook": "GTA 6 NPCs call the police?"}
        with patch("smart_hooks.requests.post") as post:
            self.assertIs(rewrite_invalid_hook(candidate, [], "GTA6", "dummy"), candidate)
        post.assert_not_called()

    def test_bad_rewrite_is_rejected_without_loop(self):
        cues = [{"start": 100, "end": 120, "text": "Police may arrive."}]
        candidate = {"start": 100, "end": 120, "hook": ""}
        response = Mock()
        response.json.return_value = {"choices":[{"message":{"content":'{"hook":"No"}'}}]}
        with patch("smart_hooks.requests.post", return_value=response) as post:
            result = rewrite_invalid_hook(candidate, cues, "GTA6", "dummy")
        self.assertEqual(result["hook"], "")
        self.assertEqual(post.call_count, 1)

    def test_fixed_windows_are_12_to_30_seconds(self):
        cues = []
        for n in range(12):
            cues.append({
                "start": n * 5.0, "end": n * 5.0 + 4.8,
                "text": "The NPC is doing something different and surprising right here."
            })
        windows = build_windows(cues, 65)
        self.assertTrue(windows)
        for window in windows:
            self.assertGreaterEqual(window["end"] - window["start"], 12)
            self.assertLessEqual(window["end"] - window["start"], 30)
            self.assertIn(window["payoff"], window["excerpt"])
            self.assertTrue(window["excerpt"].endswith("."))

    def test_ai_cannot_invent_timestamp(self):
        cues = []
        for n in range(7):
            cues.append({
                "start": n * 5.0, "end": n * 5.0 + 4.8,
                "text": "Something unexpected happened to the characters in GTA."
            })
        windows = build_windows(cues, 40)
        self.assertTrue(windows)
        answer = {"candidate_id": windows[0]["id"],
                  "start": 99999, "end": 100000,
                  "hook": "GTA NPCs react in a shocking way!",
                  "reason": "Full reaction"}
        chosen = choose_window(answer, windows)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["start"], windows[0]["start"])
        self.assertEqual(chosen["end"], windows[0]["end"])

    def test_ai_unknown_candidate_is_rejected(self):
        self.assertIsNone(choose_window({
            "candidate_id": 9999, "hook": "GTA NPCs have a surprising reaction!"
        }, [{"id": 1, "start": 12, "end": 30,
             "payoff_cue": 5, "payoff": "They escaped."}]))

    def test_far_from_sentence_end_rejected(self):
        cues = [{"start": 1, "end": 3, "text": "Setup."},
                {"start": 24, "end": 29, "text": "Payoff."}]
        self.assertIsNone(validate({"start": 1, "end": 20,
            "hook": "What if NPCs could call police?", "payoff_cue": 1}, cues, 32))

if __name__ == "__main__":
    unittest.main()
