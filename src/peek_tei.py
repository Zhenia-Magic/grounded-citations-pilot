"""Show how GROBID labelled reference entries in a TEI file (debugging aid).

Usage: python src/peek_tei.py <article_id> [n_entries]
"""
import sys
from pathlib import Path

from defusedxml import ElementTree as ET

T = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
art, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8
root = ET.parse(Path("data/tei") / f"{art}.tei.xml").getroot()
bibls = root.findall(f".//{T}back//{T}listBibl/{T}biblStruct")
print(f"{art}: {len(bibls)} entries")
for i, b in enumerate(bibls[:n]):
    raw = b.find(f"{T}note[@type='raw_reference']")
    attrs = {k.split('}')[-1]: v for k, v in b.attrib.items()}
    label = b.find(f".//{T}label")
    print(f"[{i + 1}] attrs={attrs} label={label.text if label is not None else None!r}")
    print(f"     raw={(''.join(raw.itertext()) if raw is not None else '')[:140]!r}")
refs = [r for r in root.iter(f"{T}ref") if r.get("type") == "bibr"][:6]
for r in refs:
    print("callout", repr("".join(r.itertext())), "->", r.get("target"))
