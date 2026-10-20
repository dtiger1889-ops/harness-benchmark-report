"""One blind pairwise judge call (one presentation order).

Usage:
  python run_judge.py --packet-x <x.json> --packet-y <y.json> --rubric <judge_rubric.md>
                      --evidence <judge_only/<id> dir> --order xy|yx --out <result.json>
                      [--checks-x <json> --checks-y <json>]   # results of the packet's grading script, if any
                      [--model <id>] [--effort high] [--allow-cues] [--dry-run]

One blind model judge, both orders, ties allowed; essential (must-pass) checks first, then preference.
x is the harness side and y the comparison side by convention of the driver; the judge never sees which.

Launch:
  - from a fresh empty temp folder outside the workspace root and every forbidden_launch_roots folder
  - `claude -p --model <m> --effort <e> --setting-sources project,local --strict-mcp-config
     --tools "" --no-chrome --output-format json --verbose --no-session-persistence`
  - `--tools ""` is the CLI's documented way to disable every built-in tool; the init event's tool
    list is recorded as proof. ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN are removed from the child env.
  - prompt goes in on stdin, never as a positional argument.
Sides are shown only as "Submission 1" / "Submission 2"; order xy puts x first. The verdict is mapped
back to x/y. A malformed judge reply is recorded as missing, never coerced.
Cost: total tokens from the run's final result record (input + output + cache read + cache write).
Writes <out> plus <out stem>.prompt.txt, .raw.json, .assistant.jsonl beside it, and appends one receipt
per model call to results/judge_ledger.jsonl.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # the driver runs scripts with python -I
import kitconfig  # noqa: E402

FORBIDDEN_LAUNCH_ROOTS = kitconfig.FORBIDDEN_LAUNCH_ROOTS
LEDGER = str(kitconfig.RESULTS / "judge_ledger.jsonl")  # every judge call, append-only
VERDICTS = {"pass", "fail"}
PREFS = {"1", "2", "tie"}
CONF = {"low", "medium", "high"}


def rubric_ids(text, key):
    m = re.search(r"<!--\s*%s:\s*([^>]*?)\s*-->" % key, text)
    if not m or m.group(1).strip().lower() == "none":
        return []
    return [x.strip() for x in m.group(1).split(",") if x.strip()]


def read_evidence(d):
    parts, names = [], []
    for fn in sorted(os.listdir(d)):
        p = os.path.join(d, fn)
        if not os.path.isfile(p):
            continue  # top level only: fixtures/ and packet folders are never evidence
        with open(p, "rb") as f:
            b = f.read()
        if b"\x00" in b[:8192]:
            continue
        t = b.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
        # Same masking as the packets: evidence must not name either arm's notes layout.
        t = re.sub(r"`?(?:[A-Za-z0-9_.~\-]+[/\\])*(?:(?i:checkpoint\.md|claude\.md)|CHECKPOINT)`?",
                   "the project notes file", t)
        t = re.sub(r"(?i)harness changelog", "changelog", t)
        names.append(fn)
        parts.append("=== Evidence file: %s ===\n%s%s=== End of evidence file: %s ===\n"
                     % (fn, t, "" if t.endswith("\n") else "\n", fn))
    return names, "\n".join(parts)


def automated_verdicts(obj, ids):
    """Read pass/fail per check id from a check script's JSON. Returns {id: 'pass'|'fail'|None}."""
    src = obj.get("checks", obj) if isinstance(obj, dict) else {}
    out = {}
    for i in ids:
        v = src.get(i)
        if isinstance(v, dict):
            v = v.get("verdict", v.get("result", v.get("pass")))
        if isinstance(v, bool):
            v = "pass" if v else "fail"
        v = str(v).lower() if v is not None else None
        out[i] = v if v in VERDICTS else None
    return out


def build_prompt(rubric, judge_ids, auto_ids, evidence, s1, s2, auto1, auto2):
    if judge_ids:
        step1 = ("1. For each submission, decide every essential check (%s) as \"pass\" or \"fail\", with one "
                 "short sentence of evidence." % ", ".join(judge_ids))
        decided = [i for i in auto_ids if i not in judge_ids]
        if decided:
            step1 += (" The checking script could not decide these for at least one submission, so decide them "
                      "for both from the code. The other essential checks (%s) were decided by the script; "
                      "their results are given below; do not re-decide them." % ", ".join(decided))
        ec = ",\n".join('      "%s": {"verdict": "pass" or "fail", "evidence": "one sentence"}' % i for i in judge_ids)
        schema_checks = '    "submission_1": {\n%s\n    },\n    "submission_2": { same keys }' % ec
    else:
        step1 = ("1. The essential checks (%s) were decided by an automated script; their results are given "
                 "below. Do not re-decide them. Return empty objects for essential_checks." % ", ".join(auto_ids))
        schema_checks = '    "submission_1": {},\n    "submission_2": {}'
    auto_block = ""
    if auto_ids:
        auto_block = ("\n<AUTOMATED_ESSENTIAL_CHECKS>\nSubmission 1: %s\nSubmission 2: %s\n</AUTOMATED_ESSENTIAL_CHECKS>\n"
                      % (json.dumps(auto1, ensure_ascii=False), json.dumps(auto2, ensure_ascii=False)))
    return f"""You are the blind judge in a benchmark of AI agent work on real software projects.

Two submissions each received the same task on identical frozen copies of one project. You see only the
files each submission created or changed: new files in full, edited files as diffs against the frozen copy.
You do not know how either submission was produced; do not guess, and do not let a guess influence you.
Judge the work, not the author. Presentation order means nothing.

You have no tools. Everything you may use is in this message: the rubric (with the task brief and the
project facts), the reference evidence, and the two submissions.

Order of work:
{step1}
2. Then decide which submission is better overall using the rubric's preference dimensions. A submission
   that fails any essential check cannot be preferred over one that passes all of them. "tie" is allowed
   and expected when the two are equally good. Length is not quality.
3. Return the JSON answer.

<RUBRIC>
{rubric.strip()}
</RUBRIC>

<REFERENCE_EVIDENCE>
What actually came next in the real project. Valid alternatives are acceptable; this is evidence, not
the only acceptable answer.

{evidence.strip()}
</REFERENCE_EVIDENCE>

<SUBMISSION_1>
{s1.strip()}
</SUBMISSION_1>

<SUBMISSION_2>
{s2.strip()}
</SUBMISSION_2>
{auto_block}
Answer format: return ONLY one JSON object, with no code fence and no text before or after it:
{{
  "essential_checks": {{
{schema_checks}
  }},
  "preference": "1" or "2" or "tie",
  "confidence": "low" or "medium" or "high",
  "reason": "one paragraph naming the deciding differences"
}}
"""


def parse_events(stdout):
    s = stdout.strip()
    try:
        d = json.loads(s)
        return d if isinstance(d, list) else [d]
    except Exception:
        pass
    ev = []
    for line in s.splitlines():
        try:
            ev.append(json.loads(line))
        except Exception:
            continue
    return ev


def parse_verdict(text, judge_ids):
    """Strict: the reply must be one JSON object (a single surrounding code fence is tolerated).
    Returns (obj, None) or (None, reason). Nothing is coerced."""
    if not isinstance(text, str) or not text.strip():
        return None, "empty result"
    t = text.strip()
    m = re.fullmatch(r"```(?:json)?\s*\n(.*)\n```", t, re.S)
    if m:
        t = m.group(1).strip()
    try:
        obj = json.loads(t)
    except Exception as e:
        return None, "not JSON: %s" % e
    if not isinstance(obj, dict):
        return None, "not a JSON object"
    for k in ("essential_checks", "preference", "confidence", "reason"):
        if k not in obj:
            return None, "missing key %s" % k
    ec = obj["essential_checks"]
    if not isinstance(ec, dict) or set(ec) != {"submission_1", "submission_2"}:
        return None, "essential_checks must hold exactly submission_1 and submission_2"
    for side in ("submission_1", "submission_2"):
        if not isinstance(ec[side], dict):
            return None, "%s checks not an object" % side
        for i in judge_ids:
            c = ec[side].get(i)
            if not isinstance(c, dict) or c.get("verdict") not in VERDICTS:
                return None, "%s %s verdict missing or not pass/fail" % (side, i)
    if obj["preference"] not in PREFS:
        return None, "preference %r not one of 1, 2, tie" % (obj["preference"],)
    if obj["confidence"] not in CONF:
        return None, "confidence %r not low/medium/high" % (obj["confidence"],)
    if not isinstance(obj["reason"], str) or not obj["reason"].strip():
        return None, "reason empty"
    return obj, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--packet-x", required=True)
    ap.add_argument("--packet-y", required=True)
    ap.add_argument("--rubric", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--order", required=True, choices=["xy", "yx"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--checks-x")
    ap.add_argument("--checks-y")
    ap.add_argument("--model", default=kitconfig.JUDGE_MODEL)
    ap.add_argument("--effort", default=kitconfig.JUDGE_EFFORT, choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--allow-cues", action="store_true",
                    help="run despite vocabulary cue hits (label hits always refuse)")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true", help="write the prompt file and stop; no model call")
    a = ap.parse_args()

    with open(a.rubric, encoding="utf-8") as f:
        rubric_raw = f.read()
    judge_ids = rubric_ids(rubric_raw, "judge_checks")
    auto_ids = rubric_ids(rubric_raw, "automated_checks")
    rubric = re.sub(r"<!--.*?-->\s*", "", rubric_raw, flags=re.S)  # machine lines are not for the judge
    px = json.load(open(a.packet_x, encoding="utf-8"))
    py = json.load(open(a.packet_y, encoding="utf-8"))
    for name, p in (("x", px), ("y", py)):
        ca = p.get("cue_audit", {})
        if ca.get("label_hits"):
            print("refusing: packet %s has %d arm-label cue hit(s); isolation failure" % (name, ca["label_hits"]),
                  file=sys.stderr)
            return 3
        if ca.get("vocab_hits") and not a.allow_cues:
            print("refusing: packet %s has %d vocabulary cue hit(s); rerun with --allow-cues to accept"
                  % (name, ca["vocab_hits"]), file=sys.stderr)
            return 3
    auto = {"x": None, "y": None}
    if auto_ids:
        if not (a.checks_x and a.checks_y):
            print("refusing: rubric declares automated checks %s; pass --checks-x and --checks-y" % auto_ids,
                  file=sys.stderr)
            return 2
        auto["x"] = json.load(open(a.checks_x, encoding="utf-8"))
        auto["y"] = json.load(open(a.checks_y, encoding="utf-8"))
    ev_names, evidence = read_evidence(a.evidence)

    first, second = ("x", "y") if a.order == "xy" else ("y", "x")
    pk = {"x": px, "y": py}
    # the judge sees only each check's verdict: a check script's "details" can carry trial paths,
    # and trial names carry arm labels. "manual" / unreadable results are shown as not decided.
    shown = {}
    for s in ("x", "y"):
        if auto_ids:
            shown[s] = {i: (v or "not decided by the script") for i, v in automated_verdicts(auto[s], auto_ids).items()}
        else:
            shown[s] = None
    # Checks the script left undecided (manual / unreadable) for either side go to the judge, so a
    # failure it finds is a recorded critical failure, not prose.
    undecided = [i for i in auto_ids
                 if any(automated_verdicts(auto[s], auto_ids)[i] is None for s in ("x", "y"))]
    judge_ids = list(judge_ids) + [i for i in undecided if i not in judge_ids]
    prompt = build_prompt(rubric, judge_ids, auto_ids, evidence, pk[first]["rendered"], pk[second]["rendered"],
                          shown[first], shown[second])

    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stem = os.path.splitext(out)[0]
    with open(stem + ".prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    if a.dry_run:
        print("dry run: prompt written to %s (%d chars)" % (stem + ".prompt.txt", len(prompt)))
        return 0

    exe = shutil.which(kitconfig.CLAUDE_CMD[0])
    if not exe:
        print("CLI %r not found on PATH" % kitconfig.CLAUDE_CMD[0], file=sys.stderr)
        return 2
    launch = tempfile.mkdtemp(prefix="judge_")
    lnorm = os.path.normcase(os.path.abspath(launch))
    if any(lnorm.startswith(os.path.normcase(r)) for r in FORBIDDEN_LAUNCH_ROOTS):
        print("refusing: temp launch dir %s is inside a forbidden tree" % launch, file=sys.stderr)
        return 2
    env = os.environ.copy()
    removed = [k for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN") if env.pop(k, None) is not None]
    version = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    cmd = [exe] + kitconfig.CLAUDE_CMD[1:] + ["-p", "--model", a.model, "--effort", a.effort,
           "--setting-sources", "project,local", "--strict-mcp-config",
           "--tools", "", "--no-chrome",
           "--output-format", "json", "--verbose", "--no-session-persistence"]
    popen_kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.time()
    status = "ok"
    p = subprocess.Popen(cmd, cwd=launch, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                         **popen_kw)
    try:
        stdout, stderr = p.communicate(prompt, timeout=a.timeout)
    except subprocess.TimeoutExpired:
        # end only the process tree this script started
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        else:
            os.killpg(p.pid, 9)
        stdout, stderr = p.communicate()
        status = "timeout"
    dur = round(time.time() - t0, 1)
    try:
        os.rmdir(launch)  # removes only if still empty
        launch_removed = True
    except OSError:
        launch_removed = False

    with open(stem + ".raw.json", "w", encoding="utf-8") as f:
        f.write(stdout)
    events = parse_events(stdout)
    result = next((e for e in reversed(events) if isinstance(e, dict) and e.get("type") == "result"), {})
    init = next((e for e in events if isinstance(e, dict) and e.get("type") == "system"
                 and e.get("subtype") == "init"), {})
    assistants = [e for e in events if isinstance(e, dict) and e.get("type") == "assistant"]
    with open(stem + ".assistant.jsonl", "w", encoding="utf-8") as f:
        for e in assistants:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    if status == "ok":
        if not result:
            status = "error_no_result"
        elif result.get("subtype") != "success" or result.get("is_error"):
            status = str(result.get("subtype") or "error")

    # result.usage is authoritative: an assistant event in --verbose output carries a partial output count.
    # The dollar figure is the CLI's own estimate, kept only for reference; the cost metric is total tokens.
    cost_usd, cost_src = result.get("total_cost_usd"), "CLI total_cost_usd"

    obj, why = parse_verdict(result.get("result"), judge_ids) if status == "ok" else (None, "run status %s" % status)
    side_of = {"submission_1": first, "submission_2": second, "1": first, "2": second}
    verdict = None
    if obj:
        checks = {side_of[s]: obj["essential_checks"][s] for s in ("submission_1", "submission_2")}
        crit = {}
        for s in ("x", "y"):
            av = automated_verdicts(auto[s], auto_ids) if auto_ids else {}
            # a script verdict stands; the judge's verdict fills only what the script left undecided
            final = {i: (av.get(i) or checks[s][i]["verdict"]) for i in judge_ids}
            final.update({i: v for i, v in av.items() if v is not None})
            fails = sorted(i for i, v in final.items() if v == "fail")
            unknown = [i for i, v in av.items() if v is None and i not in judge_ids]
            crit[s] = {"critical_fail": bool(fails), "failed": fails, "unreadable_automated": unknown}
        pref = obj["preference"] if obj["preference"] == "tie" else side_of[obj["preference"]]
        violation = (pref in ("x", "y") and crit[pref]["critical_fail"]
                     and not crit["y" if pref == "x" else "x"]["critical_fail"])
        verdict = {"preference": pref, "essential_checks": checks, "critical": crit,
                   "confidence": obj["confidence"], "reason": obj["reason"],
                   "rule_violation_critical_fail_preferred": violation,
                   "extra_keys": sorted(set(obj) - {"essential_checks", "preference", "confidence", "reason"})}

    rec = {
        "schema": "v4-judge-result/1",
        "started_utc": started, "duration_s": dur, "status": status, "exit_code": p.returncode,
        "order": a.order, "submission_1": first, "submission_2": second,
        "packet_x": os.path.abspath(a.packet_x), "packet_y": os.path.abspath(a.packet_y),
        "rubric": os.path.abspath(a.rubric), "evidence_dir": os.path.abspath(a.evidence), "evidence_files": ev_names,
        "checks_x": a.checks_x, "checks_y": a.checks_y,
        "model_requested": a.model, "effort": a.effort, "claude_version": version,
        "cmd": [os.path.basename(exe)] + cmd[1:] + ["<prompt on stdin>"],
        "prompt_file": stem + ".prompt.txt", "prompt_chars": len(prompt), "raw_file": stem + ".raw.json",
        "isolation": {
            "launch_cwd": launch, "launch_cwd_removed_after": launch_removed,
            "tools_observed": init.get("tools"), "mcp_servers_observed": init.get("mcp_servers"),
            "model_observed": init.get("model"), "api_key_source": init.get("apiKeySource"),
            "permission_mode": init.get("permissionMode"), "init_cwd": init.get("cwd"),
            "env_vars_removed": removed,
            "cue_hits": {"x": px.get("cue_audit", {}).get("vocab_hits"), "y": py.get("cue_audit", {}).get("vocab_hits")},
            "allow_cues": a.allow_cues,
        },
        "session_id": result.get("session_id") or init.get("session_id"),
        "result_text": result.get("result"),
        "verdict_parse_error": why,
        "verdict_raw_submission_labels": obj,
        "verdict": verdict,
        "usage": result.get("usage"), "model_usage": result.get("modelUsage"), "num_turns": result.get("num_turns"),
        "cost_usd": cost_usd, "cost_source": cost_src, "cli_total_cost_usd": result.get("total_cost_usd"),
        "stderr_tail": (stderr or "")[-2000:],
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)
    # one append-only receipt per call: retries overwrite `out`, never this ledger
    # total tokens is the benchmark's cost metric; dollars are only a weighting of the same tokens
    u = result.get("usage") or {}
    toks = {k: int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                            "cache_creation_input_tokens")}
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"started_utc": started, "out": out, "order": a.order, "status": status,
                            "parsed": verdict is not None, "session_id": result.get("session_id"),
                            "tokens": toks, "total_tokens": sum(toks.values()),
                            "cost_usd": cost_usd, "cli_total_cost_usd": result.get("total_cost_usd")}) + "\n")
    pv = verdict["preference"] if verdict else "MISSING (%s)" % why
    print("%s: status=%s order=%s preference=%s cost_usd=%s tools=%s" % (out, status, a.order, pv, cost_usd,
                                                                        init.get("tools")))
    if status != "ok":
        return 1
    return 0 if verdict is not None else 4  # a malformed verdict is a failed call


if __name__ == "__main__":
    sys.exit(main())
