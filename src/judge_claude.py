"""Day 3: run the Claude judge over a judge-input file (JSONL, one item per line).

    python src/judge_claude.py data/day3/ci_inputs.jsonl --limit 10 --budget 2
    python src/judge_claude.py data/day3/ci_inputs.jsonl --dry-run

- Model claude-opus-5-5, adaptive thinking (always on for this model), effort set explicitly.
- Strict JSON output via output_config.format, then the publication rules in judge_prompt.
- The cited source is the first, cached block. Items about the same source run in order
  in one worker, so later ones read it from cache (about 5% of the input price).
- Server-side refusal fallback is on. An item answered by a fallback model is kept but
  flagged, and the scorer leaves it out: an evaluation must not switch models silently.
- Stops starting new items once the running cost reaches --budget (USD).
- Credentials: an `ant auth login` sign-in, or ANTHROPIC_API_KEY (set in the git-ignored
  .env file), which overrides the sign-in. A free models call checks them before any paid call.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

from judge_common import Ledger, group_by_source, load_env, load_items
from judge_prompt import SCHEMA, SYSTEM, apply_rules, user_content

MODEL = "claude-opus-5-5"
PRICE = {"input": 4.00, "cache_write": 5.00, "cache_read": 0.20, "output": 20.00}  # USD per 1M tokens


def cost(u) -> float:
    return (PRICE["input"] * (u.get("input_tokens") or 0) + PRICE["cache_write"] * (u.get("cache_creation_input_tokens") or 0)
            + PRICE["cache_read"] * (u.get("cache_read_input_tokens") or 0) + PRICE["output"] * (u.get("output_tokens") or 0)) / 1e6


def request_params(item, effort):
    return dict(
        model=MODEL, max_tokens=16000, system=SYSTEM,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": user_content(item)}],
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    )


def judge(client, item, effort):
    t0 = time.time()
    resp = client.beta.messages.create(**request_params(item, effort))
    usage = {k: getattr(resp.usage, k, None) for k in
             ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")}
    fallback = any(getattr(e, "type", "") == "fallback_message" for e in (getattr(resp.usage, "iterations", None) or []))
    rec = {"item_id": item["item_id"], "model_requested": MODEL, "model_served": resp.model,
           "fallback_ran": fallback, "stop_reason": resp.stop_reason, "effort": effort,
           "usage": usage, "cost_usd": round(cost(usage), 5), "seconds": round(time.time() - t0, 1),
           "request_id": getattr(resp, "_request_id", None)}
    if resp.stop_reason == "refusal":
        details = getattr(resp, "stop_details", None)
        rec["refusal_category"] = getattr(details, "category", None)
        return rec
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        verdict = json.loads(text)
    except json.JSONDecodeError:
        rec["error"] = "invalid_json"
        rec["raw_text"] = text[:2000]
        return rec
    rec["verdict"] = verdict
    rec["final"] = apply_rules(verdict, "\n\n".join(item["passages"]), item["evidence"])
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=float, default=2.0, help="stop starting new items at this USD total")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    items = load_items(args.inputs, args.limit)
    out_dir = Path("data/day3/judgments") / MODEL
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [it for it in items if not (out_dir / f"{it['item_id']}.json").exists()]
    groups = group_by_source(todo)  # same source -> same worker, in order, for cache hits
    print(f"{len(items)} items, {len(todo)} to judge, {len(groups)} distinct sources, effort={args.effort}", flush=True)

    if args.dry_run:
        p = request_params(todo[0], args.effort) if todo else None
        if p:
            chars = sum(len(b["text"]) for b in p["messages"][0]["content"]) + len(p["system"])
            print(f"first request: ~{chars // 4:,} input tokens (chars/4); keys: {sorted(p)}")
            print(p["messages"][0]["content"][1]["text"][:600])
        return

    load_env()
    try:  # free: finds a credential (ANTHROPIC_API_KEY, or an `ant auth login` sign-in) before any paid call
        client = anthropic.Anthropic(max_retries=4)
        client.models.list(limit=1)
    except (anthropic.AnthropicError, TypeError) as e:
        print(f"Anthropic check failed, nothing judged: {type(e).__name__}: {str(e)[:200]}\n"
              "In Ubuntu, run `ant auth status`; sign in with `ant auth login` or set ANTHROPIC_API_KEY in .env.",
              flush=True)
        return
    ledger = Ledger(args.budget)

    def run_group(group):
        for it in group:
            if ledger.exhausted():
                return
            try:
                rec = judge(client, it, args.effort)
            except anthropic.AuthenticationError:
                print("authentication failed: run `ant auth status`, or check ANTHROPIC_API_KEY", flush=True)
                ledger.stop()
                return
            except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as e:
                print(f"  {it['item_id']}: {type(e).__name__}: {str(e)[:160]}", flush=True)
                continue
            ledger.add(rec["cost_usd"])
            (out_dir / f"{it['item_id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
            lab = (rec.get("final") or {}).get("final_label", rec.get("stop_reason"))
            print(f"  {it['item_id']:<40} {lab:<18} ${rec['cost_usd']:.4f}  total ${ledger.spent:.2f}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(run_group, groups.values()))
    print(f"done: spent ${ledger.spent:.2f}" + ("  (stopped early)" if ledger.exhausted() else ""), flush=True)


if __name__ == "__main__":
    main()
