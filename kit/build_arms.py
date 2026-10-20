"""Build the two context arms for one packet.

harness/ = the frozen tree (plus the packet's fixture overlay, if any) exactly as it was at the cutoff.
bloat/   = the same tree, but the context files listed in packet.json "sources" (for example the project's
           CLAUDE.md and CHECKPOINT.md) are removed and replaced by ONE CLAUDE.md at the project folder
           holding their text in order, each under its own heading. Only the patterns in "drops" are
           removed (lines that only make sense when there are two files, such as "read CHECKPOINT.md
           first"); every drop is printed so the difference between the arms is auditable.
           In the paper this arm is called the comparison arm.

Then two audits:
  fact audit       every regex in packet.json "facts" must match some .md file in both arms
  exact line audit the merged file holds every source line (after drops) in order and nothing else, and
                   no other file differs between the arms

Usage: python build_arms.py <packet id> [--audit-only]
Writes packets/<id>/arms/ and packets/<id>/fact_audit.json. Exit 0 only if both audits pass.

packet.json keys used here:
  project  folder (relative to the arm root) where the agent starts and where the merged CLAUDE.md goes
  sources  list of [relative path, heading] in merge order
  drops    list of regular expressions removed from source lines
  facts    {fact id: regular expression} for the fact audit
"""
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the driver runs scripts with python -I
import kitconfig  # noqa: E402

GENERATED = ["# Project notes", "", "Everything known about this project, in one file.", ""]


def merged_text(arm_root: Path, cfg: dict) -> tuple[str, list[str]]:
    dropped = []
    parts = list(GENERATED)
    for rel, heading in cfg["sources"]:
        text = (arm_root / rel).read_text(encoding="utf-8-sig")
        parts.append(f"# {heading} (was `{rel}`)")
        parts.append("")
        for line in text.splitlines():
            new = line
            for pat in cfg["drops"]:
                if re.search(pat, new):
                    newer = re.sub(pat, "", new)
                    dropped.append(f"{rel}: {line.strip()[:160]}")
                    new = newer
            if line.strip() and not new.strip():
                continue  # whole line was a drop
            # demote headings one level so each source sits under its own heading
            if new.startswith("#"):
                new = "#" + new
            parts.append(new.rstrip())
        parts.append("")
    return "\n".join(parts) + "\n", dropped


def fact_audit(root: Path, facts: dict) -> dict:
    corpus = ""
    for p in root.rglob("*.md"):
        corpus += p.read_text(encoding="utf-8-sig", errors="replace") + "\n"
    return {k: bool(re.search(v, corpus, re.IGNORECASE)) for k, v in facts.items()}


def exact_line_audit(harness: Path, bloat: Path, cfg: dict) -> dict:
    """missing = source lines (after drops) absent from the merged CLAUDE.md;
    extra = merged lines that come from no source (only the generated headings may be extra);
    in_order = the merged text is exactly the sources, in order;
    other_files_differ = files other than the context files that differ between the arms (must be none)."""
    merged = (bloat / cfg["project"] / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    want = []
    for rel, heading in cfg["sources"]:
        want.append(f"# {heading} (was `{rel}`)")
        for line in (harness / rel).read_text(encoding="utf-8-sig").splitlines():
            new = line
            for pat in cfg["drops"]:
                new = re.sub(pat, "", new)
            if line.strip() and not new.strip():
                continue
            want.append(("#" + new if new.startswith("#") else new).rstrip())
    generated = {x for x in GENERATED if x}
    have = [x for x in merged if x.strip()]
    need = [x for x in want if x.strip()]
    missing = [x for x in need if x not in set(have)]
    extra = [x for x in have if x not in set(need) and x not in generated]
    in_order = [x for x in have if x not in generated] == need
    ctx = {Path(r).as_posix() for r, _ in cfg["sources"]} | {Path(cfg["project"], "CLAUDE.md").as_posix()}

    def files(root):
        return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    hf, bf = files(harness), files(bloat)
    differ = sorted(r for r in (set(hf) | set(bf)) - ctx
                    if r not in hf or r not in bf or hf[r].read_bytes() != bf[r].read_bytes())
    return {"missing": missing, "extra": extra, "in_order": in_order, "other_files_differ": differ,
            "ok": not missing and not extra and in_order and not differ}


def main(pid: str, audit_only: bool) -> int:
    allp = kitconfig.packets()
    if pid not in allp:
        print(f"no packet {pid!r} under {kitconfig.PACKETS_DIR}", file=sys.stderr)
        return 2
    cfg = allp[pid]
    pdir = cfg["dir"]
    if audit_only:
        ex = exact_line_audit(pdir / "arms" / "harness", pdir / "arms" / "bloat", cfg)
        audit = json.loads((pdir / "fact_audit.json").read_text(encoding="utf-8"))
        audit["exact_line_audit"] = ex
        audit["all_facts_both_arms"] = audit["all_facts_both_arms"] and ex["ok"]
        (pdir / "fact_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
        print(json.dumps(ex, indent=2)[:3000])
        return 0 if ex["ok"] else 1
    arms = pdir / "arms"
    if arms.exists():
        shutil.rmtree(arms)
    harness = arms / "harness"
    shutil.copytree(pdir / "freeze", harness)
    fixture = pdir / "fixture"
    if fixture.exists():
        shutil.copytree(fixture, harness, dirs_exist_ok=True)

    bloat = arms / "bloat"
    shutil.copytree(harness, bloat)
    text, dropped = merged_text(bloat, cfg)
    for rel, _ in cfg["sources"]:
        (bloat / rel).unlink()
    (bloat / cfg["project"] / "CLAUDE.md").write_text(text, encoding="utf-8")

    audit = {"harness": fact_audit(harness, cfg["facts"]),
             "bloat": fact_audit(bloat, cfg["facts"]),
             "dropped": dropped,
             "bloat_claude_md_bytes": len(text.encode("utf-8"))}
    audit["exact_line_audit"] = exact_line_audit(harness, bloat, cfg)
    audit["all_facts_both_arms"] = (all(audit["harness"].values()) and all(audit["bloat"].values())
                                    and audit["exact_line_audit"]["ok"])
    (pdir / "fact_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))
    return 0 if audit["all_facts_both_arms"] else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], "--audit-only" in sys.argv[2:]))
