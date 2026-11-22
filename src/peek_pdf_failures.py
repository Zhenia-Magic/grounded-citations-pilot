"""Show what was tried for articles whose PDF could not be fetched (debugging aid)."""
import json
from pathlib import Path

for p in sorted(Path("data/raw/pdf").glob("*.json")):
    m = json.loads(p.read_text())
    if m["status"] != "ok":
        print(f"\n{m['article_id']}  status={m['status']}")
        for url, note in m.get("tried", [])[:6]:
            print(f"   {note!s:<28} {url[:120]}")
