"""P0 handoff contract tests; no Google or YouTube credentials."""
import unittest
from p0_gate import gate_rows, sync_changes

FIELDS = ["id","status","url","rights","hook","rights_evidence","rights_approved_by","rights_approved_at","youtube","clip_file"]
def row(**changes):
    r = dict.fromkeys(FIELDS, "")
    r.update(id="yt:test", status="to-cut", url="https://www.youtube.com/watch?v=test",
             rights="allowlisted", hook="NPCs fight back",
             rights_evidence="https://example.com/permission", rights_approved_by="editor",
             rights_approved_at="2026-11-16")
    r.update(changes)
    return [r[k] for k in FIELDS]

class P0Tests(unittest.TestCase):
    def test_valid_approval(self):
        result, held = gate_rows([FIELDS, row()])
        self.assertEqual(held, [])
        self.assertEqual(result[1][1], "to-cut")
    def test_gate_missing_editorial_inputs(self):
        for k,v in [("url",""),("hook","")]:
            with self.subTest(k=k):
                result, held = gate_rows([FIELDS, row(**{k:v})])
                self.assertTrue(held)
                self.assertEqual(result[1][1], "ready")
    def test_rights_are_optional_for_private_drafts(self):
        for k,v in [("rights","check"),("rights_evidence",""),("rights_approved_by",""),("rights_approved_at","")]:
            with self.subTest(k=k):
                output, held = gate_rows([FIELDS, row(**{k:v})])
                self.assertFalse(held)
                self.assertEqual(output[1][1], "to-cut")
    def test_missing_columns_rejected(self):
        with self.assertRaises(ValueError):
            gate_rows([["id","status"],["yt:test","to-cut"]])
    def test_uploaded_url_roundtrip(self):
        out = sync_changes([FIELDS,row()], {"yt:test":{"status":"uploaded",
            "youtube":"https://youtube.com/shorts/abc","clip_file":"ready/abc.mp4"}})
        self.assertIn((2,"youtube","https://youtube.com/shorts/abc"),out)
        self.assertIn((2,"clip_file","ready/abc.mp4"),out)
        self.assertEqual(out[-1],(2,"status","uploaded"))
    def test_uploaded_without_url_blocked(self):
        self.assertEqual(sync_changes([FIELDS,row()],{"yt:test":{"status":"uploaded"}}),[])
    def test_no_regression(self):
        self.assertEqual(sync_changes([FIELDS,row(status="uploaded")],
                           {"yt:test":{"status":"clipped"}}),[])
    def test_final_row_unmodified(self):
        self.assertEqual(sync_changes([FIELDS,row(status="skipped")],
                           {"yt:test":{"status":"uploaded"}}),[])

if __name__ == "__main__":
    unittest.main()
