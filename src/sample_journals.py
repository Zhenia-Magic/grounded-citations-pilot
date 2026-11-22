"""Draw a stratified random sample of OJS-style journals from the DOAJ journal CSV.

Frame: DOAJ journals whose homepage URL has the multi-journal OJS form
/index.php/<journal-path>. That misses OJS installs that hide index.php and
lets in a few non-OJS sites; the harvester confirms OJS from each OAI
Identify response.

Strata: language (EN = accepts English but not Spanish; ES = accepts Spanish)
x field group (from the journal's first LCC code). We draw OVERSAMPLE x the
quota as a ranked candidate list, because many endpoints fail or are
inactive; the summariser keeps the first valid journals in rank order.

Usage: python src/sample_journals.py data/raw/doaj/<doaj csv>
"""
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

SEED = 20261121
OVERSAMPLE = 4
QUOTA = {
    ("EN", "health"): 5, ("EN", "scitech"): 5, ("EN", "social"): 5, ("EN", "humanities"): 5,
    ("ES", "health"): 2, ("ES", "scitech"): 2, ("ES", "social"): 3, ("ES", "humanities"): 3,
}
BASE_RE = re.compile(r"^(https?://[^/?#]+(?:/[^/?#]+)*?/index\.php/([^/?#]+))", re.I)


def field_group(lcc: str):
    first = (lcc or "").split("|")[0].strip().upper()
    if not first:
        return None
    if first.startswith("BF"):  # LCC files psychology under B; treat it as social science
        return "social"
    letter = first[0]
    if letter == "R":
        return "health"
    if letter in "QSTUV":
        return "scitech"
    if letter in "HJKLG":
        return "social"
    if letter in "ABCDEFMNPZ":
        return "humanities"
    return None


def lang_stratum(langs: str):
    names = {x.strip().lower() for x in (langs or "").split(",")}
    if "spanish" in names:
        return "ES"
    if "english" in names:
        return "EN"
    return None


def main(csv_path: str) -> None:
    out = Path("data/sample")
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    n_doaj = len(df)

    m = df["Journal URL"].str.strip().str.extract(BASE_RE)
    df["base_url"] = m[0].str.rstrip("/")
    df["journal_path"] = m[1]
    frame = df[df["base_url"].notna() & (df["journal_path"].str.lower() != "index")].copy()
    n_ojs_style = len(frame)
    frame = frame.drop_duplicates("base_url")
    frame["lang"] = frame["Languages in which the journal accepts manuscripts"].map(lang_stratum)
    frame["field"] = frame["LCC Codes"].map(field_group)
    frame["oai_url"] = frame["base_url"] + "/oai"

    counts = (frame.groupby(["lang", "field"], dropna=False).size()
              .rename("n").reset_index())
    rng = random.Random(SEED)
    rows = []
    for (lang, field), quota in QUOTA.items():
        pool = frame[(frame["lang"] == lang) & (frame["field"] == field)]
        idx = list(pool.index)
        rng.shuffle(idx)
        for rank, i in enumerate(idx[: quota * OVERSAMPLE], start=1):
            r = frame.loc[i]
            rows.append({
                "lang": lang, "field": field, "rank": rank, "quota": quota,
                "title": r["Journal title"], "base_url": r["base_url"], "oai_url": r["oai_url"],
                "country": r["Country of publisher"],
                "languages": r["Languages in which the journal accepts manuscripts"],
                "lcc": r["LCC Codes"], "subjects": r["Subjects"],
                "eissn": r["Journal EISSN (online version)"], "issn": r["Journal ISSN (print version)"],
                "license": r["Journal license"], "pids": r["Persistent article identifiers"],
                "doaj_url": r["URL in DOAJ"], "doaj_article_records": r["Number of Article Records"],
                "doaj_most_recent_article": r["Most Recent Article Added"],
            })
    cands = pd.DataFrame(rows)
    cands.to_csv(out / "candidates.csv", index=False)

    summary = {
        "doaj_csv": Path(csv_path).name, "seed": SEED, "oversample": OVERSAMPLE,
        "doaj_journals": n_doaj, "ojs_style_urls": n_ojs_style, "frame_after_dedup": len(frame),
        "frame_en": int((frame["lang"] == "EN").sum()), "frame_es": int((frame["lang"] == "ES").sum()),
        "strata": {f"{r.lang}/{r.field}": int(r.n) for r in counts.itertuples()
                   if isinstance(r.lang, str) and isinstance(r.field, str)},
        "candidates": len(cands),
    }
    (out / "frame_counts.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    print(cands.groupby(["lang", "field"]).size())
    print("distinct hosts among candidates:",
          cands["oai_url"].str.extract(r"^https?://([^/]+)")[0].str.lower().nunique())


if __name__ == "__main__":
    main(sys.argv[1])
