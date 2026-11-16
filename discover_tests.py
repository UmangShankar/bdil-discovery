"""Regression checks for the discovery eligibility gate (no API calls)."""
import unittest
import yaml
import discover

class DiscoveryFiltersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("config.yaml", encoding="utf-8") as f:
            cls.cfg = yaml.safe_load(f)

    def test_gameplay_moment_is_accepted(self):
        self.assertTrue(discover.eligible_moment("GTA 6 NPCs cause chaos", self.cfg))
        self.assertTrue(discover.eligible_moment("GTA 6 police chase funny", self.cfg))

    def test_news_mods_and_unrelated_are_rejected(self):
        for title in (
            "GTA 6 NPCs explained",
            "GTA 6 Spider-Man physics fail",
            "GTA 6 leaked NPC trailer",
            "GTA 5 NPC chaos #gta6",
        ):
            with self.subTest(title=title):
                self.assertFalse(discover.eligible_moment(title, self.cfg))

    def test_non_latin_english_queue_filter(self):
        self.assertFalse(discover.eligible_moment("GTA6 人物角色NPC混乱", self.cfg))

    def test_metadata_only_does_not_override_rights(self):
        candidate = dict(id="yt:test", source="youtube", title="GTA 6 NPC chaos",
                         creator="Unknown Creator", url="https://www.youtube.com/watch?v=test",
                         published=discover.NOW,
                         views=5000, engagement=.1, outlier=1, lookback=48,
                         velocity_target=2000)
        rows = discover.score([candidate], self.cfg)
        self.assertEqual(len(rows), 1, "Expected a scored candidate to test rights handling")
        self.assertEqual(rows[0]["rights"], "check")

if __name__ == "__main__":
    unittest.main()
