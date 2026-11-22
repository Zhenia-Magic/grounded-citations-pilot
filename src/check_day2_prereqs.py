"""Look up GROBID image sizes on Docker Hub and the Citation-Integrity corpus on GitHub (read-only)."""
import requests

UA = {"User-Agent": "ojs-citation-pilot/0.1 (academic research pilot)"}

for repo in ("grobid/grobid", "lfoppiano/grobid"):
    r = requests.get(f"https://hub.docker.com/v2/repositories/{repo}/tags",
                     params={"page_size": 8, "ordering": "last_updated"}, headers=UA, timeout=30)
    print(f"== {repo}: http {r.status_code}")
    if r.ok:
        for t in r.json().get("results", []):
            amd = [i for i in t.get("images", []) if i.get("architecture") == "amd64"]
            size = (amd[0]["size"] if amd else t.get("full_size") or 0) / 1e9
            print(f"  {t['name']:<14} {size:5.2f} GB compressed  updated {t.get('last_updated', '')[:10]}")

for repo in ("ScienceNLP-Lab/Citation-Integrity", "ScienceNLP-Lab/citation-integrity"):
    r = requests.get(f"https://api.github.com/repos/{repo}", headers=UA, timeout=30)
    print(f"== github {repo}: http {r.status_code}")
    if r.ok:
        d = r.json()
        print(f"  {d['html_url']}  size={d['size']} KB  license={(d.get('license') or {}).get('spdx_id')}  "
              f"pushed={d['pushed_at'][:10]}  desc={d.get('description')}")
        break
