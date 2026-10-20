"""Drive a run: judge calibration, worker trials, grading scripts ("oracle"), judging.

  python run_driver.py fixtures              # calibration: every fixture pair, both orders + sentinel; exit 3 on a miss
  python run_driver.py trials  --run NAME    # worker trials of that run (ABBA), then the oracle
  python run_driver.py oracle  --run NAME    # (re)run each packet's grading script on the run's finished trials
  python run_driver.py judge   --run NAME    # judge the run's pairs in both orders; exit 3 on any missing,
                                             # refused or rule-breaking verdict

Packets come from <root>/packets/<id>/packet.json (see kitconfig.py and REPLICATE.md). Runs are defined in
<root>/runs.json. A run lists its trials explicitly or gives pairs_per_packet, from which names
<prefix>-<id>-p<i>-<arm> are generated, arm order alternating by pair (pair 1 harness first, pair 2 bloat
first, ...). Outputs go to results/<run>/; calibration lives in results/calibration/ and is shared by every run.

packet.json keys used here: "kind" ("write-up" or "coding": which empty fixture the calibration uses, "missing"
or "untouched"), "grader" (optional: a command list for the packet's grading script, run as
<grader...> --trial <dir> --packet <packet dir>, printing JSON {"checks": {id: "pass"|"fail"|"manual"}}).

Gates: trials and judge refuse unless calibration is clean AND its fingerprint
(rubrics, grader scripts, evidence) matches the current files. Packets and oracle results are rebuilt
every run (offline, free). A judge call is reused only when its saved result parsed and its prompt is
byte-identical to the one the current code builds. A packet with vocabulary cues is judged only if
results/<run>/cue_reviews.json holds a review whose cue hash matches the packet's current cues.
A failed or leaked trial is never retried automatically; its pair is excluded and reported. A run with
valid_pairs_target is judged complete only at exactly that many valid pairs per packet, and its trials
phase refuses pairs beyond one replacement round.
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kitconfig  # noqa: E402

APP = Path(__file__).resolve().parent
V4 = kitconfig.ROOT
CAL = kitconfig.RESULTS / "calibration"  # calibration home, shared by all runs
DONE = kitconfig.DONE
PY = sys.executable
P = kitconfig.packets()
# grading scripts by packet, from packet.json "grader": [interpreter..., script path relative to the packet folder]
ORACLES = {k: ([PY if c == "python" else c for c in v["grader"][:-1]], v["dir"] / v["grader"][-1])
           for k, v in P.items() if v.get("grader")}
MAX_TRIALS = None  # set from --max-trials

# Calibration fixtures, per packet, in judge_only/<id>/fixtures/<name>/ (each a complete copy of the project tree
# as a submission would leave it; it is diffed against the freeze, so a missing file reads as deleted):
# (x, y, preference expectation, per-side must-pass failure expectation)
#   "x" = x must win; "x_or_tie" = y must not win (length bias); "tie" = identical outputs;
#   "any" = any preference, but the must-pass expectations must hold (valid alternative).
# The empty fixture is "missing" for a write-up packet and "untouched" for a coding packet.
FIXTURE_PAIRS = []
for _pid, _cfg in P.items():
    _empty = "untouched" if _cfg["kind"] == "coding" else "missing"
    FIXTURE_PAIRS += [
        (_pid, "known_good", _empty, "x", {"x": False, "y": True}),
        (_pid, "known_good", "polished_wrong", "x", {"x": False, "y": True}),
        (_pid, "known_good", "valid_alternative", "any", {"x": False, "y": False}),
        (_pid, "known_good", "padded", "x_or_tie", {"x": False, "y": False}),
        (_pid, "known_good", "known_good", "tie", {"x": False, "y": False}),
    ]


def load_run(name):
    runs = json.loads(kitconfig.RUNS_FILE.read_text(encoding="utf-8"))
    r = runs[name]
    if "trials" in r:
        trials = [tuple(t) for t in r["trials"]]
        pairs = [tuple(p) for p in r["pairs"]]
    else:
        trials, pairs = [], []
        for pid, n in sorted(r["pairs_per_packet"].items()):
            for i in range(1, n + 1):
                h, b = f"{r['prefix']}-{pid}-p{i}-harness", f"{r['prefix']}-{pid}-p{i}-bloat"
                order = [("harness", h), ("bloat", b)] if i % 2 else [("bloat", b), ("harness", h)]
                trials += [(pid, arm, nm) for arm, nm in order]
                pairs.append((pid, h, b))
    return trials, pairs, V4 / "results" / name


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def tree_hash(h, root):
    """Every file under root (relative path + bytes), skipping generated "_*" folders and bytecode."""
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and "__pycache__" not in rel.parts and not any(s.startswith("_") for s in rel.parts[:-1]):
            h.update(rel.as_posix().encode() + b"\0" + p.read_bytes())


def packet_hash(pid):
    """What a trial of this packet is built from: freeze, fixture overlay, brief, packet.json (sources, drops,
    facts) and the arm builder."""
    h = hashlib.sha256()
    d = P[pid]["dir"]
    for sub in ("freeze", "fixture"):
        if (d / sub).is_dir():
            tree_hash(h, d / sub)
    h.update((d / "brief.txt").read_bytes() + (d / "packet.json").read_bytes() + (APP / "build_arms.py").read_bytes())
    return h.hexdigest()


def fingerprint():
    """Everything a judge prompt or verdict depends on: rubrics, graders, judge code, evidence, the packets'
    inputs and the fixture trees."""
    h = hashlib.sha256()
    files = [P[k]["rubric"] for k in P] + [APP / g for _, g in ORACLES.values()]
    files += [APP / f for f in ("run_judge.py", "build_judge_packet.py")]
    files += sorted(p for k in P for p in P[k]["evidence"].iterdir() if p.is_file())
    for f in files:
        h.update(str(f.name).encode() + b"\0" + Path(f).read_bytes())
    for k in sorted(P):
        h.update(packet_hash(k).encode())
        if (P[k]["evidence"] / "fixtures").is_dir():
            tree_hash(h, P[k]["evidence"] / "fixtures")
    return h.hexdigest()


def packet_lock_problems(name, done):
    """Bind a run's trials to the packet version they ran on: the first time a packet's trials run, its hash is
    recorded; if the packet changes after any of its trials exist, its trials so far are invalid."""
    trials, _, out = load_run(name)
    f = out / "packet_hashes.json"
    rec = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    probs = []
    for pid in sorted({t[0] for t in trials}):
        cur = packet_hash(pid)
        ran = any(t[0] == pid and t[2] in done for t in trials)
        if pid in rec and rec[pid] != cur and ran:
            probs.append(f"packet {pid} changed after its first trial: its trials so far are invalid")
        elif pid not in rec:
            rec[pid] = cur
    return probs, rec, f


def oracle(pid, trial_dir, out_file):
    if pid not in ORACLES:
        return None
    interp, grader = ORACLES[pid]
    code, txt = run(interp + [grader, "--trial", trial_dir, "--packet", P[pid]["dir"]])
    start = txt.find("{")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(txt[start:] if start >= 0 else json.dumps({"error": txt[-2000:]}), encoding="utf-8")
    return out_file


def packet(trial_dir, base, fixture, out_file):
    cmd = [PY, "-I", APP / "build_judge_packet.py", "--trial", trial_dir, "--freeze", base, "--out", out_file]
    if fixture:
        cmd += ["--fixture", fixture]
    code, txt = run(cmd)
    if code != 0:
        raise SystemExit(f"packet build failed for {trial_dir}:\n{txt[-2000:]}")
    return out_file


def cue_hash(packet_file):
    ca = json.loads(Path(packet_file).read_text(encoding="utf-8")).get("cue_audit") or {}
    return hashlib.sha256(json.dumps(ca.get("hits", []), sort_keys=True).encode()).hexdigest()[:16]


def cue_reviewed(out, *packets):
    """True only if every packet with vocabulary cues has a review for exactly its current cues."""
    f = out / "cue_reviews.json"
    reviews = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    for p in packets:
        ca = json.loads(Path(p).read_text(encoding="utf-8")).get("cue_audit") or {}
        if not ca.get("vocab_hits"):
            continue
        rv = reviews.get(Path(p).name)
        if not isinstance(rv, dict) or rv.get("cue_hash") != cue_hash(p):
            return False
    return True


def judge(out, pid, px, py, cx, cy, order, out_file):
    def args(o):
        a = [PY, "-I", APP / "run_judge.py", "--packet-x", px, "--packet-y", py, "--rubric", P[pid]["rubric"],
             "--evidence", P[pid]["evidence"], "--order", order, "--out", o]
        if cx:
            a += ["--checks-x", cx, "--checks-y", cy]
        if cue_reviewed(out, px, py):
            a += ["--allow-cues"]
        return a
    prompt_file = out_file.with_suffix(".prompt.txt")
    reuse = False
    if out_file.exists() and prompt_file.exists():
        old = json.loads(out_file.read_text(encoding="utf-8"))
        if (old.get("verdict") or {}).get("preference"):
            probe = out_file.with_name(out_file.stem + ".probe.json")
            run(args(probe) + ["--dry-run"])  # writes the probe's prompt only; no model call
            new_prompt = probe.with_suffix(".prompt.txt")
            reuse = new_prompt.exists() and new_prompt.read_text(encoding="utf-8") == prompt_file.read_text(encoding="utf-8")
            new_prompt.unlink(missing_ok=True)
    if not reuse:
        code, txt = run(args(out_file))
        if code not in (0, 4):  # 4 = call made, verdict malformed: its result file is already written
            out_file.write_text(json.dumps({"status": "refused_or_error", "exit": code, "log": txt[-3000:]}),
                                encoding="utf-8")
    d = json.loads(out_file.read_text(encoding="utf-8"))
    v = d.get("verdict") or {}
    return {"order": order, "preference": v.get("preference"), "critical": v.get("critical"),
            "violation": v.get("rule_violation_critical_fail_preferred"), "cost_usd": d.get("cost_usd"),
            "status": d.get("status"), "reused": reuse}


def evaluate(expect, crit_expect, call):
    probs = []
    pref, crit = call["preference"], call["critical"] or {}
    if pref is None:
        return ["no parsed verdict (status %s)" % call["status"]]
    if expect == "x" and pref != "x":
        probs.append("preferred %s, expected x" % pref)
    if expect == "x_or_tie" and pref == "y":
        probs.append("preferred the padded side")
    if expect == "tie" and pref != "tie":
        probs.append("identical outputs not a tie")
    for side, want in crit_expect.items():
        got = bool((crit.get(side) or {}).get("critical_fail"))
        if got != want:
            probs.append("side %s critical_fail=%s, expected %s" % (side, got, want))
    if call["violation"]:
        probs.append("preferred a critically failed side")
    return probs


def sentinel_test():
    """Every packet with a sentinel fixture (judge_only/<id>/fixtures/sentinel: a submission folder holding a
    file that names its arm) must have its packet refused before any model call (dry run, no judge call)."""
    out = CAL / "fixtures" / "sentinel"
    ok, logs = True, []
    for pid in sorted(P):
        fx = P[pid]["evidence"] / "fixtures"
        if not (fx / "sentinel").is_dir():
            continue
        fdir = P[pid]["dir"] / "fixture"
        base, fix = P[pid]["dir"] / "freeze", (fdir if fdir.is_dir() else None)
        pk = packet(fx / "sentinel", base, fix, out / f"{pid}-sentinel.json")
        good = packet(fx / "known_good", base, fix, out / f"{pid}-known_good.json")
        code, txt = run([PY, "-I", APP / "run_judge.py", "--packet-x", good, "--packet-y", pk, "--rubric",
                         P[pid]["rubric"], "--evidence", P[pid]["evidence"], "--order", "xy",
                         "--out", out / f"{pid}-sentinel-refusal.json", "--allow-cues", "--dry-run"])
        refused = code == 3 and "label" in txt.lower()
        ok = ok and refused
        logs.append(f"{pid}: {'refused' if refused else 'NOT refused: ' + txt[-300:]}")
    return ok, "; ".join(logs)


def calibration_ok():
    f = CAL / "fixtures_summary.json"
    if not f.exists():
        return False, "no calibration summary"
    s = json.loads(f.read_text(encoding="utf-8"))
    if s.get("clean") is not True:
        return False, "calibration not clean"
    if s.get("fingerprint") != fingerprint():
        return False, "rubric, grader or evidence changed since calibration: rerun the fixtures phase"
    return True, ""


def trial_status():
    res = V4 / "results" / "v4-results.csv"
    if not res.exists():
        return {}
    return {r["trial_name"]: r for r in csv.DictReader(open(res, encoding="utf-8"))}


def pair_valid(status, h, b):
    return all(n in status and status[n]["status"] == "ok" and status[n]["leak"] != "1" for n in (h, b))


def pair_limits(name, status):
    """For a run with valid_pairs_target: {packet: (target, allowed attempted pairs)}. Allowed = target plus one
    replacement per pair voided among the first `target` pairs (one replacement round)."""
    r = json.loads(kitconfig.RUNS_FILE.read_text(encoding="utf-8"))[name]
    tgt = r.get("valid_pairs_target")
    if not tgt:
        return {}
    _, pairs, _ = load_run(name)
    lim = {}
    for pid in r["pairs_per_packet"]:
        first = [(h, b) for p, h, b in pairs if p == pid][:tgt]
        voided = sum(1 for h, b in first if (h in status or b in status) and not pair_valid(status, h, b))
        lim[pid] = (tgt, tgt + voided)
    return lim


def phase_fixtures(_run):
    out = CAL / "fixtures"
    rows, problems = [], []
    for pid, x, y, expect, crit_expect in FIXTURE_PAIRS:
        fx = P[pid]["evidence"] / "fixtures"
        if not (fx / y).is_dir():
            problems.append(f"{pid} {x} vs {y}: fixture folder missing")
            continue
        # a packet with a fixture overlay builds its fixture packets against freeze + overlay
        fdir = P[pid]["dir"] / "fixture"
        base, fix = P[pid]["dir"] / "freeze", (fdir if fdir.is_dir() else None)
        pk = {n: packet(fx / n, base, fix, out / "packets" / f"{pid}-{n}.json") for n in {x, y}}
        ck = {n: oracle(pid, fx / n, out / "oracle" / f"{pid}-{n}.json") for n in {x, y}}
        calls = [judge(CAL, pid, pk[x], pk[y], ck[x], ck[y], o, out / f"{pid}-{x}-vs-{y}-{o}.json")
                 for o in ("xy", "yx")]
        probs = [f"{c['order']}: {p}" for c in calls for p in evaluate(expect, crit_expect, c)]
        rows.append({"packet": pid, "x": x, "y": y, "expect": expect, "critical_expect": crit_expect,
                     "ok": not probs, "problems": probs, "calls": calls})
        problems += [f"{pid} {x} vs {y}: {p}" for p in probs]
    sent_ok, sent_log = sentinel_test()
    if not sent_ok:
        problems.append("sentinel: arm-label packet was not refused: " + sent_log)
    summary = {"clean": not problems, "fingerprint": fingerprint(), "problems": problems,
               "sentinel_refused": sent_ok, "pairs": rows,
               "cost_usd_this_run": round(sum((c["cost_usd"] or 0) for r in rows for c in r["calls"]
                                              if not c["reused"]), 4)}
    (CAL / "fixtures_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for r in rows:
        print(f"{r['packet']} {r['x']} vs {r['y']} expect={r['expect']} ok={r['ok']} "
              f"prefs={[c['preference'] for c in r['calls']]} reused={[c['reused'] for c in r['calls']]}")
    print("sentinel refused:", sent_ok)
    print("new judge cost_usd", summary["cost_usd_this_run"], "| problems:", problems or "none")
    return 0 if summary["clean"] else 3


def phase_trials(name):
    ok, why = calibration_ok()
    if not ok:
        print("refusing:", why)
        return 3
    trials, _, out = load_run(name)
    done = trial_status()
    lim = pair_limits(name, done)
    over = {pid: (n, lim[pid][1]) for pid, n in
            json.loads(kitconfig.RUNS_FILE.read_text(encoding="utf-8"))[name].get("pairs_per_packet", {}).items()
            if pid in lim and n > lim[pid][1]}
    if over:
        print("refusing: more pairs than the target plus one replacement round allows (attempted, allowed):", over)
        return 3
    lock_probs, rec, lockf = packet_lock_problems(name, done)
    if lock_probs:
        print("refusing:", lock_probs)
        return 3
    out.mkdir(parents=True, exist_ok=True)
    lockf.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    failed, launched = [], 0
    for pid, arm, tn in trials:
        if tn in done:
            if done[tn]["status"] != "ok":
                failed.append(tn)
            continue
        if MAX_TRIALS is not None and launched >= MAX_TRIALS:
            # the driver cannot see the usage window: batches let the operator check it between them
            # rerun the same command to continue
            print(f"stopped after {launched} new trial(s) (--max-trials); rerun to continue")
            break
        launched += 1
        code, txt = run([PY, "-I", APP / "run_trial.py", "--packet", pid, "--arm", arm, "--name", tn])
        (out / "trials").mkdir(parents=True, exist_ok=True)
        (out / "trials" / f"{tn}.log").write_text(txt, encoding="utf-8")
        print(tn, "exit", code)
        if code != 0:
            failed.append(tn)
    phase_oracle(name)
    if failed:
        print("failed trials (not retried; their pairs are excluded):", failed)
    return 0


def phase_oracle(name):
    trials, _, out = load_run(name)
    for pid, arm, tn in trials:
        if pid in ORACLES and (DONE / tn).is_dir():
            oracle(pid, DONE / tn, out / "oracle" / f"{tn}.json")
            print(tn, json.loads((out / "oracle" / f"{tn}.json").read_text(encoding="utf-8")).get("summary"))
    return 0


def phase_judge(name):
    ok, why = calibration_ok()
    if not ok:
        print("refusing:", why)
        return 3
    _, pairs, out = load_run(name)
    jout = out / "judge"
    status = trial_status()
    rows, problems = [], []
    problems += packet_lock_problems(name, status)[0]
    for pid, h, b in pairs:
        bad = [n for n in (h, b) if n not in status or status[n]["status"] != "ok" or status[n]["leak"] == "1"]
        if bad:
            rows.append({"packet": pid, "harness": h, "bloat": b, "excluded": bad})
            print(pid, h, "vs", b, "EXCLUDED (failed, missing or leaked):", bad)
            continue
        pk = {n: packet(DONE / n, P[pid]["dir"] / "arms" / n.rsplit("-", 1)[1], None, jout / "packets" / f"{n}.json")
              for n in (h, b)}
        ck = {n: oracle(pid, DONE / n, out / "oracle" / f"{n}.json") for n in (h, b)}
        if not cue_reviewed(out, pk[h], pk[b]):
            problems.append(f"{h} vs {b}: cue review needed for the packets' current cues")
        res = [judge(out, pid, pk[h], pk[b], ck[h], ck[b], o, jout / f"{h}-vs-bloat-{o}.json") for o in ("xy", "yx")]
        for c in res:
            if c["preference"] is None:
                problems.append(f"{h} vs {b} {c['order']}: no parsed verdict (status {c['status']})")
            if c["violation"]:
                problems.append(f"{h} vs {b} {c['order']}: judge preferred a critically failed side")
        rows.append({"packet": pid, "harness": h, "bloat": b, "calls": res})
        print(pid, h, "vs", b, [(c["order"], c["preference"], c["status"]) for c in res], "(x = harness)")
    # a run with a valid-pair target is complete only with exactly that many valid pairs per packet
    valid = {}
    for r in rows:
        if "calls" in r:
            valid[r["packet"]] = valid.get(r["packet"], 0) + 1
    # ...or with fewer once the one replacement round is used up: every allowed pair attempted, none still to run;
    # that shortfall is reported, not a problem
    shortfall = {}
    for pid, (tgt, allowed) in pair_limits(name, status).items():
        mine = [(h, b) for p, h, b in pairs if p == pid]
        attempted = all(h in status and b in status for h, b in mine)
        if valid.get(pid, 0) < tgt and len(mine) >= allowed and attempted:
            shortfall[pid] = f"{valid.get(pid, 0)} valid pairs of target {tgt}; replacement round used up"
        elif valid.get(pid, 0) != tgt:
            problems.append(f"packet {pid}: {valid.get(pid, 0)} valid pairs, target {tgt}")
    summary = {"complete": not problems, "problems": problems, "shortfall": shortfall, "pairs": rows,
               "valid_pairs": valid,
               "cost_usd_this_run": round(sum((c["cost_usd"] or 0) for r in rows
                                              for c in r.get("calls", []) if not c["reused"]), 4),
               "cost_note": "cumulative judge spend: results/judge_ledger.jsonl"}
    (out / "judge_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("judge cost_usd this run", summary["cost_usd_this_run"], "| problems:", problems or "none")
    return 0 if not problems else 3


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["fixtures", "trials", "oracle", "judge"])
    ap.add_argument("--run", default="pilot")
    ap.add_argument("--max-trials", type=int, default=None,
                    help="trials phase: launch at most this many new trials, then stop (check usage between batches)")
    a = ap.parse_args()
    MAX_TRIALS = a.max_trials
    CAL.mkdir(parents=True, exist_ok=True)
    sys.exit({"fixtures": phase_fixtures, "trials": phase_trials, "oracle": phase_oracle,
              "judge": phase_judge}[a.phase](a.run))
