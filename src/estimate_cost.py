"""Project the cost and time of full judge runs from a calibration run's measured usage.

    python src/estimate_cost.py data/day3/judgments/claude-opus-5-5
    python src/estimate_cost.py data/day3/judgments/gpt-5.6-sol

From the finished calibration judgments it measures output tokens per item (thinking or
reasoning included), seconds per item, and the ratio of real input tokens to characters/4.
It then prices every item of each target file. The first item about a source pays the input
rate on the shared prefix (prompt and source), or the cache-write rate where the prefix will
be cached; later items about the same source pay the cache-read rate on it; the citing
context and all output pay full rates. These are estimates, not quotes: output length varies.
"""
import argparse
import json
import statistics
from pathlib import Path

from judge_common import group_by_source, load_items
from judge_prompt import SYSTEM, context_block, source_block

TARGETS = ["data/day3/ci_inputs.jsonl", "data/day3/ojs_inputs.jsonl"]


def prices(model):
    """(USD per 1M tokens, whether every prompt over 1,024 tokens is cached automatically)."""
    if model.startswith("claude"):
        from judge_claude import PRICE
        return PRICE, False  # explicit cache_control, only on sources more than one item shares
    from judge_openai import price_for
    return price_for(model), True


def prefix_suffix_chars(item):
    pre = len(SYSTEM) + len(source_block(item["source_meta"], item["passages"], item["evidence"]))
    return pre, len(context_block(item["ctx"]))


def real_input_tokens(usage):
    if "cache_read_input_tokens" in usage:  # Anthropic: input_tokens excludes cached and written tokens
        return sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return usage.get("input_tokens") or 0      # OpenAI: input_tokens includes cached tokens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("judgments", help="folder of calibration judgments for one model")
    ap.add_argument("--calibration-inputs", default="data/day3/ci_inputs.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-cache-hits", action="store_true",
                    help="worst case: later items about a source miss the cache and pay the first item's rate")
    args = ap.parse_args()

    recs = [json.loads(p.read_text()) for p in Path(args.judgments).glob("*.json")]
    recs = [r for r in recs if r.get("usage") and (r["usage"].get("output_tokens") or 0) > 0]
    if not recs:
        raise SystemExit("no judgments with usage in " + args.judgments)
    model = recs[0]["model_requested"]
    price, auto_cache = prices(model)
    by_id = {it["item_id"]: it for it in load_items(args.calibration_inputs)}
    ratios = [real_input_tokens(r["usage"]) / (sum(prefix_suffix_chars(by_id[r["item_id"]])) / 4)
              for r in recs if r["item_id"] in by_id]
    ratio = statistics.mean(ratios) if ratios else 1.0
    out_tok = statistics.mean(r["usage"]["output_tokens"] for r in recs)
    secs = statistics.mean(r.get("seconds") or 0 for r in recs)
    spent = sum(r.get("cost_usd", 0) for r in recs)
    print(f"{model}: calibration {len(recs)} items, ${spent:.2f} (${spent / len(recs):.3f} per item); "
          f"{out_tok:,.0f} output tokens and {secs:.0f} s per item; real input tokens = {ratio:.2f} x chars/4")

    for target in TARGETS:
        items = load_items(target)
        groups = group_by_source(items)
        in_cost = 0.0
        for g in groups.values():
            cached = len(g) > 1 if not auto_cache else None
            for j, it in enumerate(g):
                pre, suf = prefix_suffix_chars(it)
                pre_t, suf_t = ratio * pre / 4, ratio * suf / 4
                if j == 0 or args.no_cache_hits:
                    write = (pre_t >= 1024) if auto_cache else cached
                    rate = price["cache_write"] if write else price["input"]
                else:
                    rate = price["cache_read"]
                in_cost += (rate * pre_t + price["input"] * suf_t) / 1e6
        out_cost = len(items) * out_tok * price["output"] / 1e6
        per_worker = sorted((len(g) for g in groups.values()), reverse=True)
        lanes = [0] * max(1, args.workers)  # groups run whole, one per worker, in order
        for n in per_worker:
            lanes[lanes.index(min(lanes))] += n
        hours = max(lanes) * secs / 3600
        print(f"  {target}: {len(items)} items, {len(groups)} sources -> about ${in_cost + out_cost:.2f} "
              f"(input ${in_cost:.2f}, output ${out_cost:.2f}); about {hours:.1f} h with {args.workers} workers")


if __name__ == "__main__":
    main()
