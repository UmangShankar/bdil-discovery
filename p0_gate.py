"""Fail-closed editorial gate and status reconciliation, testable without credentials."""
from urllib.parse import urlparse

REQUIRED = ("status", "url", "rights", "hook", "rights_evidence", "rights_approved_by", "rights_approved_at")
ORDER = {"": 0, "ready": 1, "to-cut": 2, "in-progress": 3, "clipped": 4, "uploaded": 5}
FINAL = {"skipped", "expired", "filtered"}

def evidence_valid(value):
    value = (value or "").strip()
    if value.startswith("owned:") and len(value.partition(":")[2].strip()) >= 8:
        return True
    p = urlparse(value)
    return p.scheme in ("http", "https") and bool(p.netloc)

def approval_error(row):
    if row.get("rights", "").strip().lower() != "allowlisted":
        return "creator not allowlisted"
    if not row.get("url", "").strip():
        return "source URL missing"
    if not row.get("hook", "").strip():
        return "editorial hook missing"
    if "SPOILER" in (row.get("flags") or "").upper():
        return "spoiler"
    if not evidence_valid(row.get("rights_evidence", "")):
        return "rights evidence missing (http(s) URL or owned: reference)"
    if not row.get("rights_approved_by", "").strip():
        return "approver missing"
    if not row.get("rights_approved_at", "").strip():
        return "approval date missing"
    return None

def gate_rows(rows):
    if not rows:
        raise ValueError("Missing Sheet header")
    head = rows[0]
    missing = [c for c in REQUIRED if c not in head]
    if missing:
        raise ValueError("Missing approval columns: " + ", ".join(missing))
    output, held = [list(head)], []
    for line, raw in enumerate(rows[1:], 2):
        values = list(raw) + [""] * (len(head) - len(raw))
        row = dict(zip(head, values))
        if row["status"].strip() == "to-cut":
            reason = approval_error(row)
            if reason:
                values[head.index("status")] = "ready"
                held.append(f"row {line}: {reason}")
        output.append(values)
    return output, held

def sync_changes(remote, local):
    if not remote:
        return []
    head = remote[0]
    missing = {"id", "status", "youtube", "clip_file"} - set(head)
    if missing:
        raise ValueError("Missing output columns: " + ", ".join(sorted(missing)))
    updates = []
    for line, raw in enumerate(remote[1:], 2):
        row = dict(zip(head, list(raw) + [""] * (len(head) - len(raw))))
        changed = local.get(row["id"])
        if not changed:
            continue
        old, new = row["status"], (changed.get("status") or "").strip()
        if old in FINAL or old == "uploaded":
            continue
        if not (new in FINAL or new in ORDER and ORDER[new] > ORDER.get(old, 99)):
            continue
        if new == "uploaded" and not (changed.get("youtube") or "").startswith("https://youtube.com/shorts/"):
            continue
        for col in ("youtube", "clip_file"):
            value = (changed.get(col) or "").strip()
            if value and not row.get(col):
                updates.append((line, col, value))
        updates.append((line, "status", new))
    return updates
