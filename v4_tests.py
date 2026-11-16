"""Offline regression tests for v4_local. Run: python -m unittest v4_tests.py"""
import unittest
from unittest.mock import patch
import v4_local

def cues():
    result=[]
    for i in range(80):
        text="We are driving around the city and looking at all the other cars."
        if i in (12, 35, 59):
            text="Wait what just happened? That NPC crashed and exploded!"
        result.append({"start":i*2.0,"end":i*2.0+1.9,"text":text})
    return result

class TestV4(unittest.TestCase):
    def test_no_network_or_api_key_needed(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY":""}):
            picks=v4_local.rank(cues(),160,limit=5)
        self.assertTrue(picks)
        self.assertLessEqual(len(picks),5)
        self.assertTrue(all(p["verification"]=="transcript-only" for p in picks))
        self.assertTrue(all(12 <= p["end"]-p["start"] <= 30.4 for p in picks))

    def test_non_overlapping(self):
        picks=v4_local.rank(cues(),160)
        for i,a in enumerate(picks):
            for b in picks[i+1:]:
                self.assertLessEqual(max(0,min(a["end"],b["end"])-max(a["start"],b["start"])),2)

    def test_optional_signal_is_not_zero_scored(self):
        with patch.object(v4_local,"audio_activity",return_value=([],[])):
            with patch.object(v4_local,"motion_activity",return_value=([],[])):
                picks=v4_local.rank(cues(),160,video="dummy.mp4")
        self.assertTrue(picks)
        self.assertTrue(all(0 <= p["score"] <= 100 for p in picks))

    def test_sponsor_penalty(self):
        base={"start":0,"end":20,"excerpt":"Wait! The NPC crashed into the car! That's insane!","payoff":"That's insane!"}
        ad={**base,"excerpt":base["excerpt"]+" Subscribe and use my discount code."}
        self.assertFalse(v4_local.text_signals(base)[-1])
        self.assertTrue(v4_local.text_signals(ad)[-1])

    def test_empty(self):
        self.assertEqual(v4_local.rank([],100),[])

if __name__=="__main__":
    unittest.main()
