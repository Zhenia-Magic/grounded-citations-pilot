"""Print a compact view of cached harvest results (debugging aid)."""
import json
import sys
from pathlib import Path

KEYS = ["status", "toolkit", "toolkit_version", "generator", "n_records", "pages",
        "tls_ok", "records_error", "capped"]
dirs = sorted(Path("data/raw/oai").iterdir())
for d in dirs:
    p = d / "result.json"
    if not p.exists():
        print(d.name, "(no result yet)")
        continue
    r = json.loads(p.read_text())
    print(d.name, {k: r.get(k) for k in KEYS if r.get(k) is not None})
if "--record" in sys.argv:
    for d in dirs:
        f = d / "records.json"
        if f.exists():
            recs = json.loads(f.read_text())
            if recs:
                print(f"\n{d.name}: {len(recs)} records; first one:")
                print(json.dumps(recs[0], ensure_ascii=False, indent=1)[:2000])
                break
