"""Day 3: run the second judge, an OpenAI model, over a judge-input file (JSONL).

    python src/judge_openai.py data/day3/ci_inputs.jsonl --limit 10 --budget 2   # calibration
    python src/judge_openai.py data/day3/ci_inputs.jsonl --dry-run

Same prompt, output schema and publication rules as the Claude judge (judge_prompt.py);
only the client differs. The design asks for two judges from different model families to
agree before any negative note, and score_benchmark.py scores that agreement rule.

- Responses API with the reasoning effort set explicitly and strict JSON via text.format.
- The prompt goes in as a developer message at the start of the input, then the cited
  source, then the citing context. GPT-6.2 models append top-level `instructions` after
  the input and bill them uncached on every call, so the stable prompt stays first, where
  it is part of the cached prefix. Caching is automatic above 1,024 tokens; items about
  the same source run in order in one worker so later ones read the cached prefix.
- store=False: OpenAI does not keep the responses for later retrieval.
- If the API serves another model than the one requested, the record is flagged like a
  fallback and the scorer leaves it out: an evaluation must not switch models silently.
- Stops starting new items once the running cost reaches --budget (USD).
- The API key comes from OPENAI_API_KEY, which the git-ignored .env file may set.
"""
import argparse
import datetime
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import openai

from judge_common import Ledger, group_by_source, load_env, load_items, source_key
from judge_prompt import SCHEMA, SYSTEM, apply_rules, context_block, source_block

DEFAULT_MODEL = "gpt-6.2-sol"  # OpenAI's everyday model, at half GPT-5.6 Sol's promotional price; gpt-6.2-astra is its flagship
# USD per 1M tokens, standard tier, prompts under 272K tokens (ours stay under 40K), from
# OpenAI's pricing page on 2026-11-21. From GPT-5.6 on, cache writes are billed (30-minute
# retention, 1.25x input). GPT-5.6 Sol's rate is promotional: see price_for.
PRICES = {
    "gpt-6.2-astra": {"input": 8.00, "cache_write": 10.00, "cache_read": 0.40, "output": 40.00},
    "gpt-6.2-sol": {"input": 2.00, "cache_write": 2.50, "cache_read": 0.10, "output": 10.00},
    "gpt-5.6-sol": {"input": 4.00, "cache_write": 5.00, "cache_read": 0.40, "output": 20.00},
    "gpt-5.5": {"input": 5.00, "cache_write": 5.00, "cache_read": 0.50, "output": 30.00},
}
# OpenAI lists Sol's promotional rate until 30 November 2026 and publishes no rate for after
# it. The announcement called it a 20% input and 33% output cut, which implies $5 and $30
# before; the ledger assumes that from 1 December, so the budget cap errs high, not low.
SOL_PROMO_ENDS = datetime.date(2026, 11, 30)
SOL_AFTER_PROMO = {"input": 5.00, "cache_write": 6.25, "cache_read": 0.50, "output": 30.00}


def price_for(model, today=None):
    if model == "gpt-5.6-sol" and (today or datetime.date.today()) > SOL_PROMO_ENDS:
        return SOL_AFTER_PROMO
    return PRICES[model]
MAX_OUTPUT_TOKENS = 25000  # reasoning plus the JSON answer; OpenAI suggests reserving at least 25K


def usage_of(resp) -> dict:
    u = resp.usage
    inp = getattr(u, "input_tokens_details", None)
    out = getattr(u, "output_tokens_details", None)
    return {"input_tokens": getattr(u, "input_tokens", None),
            "cached_tokens": getattr(inp, "cached_tokens", None),
            "cache_write_tokens": getattr(inp, "cache_write_tokens", None),
            "output_tokens": getattr(u, "output_tokens", None),
            "reasoning_tokens": getattr(out, "reasoning_tokens", None)}


def cost(u: dict, price: dict) -> float:
    """Uncached input at the input rate, cache reads and writes at theirs, reasoning and
    visible output at the output rate. If the response does not report cache writes, all
    uncached input is charged as a write, so the ledger errs high rather than low."""
    inp, read = u.get("input_tokens") or 0, u.get("cached_tokens") or 0
    write = u.get("cache_write_tokens")
    if write is None:
        write = max(0, inp - read)
    plain = max(0, inp - read - write)
    return (price["input"] * plain + price["cache_write"] * write + price["cache_read"] * read
            + price["output"] * (u.get("output_tokens") or 0)) / 1e6


def request_params(item, model, effort):
    source = source_block(item["source_meta"], item["passages"], item["evidence"])
    return dict(
        model=model,
        input=[
            {"role": "developer", "content": SYSTEM},
            {"role": "user", "content": [{"type": "input_text", "text": source},
                                         {"type": "input_text", "text": context_block(item["ctx"])}]},
        ],
        reasoning={"effort": effort},
        text={"format": {"type": "json_schema", "name": "citation_verdict", "schema": SCHEMA, "strict": True}},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        store=False,
        prompt_cache_key=f"ojs-pilot-{source_key(item)[:16]}",
    )


def refusal_text(resp):
    for o in resp.output or []:
        if getattr(o, "type", "") == "message":
            for part in getattr(o, "content", None) or []:
                if getattr(part, "type", "") == "refusal":
                    return getattr(part, "refusal", "") or ""
    return None


def judge(client, item, model, effort):
    t0 = time.time()
    resp = client.responses.create(**request_params(item, model, effort))
    usage = usage_of(resp)
    served = getattr(resp, "model", "") or ""
    rec = {"item_id": item["item_id"], "model_requested": model, "model_served": served,
           "fallback_ran": not served.startswith(model), "stop_reason": resp.status, "effort": effort,
           "usage": usage, "cost_usd": round(cost(usage, price_for(model)), 5),
           "seconds": round(time.time() - t0, 1), "request_id": getattr(resp, "_request_id", None)}
    refusal = refusal_text(resp)
    if refusal is not None:  # a refusal need not follow the schema, so check it before parsing
        rec["stop_reason"], rec["refusal_text"] = "refusal", refusal[:500]
        return rec
    if resp.status != "completed":
        rec["error"] = "incomplete"
        rec["incomplete_reason"] = getattr(getattr(resp, "incomplete_details", None), "reason", None)
        return rec
    text = resp.output_text or ""
    try:
        verdict = json.loads(text)
    except json.JSONDecodeError:
        rec["error"], rec["raw_text"] = "invalid_json", text[:2000]
        return rec
    rec["verdict"] = verdict
    rec["final"] = apply_rules(verdict, "\n\n".join(item["passages"]), item["evidence"])
    return rec


def check_strict(schema):
    """Strict structured outputs need additionalProperties false and every property required."""
    if schema.get("type") == "object":
        props = schema.get("properties", {})
        assert schema.get("additionalProperties") is False, "strict mode needs additionalProperties: false"
        assert set(schema.get("required", [])) == set(props), "strict mode needs every property in required"
        for p in props.values():
            check_strict(p)
    elif schema.get("type") == "array":
        check_strict(schema.get("items", {}))


def check_sdk_accepts(params):
    """Catch a parameter this SDK version does not know before any paid call."""
    try:
        import inspect
        from openai.resources.responses import Responses
    except ImportError:
        return "SDK signature check skipped"
    known = inspect.signature(Responses.create).parameters
    unknown = [k for k in params if k not in known]
    assert not unknown, f"openai {openai.__version__} does not accept: {unknown}"
    return f"openai {openai.__version__} accepts all request parameters"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs")
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(PRICES))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=float, default=2.0, help="stop starting new items at this USD total")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    items = load_items(args.inputs, args.limit)
    out_dir = Path("data/day3/judgments") / args.model
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [it for it in items if not (out_dir / f"{it['item_id']}.json").exists()]
    groups = group_by_source(todo)  # same source -> same worker, in order, for cache hits
    print(f"{len(items)} items, {len(todo)} to judge, {len(groups)} distinct sources, "
          f"model={args.model}, effort={args.effort}", flush=True)
    print(f"ledger prices, USD per 1M tokens: {price_for(args.model)}", flush=True)

    if args.dry_run:
        check_strict(SCHEMA)
        print("schema fits strict structured outputs")
        if todo:
            p = request_params(todo[0], args.model, args.effort)
            print(check_sdk_accepts(p))
            chars = len(p["input"][0]["content"]) + sum(len(b["text"]) for b in p["input"][1]["content"])
            print(f"first request: ~{chars // 4:,} input tokens (chars/4); keys: {sorted(p)}")
            print(p["input"][1]["content"][1]["text"][:600])
        return

    load_env()
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set: paste your key into .env after OPENAI_API_KEY=", flush=True)
        return
    client = openai.OpenAI(max_retries=4, timeout=900)
    try:  # free: checks the key, and that this account can use the model, before any paid call
        client.models.retrieve(args.model)
    except openai.OpenAIError as e:
        print(f"OpenAI check failed, nothing judged: {type(e).__name__}: {str(e)[:200]}", flush=True)
        return
    ledger = Ledger(args.budget)

    def run_group(group):
        for it in group:
            if ledger.exhausted():
                return
            try:
                rec = judge(client, it, args.model, args.effort)
            except openai.AuthenticationError:
                print("authentication failed: check OPENAI_API_KEY", flush=True)
                ledger.stop()
                return
            except openai.BadRequestError as e:  # a rejected schema or parameter fails the same way for every item
                print(f"request rejected, stopping: {str(e)[:300]}", flush=True)
                ledger.stop()
                return
            except openai.RateLimitError as e:
                if getattr(e, "code", None) == "insufficient_quota":
                    print("the OpenAI account has no credit left: stopping", flush=True)
                    ledger.stop()
                    return
                print(f"  {it['item_id']}: RateLimitError: {str(e)[:160]}", flush=True)
                continue
            except (openai.APIStatusError, openai.APIConnectionError) as e:
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
