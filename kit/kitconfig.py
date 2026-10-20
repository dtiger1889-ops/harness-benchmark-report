"""Shared settings for the kit. Every script imports this instead of carrying its own paths.

Settings come from a JSON file: the path in the KIT_CONFIG environment variable, or kit_config.json next to
this file. Copy kit_config.example.json to start. Keys:

  root            folder that holds packets/, judge_only/ and results/ (your benchmark workspace)
  trials_dir      empty folder where each trial runs; must be outside root, so a trial cannot reach the
                  results, the judge-only evidence or other trials through git or a parent-folder listing
  done_dir        where finished trials move (outside root and outside trials_dir)
  worker_model    model id passed to the CLI for worker trials
  judge_model     model id for the judge
  judge_effort    effort level for the judge (low, medium, high, xhigh, max)
  claude_cmd      the CLI command, as a list (e.g. ["claude"])
  forbidden_launch_roots   folders the judge must never be launched from (add your own workspace)
  leak_patterns   extra regular expressions; a worker tool call matching any of them voids the trial
                  (put your own private folders here)
  benign_prefixes folders outside the trial copy that a worker may touch without voiding the trial
                  (tool installs); compared as lower-case forward-slash prefixes
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
_cfg_path = Path(os.environ.get("KIT_CONFIG") or HERE / "kit_config.json")
if not _cfg_path.exists():
    raise SystemExit(f"kit config not found: {_cfg_path} (copy kit_config.example.json to kit_config.json)")
CFG = json.loads(_cfg_path.read_text(encoding="utf-8"))

ROOT = Path(CFG["root"]).resolve()
TRIALS = Path(CFG["trials_dir"]).resolve()
DONE = Path(CFG["done_dir"]).resolve()
WORKER_MODEL = CFG["worker_model"]
JUDGE_MODEL = CFG["judge_model"]
JUDGE_EFFORT = CFG.get("judge_effort", "high")
CLAUDE_CMD = list(CFG.get("claude_cmd", ["claude"]))
FORBIDDEN_LAUNCH_ROOTS = [str(ROOT)] + list(CFG.get("forbidden_launch_roots", []))
LEAK_PATTERNS = list(CFG.get("leak_patterns", []))
BENIGN_PREFIXES = tuple(p.lower().replace("\\", "/").rstrip("/") for p in CFG.get("benign_prefixes", []))

PACKETS_DIR = ROOT / "packets"
JUDGE_ONLY = ROOT / "judge_only"
RESULTS = ROOT / "results"
RUNS_FILE = ROOT / "runs.json"

for _inner in (TRIALS, DONE):
    if _inner == ROOT or ROOT in _inner.parents:
        raise SystemExit(f"{_inner} is inside root {ROOT}: trials must run outside the benchmark workspace")


def packets() -> dict:
    """Every packet under root/packets/<id>/packet.json, keyed by its id (the folder name)."""
    out = {}
    if PACKETS_DIR.is_dir():
        for d in sorted(PACKETS_DIR.iterdir()):
            f = d / "packet.json"
            if f.is_file():
                cfg = json.loads(f.read_text(encoding="utf-8"))
                cfg["dir"] = d
                cfg.setdefault("project", ".")
                cfg.setdefault("drops", [])
                cfg.setdefault("facts", {})
                cfg.setdefault("kind", "write-up")
                cfg["rubric"] = d / cfg.get("rubric", "judge_rubric.md")
                cfg["evidence"] = JUDGE_ONLY / d.name
                out[d.name] = cfg
    return out
