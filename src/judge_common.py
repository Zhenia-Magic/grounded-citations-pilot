"""Pieces shared by the judge clients (judge_claude.py, judge_openai.py): .env loading,
the budget ledger, reading judge inputs, and grouping items by cited source so that
requests about the same source run in order in one worker and reuse the cached prefix."""
import hashlib
import json
import os
import threading
from collections import defaultdict
from pathlib import Path


def load_env(path=Path(".env")):
    """Set variables from the git-ignored .env file without overriding the environment.
    Empty values are skipped, because an empty ANTHROPIC_API_KEY would still outrank an
    `ant auth login` sign-in. utf-8-sig and strip() also accept a file saved by Notepad."""
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip().strip("\"'")
                if v:
                    os.environ.setdefault(k.strip(), v)


class Ledger:
    """Running cost in USD. Workers stop starting new items once the budget is reached
    or after a fatal error (bad key, rejected request, no credit)."""

    def __init__(self, budget):
        self.budget, self.spent, self.stopped = budget, 0.0, False
        self.lock = threading.Lock()

    def add(self, usd):
        with self.lock:
            self.spent += usd

    def stop(self):
        with self.lock:
            self.stopped = True

    def exhausted(self):
        with self.lock:
            return self.stopped or self.spent >= self.budget


def load_items(path, limit=0):
    items = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    return items[:limit] if limit else items


def source_key(item):
    return hashlib.sha1("\n".join(item["passages"]).encode()).hexdigest()


def group_by_source(items):
    """Same source -> same group, in input order. Also records whether a source is read by
    more than one item, because a cache write pays off only on reuse."""
    groups = defaultdict(list)
    for it in items:
        groups[source_key(it)].append(it)
    for g in groups.values():
        for it in g:
            it["cache"] = len(g) > 1
    return groups
