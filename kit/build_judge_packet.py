"""Build the blind judge's artifact packet for one trial (or judge fixture).

Usage:
  python build_judge_packet.py --trial <dir> --freeze <dir> [--fixture <dir>] --out <file.json>
  (for a real trial, --freeze is the trial's own arm folder, e.g. packets/<id>/arms/harness)

Notes-file handling: where a submission records its write-up is not scored, and the judge must see it
either way.

Baseline = the freeze tree, overlaid with the fixture tree when given (synthetic data a packet adds sits
at the same relative root). The packet holds every file that is new, edited, moved or deleted in the
trial versus that baseline:
  - new text file    -> full text
  - edited text file -> unified diff against the baseline
  - moved file       -> "moved from X" when its bytes equal a deleted baseline file (no text repeated)
  - deleted file     -> name only
  - binary file      -> name only
Project notes files (any CLAUDE.md or CHECKPOINT.md, and archive/harness_changelog.md) are not shown
whole: only the lines a submission ADDED or changed in them are shown, all notes files together as ONE
entry named "project notes file (added text)", without file names or line numbers (both differ
between arms). Deleted notes files and removed notes lines are listed for the analyst only.
Excluded entirely (listed in the JSON for the analyst): transcripts and tool state (*.jsonl, anything
under .claude/, .git/, __pycache__/).

Redaction: in all packet text (file text, diffs, notes text, paths), the literal file names
CHECKPOINT.md and CLAUDE.md, with any path prefix and optional surrounding backticks, are replaced by
"the project notes file". Every replacement is logged in cue_audit.redacted (file:line, original).
Nothing else in the artifact text is altered.

Cue audit (after redaction) lists remaining arm cues in the text the judge would see (file:line):
  - "label": the path or a line names an arm outright (ARM_LABEL-style file, "arm: <name>").
             run_judge.py always refuses a packet with label hits.
  - "vocab": wording that can hint at an arm (checkpoint, harness, bloat, open threads,
             harness changelog). run_judge.py refuses these unless --allow-cues.
Output: JSON (schema v4-judge-packet/2) with `rendered` = exactly the text the judge sees.
The trial/freeze paths are metadata only and never rendered (trial names carry arm labels).
"""
import argparse
import difflib
import json
import os
import re
import sys
from datetime import datetime, timezone

CONTEXT_NAMES = {"claude.md", "checkpoint.md"}
CONTEXT_SUFFIXES = ("archive/harness_changelog.md",)
TOOL_DIRS = {".claude", ".git", "__pycache__"}
MAX_TEXT_BYTES = 200_000  # larger text files are shown as a head excerpt and flagged
NOTES_ENTRY = "project notes file (added text)"
NOTES_PHRASE = "the project notes file"
# File names in any case; a bare upper-case CHECKPOINT ("the CHECKPOINT entries") too.
NOTES_NAME_RX = re.compile(r"`?(?:[A-Za-z0-9_.~\-]+[/\\])*(?:(?i:checkpoint\.md|claude\.md)|CHECKPOINT)`?")
HEADING_RX = re.compile(r"^#{1,6}(?=\s)")
LAYOUT_RX = re.compile(r"harness\s+changelog", re.I)

VOCAB = [
    ("harness changelog", re.compile(r"harness\s+changelog", re.I)),
    ("open threads", re.compile(r"open\s+threads", re.I)),
    ("checkpoint", re.compile(r"checkpoint", re.I)),
    ("harness", re.compile(r"harness", re.I)),
    ("bloat", re.compile(r"bloat", re.I)),
]
LABEL_LINE = re.compile(r"\barm\s*[:=]", re.I)
LABEL_PATH = re.compile(r"arm[\s_\-]?label|(^|/)arm\.(txt|md|json)$", re.I)


def rel_files(root):
    out = {}
    if not root:
        return out
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(dns)
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            out[rel] = full
    return out


def classify(rel):
    parts = rel.split("/")
    low = rel.lower()
    if any(p in TOOL_DIRS for p in parts[:-1]) or low.endswith(".jsonl"):
        return "transcript_or_tool_state"
    if parts[-1].lower() in CONTEXT_NAMES or any(low.endswith(s) for s in CONTEXT_SUFFIXES):
        return "notes"
    return None


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def as_text(b):
    """Return decoded text, or None for binary."""
    if b"\x00" in b[:8192]:
        return None
    try:
        return b.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return b.decode("cp1252")
        except UnicodeDecodeError:
            return None


def norm(t):
    return t.replace("\r\n", "\n").replace("\r", "\n")


def notes_added(rel, old_text, new_text):
    """Segments of lines added or changed in a notes file: [{source, start_line, lines}]."""
    o = norm(old_text).split("\n") if old_text is not None else []
    n = norm(new_text).split("\n")
    segs, removed = [], 0
    sm = difflib.SequenceMatcher(None, o, n, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            # One heading depth for all notes text: the single-file arm demotes its headings a level.
            lines = [HEADING_RX.sub("###", x) for x in n[j1:j2]]
            while lines and not lines[-1].strip():  # trailing blank lines carry nothing
                lines = lines[:-1]
            if any(x.strip() for x in lines):
                segs.append({"source": rel, "start_line": j1 + 1, "lines": lines})
        if tag in ("replace", "delete"):
            removed += i2 - i1
    return segs, removed


def build(trial, freeze, fixture):
    base = rel_files(freeze)
    base.update(rel_files(fixture))  # fixture overlays freeze
    cur = rel_files(trial)
    excluded, entries, notes_segs, notes_meta = [], [], [], []

    deleted = {}
    for rel, full in base.items():
        if rel in cur:
            continue
        why = classify(rel)
        if why == "transcript_or_tool_state":
            excluded.append({"path": rel, "reason": why, "change": "deleted"})
        elif why == "notes":
            notes_meta.append({"source": rel, "change": "deleted", "added_lines": 0})
        else:
            deleted[rel] = read_bytes(full)
    moved_used = set()

    for rel in sorted(cur):
        b = read_bytes(cur[rel])
        if rel in base:
            ob = read_bytes(base[rel])
            if ob == b:
                continue
            change = "edited"
        else:
            ob = None
            change = "new"
        why = classify(rel)
        if why == "transcript_or_tool_state":
            excluded.append({"path": rel, "reason": why, "change": change})
            continue
        t = as_text(b)
        if why == "notes":
            ot = as_text(ob) if ob is not None else None
            if t is None:
                notes_meta.append({"source": rel, "change": change + "_binary", "added_lines": 0})
                continue
            segs, removed = notes_added(rel, ot, t)
            notes_segs.extend(segs)
            notes_meta.append({"source": rel, "change": change, "added_lines": sum(len(s["lines"]) for s in segs),
                               "removed_lines": removed})
            continue
        if change == "new":
            src = next((d for d, db in deleted.items() if db == b and d not in moved_used), None)
            if src:
                moved_used.add(src)
                entries.append({"path": rel, "status": "moved", "moved_from": src, "bytes": len(b)})
                continue
            if t is None:
                entries.append({"path": rel, "status": "new_binary", "bytes": len(b)})
                continue
            nt = norm(t)
            e = {"path": rel, "status": "new", "lines": nt.count("\n") + (0 if nt.endswith("\n") or not nt else 1),
                 "bytes": len(b)}
            if len(b) > MAX_TEXT_BYTES:
                e["text"] = nt[:MAX_TEXT_BYTES]
                e["truncated"] = True
            else:
                e["text"] = nt
            entries.append(e)
        else:
            ot = as_text(ob)
            if t is None or ot is None:
                entries.append({"path": rel, "status": "edited_binary", "bytes": len(b)})
                continue
            o, n = norm(ot), norm(t)
            if o == n:
                entries.append({"path": rel, "status": "edited_line_endings_only", "bytes": len(b)})
                continue
            diff = "".join(difflib.unified_diff(o.splitlines(True), n.splitlines(True),
                                                fromfile="frozen/" + rel, tofile="submission/" + rel, n=3))
            if not diff.endswith("\n"):
                diff += "\n"
            entries.append({"path": rel, "status": "edited", "diff": diff, "bytes": len(b)})

    for rel in sorted(deleted):
        if rel not in moved_used:
            entries.append({"path": rel, "status": "deleted"})
    if notes_segs:
        entries.append({"path": NOTES_ENTRY, "status": "notes_added", "segments": notes_segs,
                        "lines": sum(len(s["lines"]) for s in notes_segs)})
    return entries, excluded, notes_meta


# ---------- redaction ----------

def redact_str(s, log, file, line, where):
    def sub(m):
        log.append({"file": file, "line": line, "where": where, "original": m.group(0),
                    "line_excerpt": s.strip()[:200]})
        return NOTES_PHRASE

    def sub_layout(m):
        log.append({"file": file, "line": line, "where": where, "original": m.group(0),
                    "line_excerpt": s.strip()[:200]})
        return "changelog"
    # Layout term from the harness convention; both arms carry it, but it reads as an arm label.
    return LAYOUT_RX.sub(sub_layout, NOTES_NAME_RX.sub(sub, s))


def iter_diff(diff):
    """Yield (raw, tag, body, number, where) for each diff line; number is the new-file line for
    added/context lines and the frozen-copy line for removed lines; 0 for header lines."""
    old_no = new_no = 0
    for ln in diff.split("\n"):
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", ln)
        if m:
            old_no, new_no = int(m.group(1)), int(m.group(2))
            yield ln, "@", ln, 0, "hunk header"
            continue
        if ln.startswith("---") or ln.startswith("+++"):
            yield ln, "h", ln, 0, "diff header"
            continue
        if not ln:
            yield ln, "", "", 0, "blank"
            continue
        tag, body = ln[0], ln[1:]
        if tag == "+":
            yield ln, tag, body, new_no, "added line"
            new_no += 1
        elif tag == "-":
            yield ln, tag, body, old_no, "removed line (frozen copy line)"
            old_no += 1
        else:
            yield ln, tag, body, new_no, "context line"
            old_no += 1
            new_no += 1


def redact_entries(entries):
    log = []
    for e in entries:
        if e["status"] != "notes_added":
            e["path"] = redact_str(e["path"], log, e["path"], 0, "path")
        if e.get("moved_from"):
            e["moved_from"] = redact_str(e["moved_from"], log, e["path"], 0, "moved_from")
        if "text" in e:
            e["text"] = "\n".join(redact_str(ln, log, e["path"], i, "new file")
                                  for i, ln in enumerate(e["text"].split("\n"), 1))
        if "diff" in e:
            out = []
            for raw, tag, body, num, where in iter_diff(e["diff"]):
                if tag in ("+", "-", " "):
                    out.append(tag + redact_str(body, log, e["path"], num, where))
                else:
                    out.append(redact_str(raw, log, e["path"], num, where))
            e["diff"] = "\n".join(out)
        if e["status"] == "notes_added":
            for s in e["segments"]:
                s["lines"] = [redact_str(ln, log, s["source"], s["start_line"] + k, "notes added text")
                              for k, ln in enumerate(s["lines"])]
    return log


# ---------- render + audit ----------

def render(entries):
    if not entries:
        return "(No new or changed files.)\n"
    out = []
    for e in entries:
        p, s = e["path"], e["status"]
        if s == "new":
            note = " (first %d characters only; file is %d bytes)" % (MAX_TEXT_BYTES, e["bytes"]) if e.get("truncated") else ""
            out.append("=== File: %s (new file, %d lines)%s ===\n%s" % (p, e["lines"], note, e["text"]))
            if not e["text"].endswith("\n"):
                out.append("\n")
            out.append("=== End of file: %s ===\n\n" % p)
        elif s == "edited":
            out.append("=== File: %s (edited; unified diff against the frozen copy) ===\n%s=== End of diff: %s ===\n\n"
                       % (p, e["diff"] if e["diff"].endswith("\n") else e["diff"] + "\n", p))
        elif s == "moved":
            out.append("=== File: %s (moved from %s, content unchanged) ===\n\n" % (p, e["moved_from"]))
        elif s == "deleted":
            out.append("=== File: %s (deleted) ===\n\n" % p)
        elif s == "new_binary":
            out.append("=== File: %s (new binary file, %d bytes, not shown) ===\n\n" % (p, e["bytes"]))
        elif s == "edited_binary":
            out.append("=== File: %s (changed binary file, %d bytes, not shown) ===\n\n" % (p, e["bytes"]))
        elif s == "edited_line_endings_only":
            out.append("=== File: %s (line endings changed only) ===\n\n" % p)
        elif s == "notes_added":
            body = "\n[...]\n".join("\n".join(seg["lines"]) for seg in e["segments"])
            out.append("=== File: %s ===\n(Only the lines this submission added or changed in the project's own "
                       "notes are shown; the rest of the notes is not.)\n%s\n=== End of %s ===\n\n"
                       % (NOTES_ENTRY, body, NOTES_ENTRY))
    return "".join(out)


def scan_line(text):
    terms = []
    for name, rx in VOCAB:
        if rx.search(text):
            terms.append(name)
    if "harness changelog" in terms and "harness" in terms:
        rest = re.sub(r"harness\s+changelog", "", text, flags=re.I)
        if not re.search(r"harness", rest, re.I):
            terms.remove("harness")
    return terms


def hit(hits, file, line, where, body):
    lab = bool(LABEL_LINE.search(body))
    terms = scan_line(body)
    if lab or terms:
        hits.append({"file": file, "line": line, "where": where, "class": "label" if lab else "vocab",
                     "terms": (["arm: label"] if lab else []) + terms, "excerpt": body.strip()[:200]})


def cue_audit(entries):
    hits = []
    for e in entries:
        p = e["path"]
        if e["status"] != "notes_added":
            pterms = scan_line(p)
            if LABEL_PATH.search(p):
                hits.append({"file": p, "line": 0, "where": "path", "class": "label",
                             "terms": ["arm label file name"] + pterms, "excerpt": p})
            elif pterms:
                hits.append({"file": p, "line": 0, "where": "path", "class": "vocab", "terms": pterms, "excerpt": p})
        if e.get("moved_from"):
            hit(hits, p, 0, "moved_from", e["moved_from"])
        if "text" in e:
            for i, ln in enumerate(e["text"].split("\n"), 1):
                hit(hits, p, i, "new file", ln)
        if "diff" in e:
            for raw, tag, body, num, where in iter_diff(e["diff"]):
                if tag in ("+", "-", " "):
                    hit(hits, p, num, where, body)
        if e["status"] == "notes_added":
            for s in e["segments"]:
                for k, ln in enumerate(s["lines"]):
                    hit(hits, s["source"], s["start_line"] + k, "notes added text", ln)
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trial", required=True)
    ap.add_argument("--freeze", required=True)
    ap.add_argument("--fixture")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    for label, d in (("trial", a.trial), ("freeze", a.freeze), ("fixture", a.fixture)):
        if d and not os.path.isdir(d):
            print("missing %s dir: %s" % (label, d), file=sys.stderr)
            return 2
    entries, excluded, notes_meta = build(a.trial, a.freeze, a.fixture)
    redacted = redact_entries(entries)
    rendered = render(entries)
    hits = cue_audit(entries)
    labels = [h for h in hits if h["class"] == "label"]
    pkt = {
        "schema": "v4-judge-packet/2",
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"trial_dir": os.path.abspath(a.trial), "freeze_dir": os.path.abspath(a.freeze),
                   "fixture_dir": os.path.abspath(a.fixture) if a.fixture else None,
                   "note": "metadata only; never rendered to the judge"},
        "summary": {"files_shown": len(entries),
                    "by_status": {s: sum(1 for e in entries if e["status"] == s) for s in sorted({e["status"] for e in entries})},
                    "notes_files_changed": notes_meta, "excluded": len(excluded), "rendered_chars": len(rendered)},
        "files": entries,
        "excluded": excluded,
        "cue_audit": {"clean": not hits, "label_hits": len(labels), "vocab_hits": len(hits) - len(labels),
                      "hits": hits, "redacted_count": len(redacted), "redacted": redacted},
        "rendered": rendered,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(pkt, f, indent=2, ensure_ascii=False)
    print("%s: %d entr(ies) shown %s, notes changed %s, %d excluded, %d redacted, cue hits: %d label, %d vocab"
          % (a.out, len(entries), pkt["summary"]["by_status"],
             [(m["source"], m["change"], m["added_lines"]) for m in notes_meta], len(excluded), len(redacted),
             len(labels), len(hits) - len(labels)))
    for r in redacted:
        print("  REDACTED %s:%s (%s) %r" % (r["file"], r["line"], r["where"], r["original"]))
    for h in hits:
        print("  CUE [%s] %s:%s (%s) %s :: %s" % (h["class"], h["file"], h["line"], h["where"], ",".join(h["terms"]),
                                                h["excerpt"][:100]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
