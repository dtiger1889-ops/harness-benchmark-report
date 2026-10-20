"""Run one worker trial in an isolated fresh copy of one arm.

Usage:
  python run_trial.py --packet <id> --arm harness|bloat --name <run>-<id>-p<i>-<arm> [--model <id>]

What it does:
  1. Copies packets/<id>/arms/<arm>/ to <trials_dir>/<name>/ (outside the workspace; refuses if the name was used
     before or if the trials folder is not empty, so a trial can only ever see itself there).
  2. Runs the CLI headless (`claude -p`) from the project folder inside that copy, prompt from brief.txt on
     stdin, with user-level settings skipped (--setting-sources project,local --strict-mcp-config) so your own
     hooks, skills and MCP servers do not enter the trial; subagents and web tools disallowed.
  3. Saves the stream-json transcript, takes token totals from the run's final result record, counts messages
     and peak context once per message id, audits every tool call for references outside the trial copy,
     and appends one row to results/v4-results.csv. Then moves the copy to <done_dir>.
Trials are not OS-sandboxed: the outside-reference audit after the run is the boundary check. A trial whose
audit finds a non-allowlisted outside reference is marked void (leak = 1) and its pair is excluded.
"""
import argparse
import csv
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the driver runs scripts with python -I
import kitconfig  # noqa: E402

RESULTS = kitconfig.RESULTS / "v4-results.csv"
TRIALS = kitconfig.TRIALS
DONE = kitconfig.DONE
COLUMNS = ["trial_name", "packet", "arm", "model", "claude_version", "start_iso", "duration_s",
           "exit_code", "status", "num_turns", "msgs", "input", "output", "cache_read",
           "cache_create", "w5m", "w1h", "w_unsplit", "total_tokens", "cli_total_cost_usd",
           "cache_hit_rate", "peak_context", "gap_since_prev_trial_s", "outside_paths", "leak"]


def _posix(p) -> str:
    return str(p).lower().replace("\\", "/")


# A reference to the workspace (results, judge-only evidence, packets), the done folder or a user-listed private
# folder is always recorded with a "flag:" prefix and voids the trial.
_leak = [re.escape(_posix(kitconfig.ROOT)), re.escape(_posix(DONE)), r"judge_only"] + kitconfig.LEAK_PATTERNS
LEAK_RX = re.compile("|".join(_leak).replace("/", r"[\\/]+"), re.I)
GIT_C_RX = re.compile(r"git\s+-C\s+(\"[^\"]+\"|'[^']+'|\S+)", re.I)
# Allowlisted outside references are recorded with a "benign:" prefix and do not void a trial.
BENIGN_PREFIXES = kitconfig.BENIGN_PREFIXES
TRIALS_ROOT = _posix(TRIALS)


def is_void(outside: list[str], trial_name: str) -> bool:
    return any(not e.startswith("benign:") for e in outside)


def sibling_rx(name: str):
    """References to any other trial folder under the trials root."""
    n = re.escape(name)
    tr = re.escape(TRIALS.name)
    return re.compile(r"%s[\\/]+(?!%s(?![\w.-]))[\w.-]+|\.\.[\\/]+(?!%s(?![\w.-]))[\w.-]+-(?:harness|bloat)(?![\w-])"
                      % (tr, n, n), re.I)


NET_RX = re.compile(r"invoke-webrequest|invoke-restmethod|\biwr\b|\birm\b|\bcurl\b|\bwget\b|start-bitstransfer"
                    r"|net\.webclient|httpclient|urllib\.request|requests\.get"
                    # git and gh can fetch private repos with stored credentials
                    r"|\bgit\b[^;&|\n]*?\s(?:clone|fetch|pull|ls-remote|submodule)\b|\bgh\s+(?:repo|api|gist|release|pr)\b",
                    re.I)
CD_RX = re.compile(r"(?:^|[;&|(]\s*)(?:cd|pushd|set-location|sl|push-location)\s+(\"[^\"]+\"|'[^']+'|[^\s;&|)]+)?",
                   re.I)


def _norm(path: str) -> str:
    p = re.sub(r"^/([a-z])/+", r"\1:/", path.strip("\"'").replace("\\", "/").lower())
    return posixpath.normpath(p)


def _under(p: str, base: str) -> bool:
    """p is base itself or a slash-delimited descendant (so "npm-backup" is not under "npm")."""
    return p == base or p.startswith(base.rstrip("/") + "/")


def git_c_inside(cmd: str, target: str, root: str) -> bool:
    """A `git -C` target is benign only when it provably stays inside the trial copy: no ".." anywhere in the
    command, no drive-relative target ("D:x"), every cd/pushd in the command goes to an absolute path inside the
    copy, and the target is either absolute inside the copy or plainly relative."""
    if ".." in cmd:
        return False
    for m in CD_RX.finditer(cmd):
        arg = m.group(1)
        if not arg or not re.match(r"(?:[a-z]:[\\/]|/[a-z]/)", arg.strip("\"'"), re.I) or not _under(_norm(arg), root):
            return False
    t = target.strip("\"'")
    if re.match(r"[a-z]:(?![\\/])", t, re.I):
        return False
    if re.match(r"(?:[a-z]:[\\/]|/[a-z]/)", t, re.I):
        return _under(_norm(t), root)
    return not t.startswith(("/", "\\", "~", "$", "%"))


def outside_paths(transcript: Path, trial_root: Path) -> list[str]:
    """Absolute paths named in tool calls that are not inside the trial copy, plus flagged workspace /
    judge-only / other-trial references ("flag:") and network commands ("net:").
    Paths are matched against the trial's run location <trials_dir>/<name>. Windows drive paths
    (C:\\x, C:/x) and MSYS-style paths (/c/x) are recognized; this matcher was built for Windows hosts."""
    root = _posix(TRIALS / trial_root.name)
    found = set()
    # "Program Files" keeps its space so an allowed tool path is not cut short, and "/x/" followed by another "/"
    # is a sed pattern ("/s//..."), not a drive path; "/c/$HOME", a bare drive root ("/d/", "ls C:/") and a
    # doubled separator before a name ("/c//Users") still count
    pat = re.compile(r"(?<![A-Za-z])(?:[a-zA-Z]:[\\/]{1,2}(?=[\w.$~]|[\s\"'`|;,)]|$)|/[a-z]/(?!/)|/[a-z]//(?=[A-Za-z]))"
                     r"(?:Program Files \(x86\)|Program Files|[^\s\"'`|;,)])*", re.I)
    esc = sibling_rx(trial_root.name)
    own = "-" + trial_root.name.lower()  # the CLI's own per-session scratch folder carries the trial name
    events = []
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    for d in events:
        if d.get("type") != "assistant":
            continue
        for b in (d.get("message") or {}).get("content") or []:
            if b.get("type") != "tool_use":
                continue
            s = json.dumps(b.get("input")).replace("\\\\", "\\")
            for m in list(LEAK_RX.finditer(s)) + list(esc.finditer(s)):
                found.add("flag:" + s[max(0, m.start() - 60):m.end() + 60])
            if b.get("name") in ("Bash", "PowerShell"):
                c = str((b.get("input") or {}).get("command", ""))
                for m in NET_RX.finditer(c):
                    found.add("net:" + c[max(0, m.start() - 60):m.end() + 60])
                for m in GIT_C_RX.finditer(c):
                    inside = git_c_inside(c, m.group(1), root)
                    found.add(("benign:" if inside else "flag:") + c[max(0, m.start() - 60):m.end() + 60])
            for raw in pat.findall(json.dumps(b.get("input"))):
                if re.fullmatch(r"[a-zA-Z]:\\[nrt]", raw):  # "of:\n" in escaped JSON text, not a path
                    continue
                p = raw.replace("\\\\", "/").replace("\\", "/").lower()
                p = re.sub(r"^/([a-z])/+", r"\1:/", p)
                p = posixpath.normpath(p)  # judge "<trial>/../../x" where it lands
                if (not _under(p, root) and not p.startswith(("c:/program files", "c:/windows"))
                        and own not in p):
                    # the bare trials root holds only the running trial (main() refuses to start otherwise)
                    benign = p.rstrip("/") == TRIALS_ROOT or any(_under(p, bp) for bp in BENIGN_PREFIXES)
                    found.add(("benign:" if benign else "") + raw[:200])
    return sorted(found)


def capture_changes(arm: Path, trial: Path, dest: Path) -> dict:
    """Copy every file the trial added or changed (vs its arm) into dest; list deletions."""
    def files(root):
        return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    before, after = files(arm), files(trial)
    added = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    changed = sorted(k for k in set(after) & set(before)
                     if after[k].read_bytes() != before[k].read_bytes())
    for rel in added + changed:
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(after[rel], out)
    manifest = {"added": added, "changed": changed, "deleted": deleted}
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def per_message(transcript: Path) -> dict:
    """Messages and peak context, counting each message id once. The CLI writes one event per content block
    and repeats the message's full usage on each, so summing every event double-counts."""
    seen, peak = set(), 0
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "assistant":
            continue
        m = d.get("message") or {}
        mid = m.get("id")
        if not mid or mid in seen:
            continue
        seen.add(mid)
        u = m.get("usage") or {}
        ctx = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        peak = max(peak, ctx)
    return {"msgs": len(seen), "peak_context": peak}


def usage_columns(transcript: Path, trial: Path, result: dict) -> dict:
    """Token columns. Totals come from the run's final result record: each assistant event carries a partial
    output count, so summing events undercounts output. total_tokens = input + output + cache read + cache
    write, the benchmark's cost metric. cli_total_cost_usd is the CLI's own dollar figure, kept for reference."""
    pm = per_message(transcript)
    u = result.get("usage") or {}
    cc = u.get("cache_creation") or {}
    inp, out = int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
    read, create = int(u.get("cache_read_input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0)
    w5, w1 = int(cc.get("ephemeral_5m_input_tokens") or 0), int(cc.get("ephemeral_1h_input_tokens") or 0)
    denom = read + create + inp
    outside = outside_paths(transcript, trial)
    leak = is_void(outside, trial.name)
    (transcript.parent / f"{transcript.stem}.outside_paths.json").write_text(
        json.dumps(outside, indent=2), encoding="utf-8")
    return {"num_turns": result.get("num_turns", ""), "msgs": pm["msgs"], "input": inp, "output": out,
            "cache_read": read, "cache_create": create, "w5m": w5, "w1h": w1,
            "w_unsplit": max(0, create - w5 - w1), "total_tokens": inp + out + read + create,
            "cli_total_cost_usd": result.get("total_cost_usd", ""),
            "cache_hit_rate": round(read / denom, 4) if denom else "",
            "peak_context": pm["peak_context"], "outside_paths": len(outside), "leak": int(leak)}


def prev_end(packet: str):
    if not RESULTS.exists():
        return None
    last = None
    with open(RESULTS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["packet"] == packet:
                last = r
    if not last:
        return None
    t = datetime.fromisoformat(last["start_iso"])
    return t.timestamp() + float(last["duration_s"])


def main() -> int:
    packets = kitconfig.packets()
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", required=True, choices=sorted(packets))
    ap.add_argument("--arm", required=True, choices=["harness", "bloat"])
    ap.add_argument("--name", required=True)
    ap.add_argument("--model", default=kitconfig.WORKER_MODEL)
    ap.add_argument("--max-turns", type=int, default=80)
    ap.add_argument("--timeout", type=int, default=2400, help="wall-clock seconds")
    a = ap.parse_args()

    cfg = packets[a.packet]
    src = cfg["dir"] / "arms" / a.arm
    trial = TRIALS / a.name
    recorded = RESULTS.exists() and any(r["trial_name"] == a.name
                                        for r in csv.DictReader(open(RESULTS, encoding="utf-8")))
    if trial.exists() or (DONE / a.name).exists() or recorded:
        # a reused name would overwrite the old transcript and its record
        print(f"refusing: trial name {a.name} already exists (running, finished or recorded)", file=sys.stderr)
        return 2
    others = [p.name for p in TRIALS.iterdir()] if TRIALS.exists() else []
    if others:
        # a listing of the trials root is only harmless while it holds nothing but the running trial
        print(f"refusing: trials folder is not empty: {others}", file=sys.stderr)
        return 2
    TRIALS.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, trial)
    try:
        return launch(a, cfg, src, trial)
    finally:
        if trial.exists():
            # an interrupted launch must not leave its copy in the trials root, or every later trial refuses to
            # start; the name stays used, so a retry runs under a new name
            DONE.mkdir(parents=True, exist_ok=True)
            shutil.move(str(trial), str(DONE / a.name))
            print("interrupted launch: copy moved to", DONE / a.name, file=sys.stderr)


def launch(a, cfg: dict, src: Path, trial: Path) -> int:
    cwd = trial / cfg["project"]
    prompt = (cfg["dir"] / "brief.txt").read_text(encoding="utf-8")
    tdir = kitconfig.RESULTS / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    transcript = tdir / f"{a.name}.jsonl"
    exe = list(kitconfig.CLAUDE_CMD)
    exe[0] = shutil.which(exe[0]) or exe[0]  # resolves a .cmd shim on Windows
    version = subprocess.run(exe + ["--version"], capture_output=True, text=True).stdout.strip()
    cmd = exe + ["-p", "--model", a.model,
                 "--setting-sources", "project,local", "--strict-mcp-config",
                 "--permission-mode", "acceptEdits",
                 "--allowedTools", "Read,Edit,Write,Bash,PowerShell,Glob,Grep",
                 "--disallowedTools", "Agent,WebFetch,WebSearch",
                 "--max-turns", str(a.max_turns),
                 "--output-format", "stream-json", "--verbose", "--no-session-persistence"]
    start = time.time()
    start_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    status = "ok"
    # never let an inherited API credential switch the run to metered API billing
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    popen_kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with open(transcript, "w", encoding="utf-8") as out:
        p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=out, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", env=env, **popen_kw)
        p.stdin.write(prompt)
        p.stdin.close()
        try:
            code = p.wait(timeout=a.timeout)
        except subprocess.TimeoutExpired:
            # end only the process tree this script started
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            else:
                os.killpg(p.pid, 9)
            code = -1
            status = "timeout"
    dur = round(time.time() - start, 1)

    result = {}
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") == "result":
            result = d
    if status == "ok":
        if not result:
            status = "error_no_result"
        elif result.get("subtype") != "success" or result.get("is_error"):
            status = str(result.get("subtype") or "error")

    pe = prev_end(a.packet)
    row = {"trial_name": a.name, "packet": a.packet, "arm": a.arm, "model": a.model,
           "claude_version": version, "start_iso": start_iso, "duration_s": dur, "exit_code": code,
           "status": status, "gap_since_prev_trial_s": round(start - pe, 1) if pe else ""}
    row.update(usage_columns(transcript, trial, result))
    new = not RESULTS.exists()
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)
    manifest = capture_changes(src, trial, kitconfig.RESULTS / "trial_outputs" / a.name)
    DONE.mkdir(parents=True, exist_ok=True)
    shutil.move(str(trial), str(DONE / a.name))  # keep the trials folder to the running trial only
    print(json.dumps(row, indent=2))
    print("changes:", json.dumps({k: len(v) for k, v in manifest.items()}))
    print("moved to", DONE / a.name)
    return 0 if status == "ok" else 1  # a failed trial is never reported as success


if __name__ == "__main__":
    sys.exit(main())
