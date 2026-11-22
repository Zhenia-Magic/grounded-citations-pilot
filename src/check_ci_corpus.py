"""List the Citation-Integrity repository's layout and file sizes via the GitHub API (read-only)."""
import requests

from harvest_oai import UA

BASE = "https://api.github.com/repos/ScienceNLP-Lab/Citation-Integrity"
H = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
repo = requests.get(BASE, headers=H, timeout=30).json()
branch = repo.get("default_branch", "main")
tree = requests.get(f"{BASE}/git/trees/{branch}", params={"recursive": "1"}, headers=H, timeout=60).json()
items = tree.get("tree", [])
print(f"branch={branch} entries={len(items)} truncated={tree.get('truncated')}")
dirs = {}
for it in items:
    top = it["path"].split("/")[0]
    dirs.setdefault(top, [0, 0])
    if it["type"] == "blob":
        dirs[top][0] += 1
        dirs[top][1] += it.get("size", 0)
for d, (n, size) in sorted(dirs.items(), key=lambda x: -x[1][1]):
    print(f"{d:<40} files={n:<5} {size / 1e6:8.1f} MB")
for it in items:
    if it["type"] == "blob" and any(k in it["path"].lower() for k in ("data", "corpus", "annot", ".json", ".tsv", ".csv")):
        print(f"  {it['path']:<80} {it.get('size', 0) / 1e3:9.1f} KB")
