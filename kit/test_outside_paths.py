"""Tests for the void rule in run_trial.py (outside_paths + is_void). No model calls, no network.

Writes a throwaway kit config into a temp folder (trials under C:/kittest/trials), feeds one synthetic tool call
per case through outside_paths, and checks whether the trial would be voided.
Run: python test_outside_paths.py   (exit 0 = all cases pass). The path matcher targets Windows hosts.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
cfg_dir = tempfile.mkdtemp(prefix="kittest_cfg_")
cfg = Path(cfg_dir) / "kit_config.json"
cfg.write_text(json.dumps({
    "root": "C:/kittest/workspace", "trials_dir": "C:/kittest/trials", "done_dir": "C:/kittest/done",
    "worker_model": "worker-model", "judge_model": "judge-model", "claude_cmd": ["claude"],
    "leak_patterns": ["my-private-notes"], "benign_prefixes": ["C:/tools/npm"]}), encoding="utf-8")
os.environ["KIT_CONFIG"] = str(cfg)
sys.path.insert(0, str(HERE))
import run_trial as rt  # noqa: E402

# True = the trial must be voided
cases = {
    "cat /c/$HOME/private.txt": True,
    "ls /d/": True,
    "cd /d/ && ls": True,
    "ls /c/Users/x": True,
    r"type C:\Users\x\a.txt": True,
    'ls "/c/Program Files/SomeTool/tool.exe"': False,
    "sed -i '0,/^param(/s//$ErrorActionPreference = 1/' scripts/a.ps1": False,
    "ls /c/kittest/trials/tname/scripts": False,
    "echo a/b/c and/or": False,
    "ls C:/": True,
    r"Get-ChildItem D:\ ": True,
    "ls /c//Users/public": True,
    "cat C:/kittest/trials/tname/../../private.txt": True,
    "cat C:/kittest/trials/tname/scripts/../README.md": False,
    "echo https://example.com/a": False,
    # allowlist and the bare trials root
    "ls /c/tools/npm/node_modules": False,
    "ls /c/kittest/trials": False,
    "ls /c/tools/npm-backup": True,
    r'Get-Content "C:\tools\npm\..\..\secret.txt"': True,
    # git -C must provably stay inside the copy
    "git -C sub status": False,
    "cd /c/kittest/trials/tname/proj && git -C sub log": False,
    r"git -C C:\kittest\trials\tname\..\..\workspace show HEAD:runs.json": True,
    "cd ~; git -C . show HEAD:answer.md": True,
    "git -C D:private-project show HEAD:answer.md": True,
    # network commands, including git/gh fetches
    "git -C . clone https://example.com/project.git downloaded": True,
    "git fetch origin": True,
    "gh repo clone someone/project": True,
    "curl http://localhost:8000/": True,
    # workspace, done folder, other trials, user-listed private folders
    "cat C:/kittest/workspace/results/v4-results.csv": True,
    "ls C:/kittest/done": True,
    "ls ../other-p1-harness": True,
    "cat notes/my-private-notes/x.md": True,
}
bad = 0
for cmd, want in cases.items():
    with tempfile.TemporaryDirectory() as d:
        tr = Path(d) / "t.jsonl"
        tr.write_text(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}) + "\n", encoding="utf-8")
        got = rt.outside_paths(tr, Path("tname"))
        ok = rt.is_void(got, "tname") == want
        bad += not ok
        print("ok " if ok else "BAD", cmd, got)
print("failures:", bad)
sys.exit(1 if bad else 0)
