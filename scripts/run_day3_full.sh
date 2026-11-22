#!/usr/bin/env bash
# Day 3 full runs for one judge: the Citation-Integrity benchmark, then the OJS citations,
# each with its own USD cap. Items already judged (the calibration) are skipped.
#   bash scripts/run_day3_full.sh claude 12 8
#   bash scripts/run_day3_full.sh gpt 10 4
set -euo pipefail
cd ~/ml/ojs-citation-pilot
mkdir -p data/day3/logs
judge=$1
ci_budget=$2
ojs_budget=$3
case "$judge" in
  claude) script=src/judge_claude.py ;;
  gpt) script=src/judge_openai.py ;;
  *) echo "judge must be claude or gpt" >&2; exit 2 ;;
esac
.venv/bin/python "$script" data/day3/ci_inputs.jsonl --budget "$ci_budget" 2>&1 | tee "data/day3/logs/full_${judge}_ci.log"
.venv/bin/python "$script" data/day3/ojs_inputs.jsonl --budget "$ojs_budget" 2>&1 | tee "data/day3/logs/full_${judge}_ojs.log"
