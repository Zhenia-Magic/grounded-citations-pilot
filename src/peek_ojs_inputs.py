"""Print one full-text and one abstract-only judge input, shortened (debugging aid)."""
import json
from pathlib import Path

items = [json.loads(l) for l in Path("data/day3/ojs_inputs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
for ev in ("full_text", "abstract"):
    it = next(i for i in items if i["evidence"] == ev and i["lang_stratum"] == "EN")
    print(f"== {ev}: {it['item_id']}  link_check={it['link_check']}")
    print("sentence:", it["ctx"]["sentence"][:300])
    print("source:", it["source_meta"][:200])
    print(f"passages: {len(it['passages'])}, chars {sum(map(len, it['passages']))}; first: {it['passages'][0][:250]!r}\n")
