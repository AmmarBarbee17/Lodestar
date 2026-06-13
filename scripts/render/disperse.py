"""Stage a week's raw dumps from the OneDrive thesis-inbox into the repo.

This is the deterministic *staging* half of the weekly dispersal workflow.
It copies the inbox folder (where you drop photos, videos, CAD, and a rolling
`notes-week-NN.md` from any device via OneDrive) into
``<repo>/_inbox/<YYYY-Www>/`` and writes a `_manifest.md` listing what landed.

The *routing* half — turning that staged dump into a weekly-update deck plus
files moved into the right ``initiatives/<I>/epics/<E>/experiments/<EX>/`` /
``updates/<WU>/media/`` / ``archive/`` / ``data/`` locations — is done by the
``/disperse`` Claude Code skill (see ``.claude/skills/disperse/SKILL.md``),
which reads this manifest and proposes routes for your approval. This script
deliberately does no routing: it only makes a safe, reviewable copy.

Usage
-----
    python scripts/disperse.py [--week 2026-W22] [--source PATH]

``--source`` defaults to the ``THESIS_INBOX`` environment variable. Set it once:
    setx THESIS_INBOX "C:\\Users\\<you>\\OneDrive - ...\\thesis-inbox\\current"
``--week`` defaults to the current ISO week.

The staged ``_inbox/<week>/`` is gitignored and kept as an audit trail; delete
it manually once a week's dispersal is committed and it has grown large.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INBOX = ROOT / "_inbox"


def iso_week(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Stage OneDrive thesis-inbox dumps into _inbox/<week>/.")
    ap.add_argument("--week", default=iso_week(date.today()),
                    help="ISO week tag, e.g. 2026-W22 (default: current week)")
    ap.add_argument("--source", default=os.environ.get("THESIS_INBOX"),
                    help="Inbox folder to stage from (default: $THESIS_INBOX)")
    args = ap.parse_args(argv)

    if not args.source:
        print(
            "ERROR: no --source given and $THESIS_INBOX is not set.\n"
            "Set it once (PowerShell):\n"
            '  setx THESIS_INBOX "C:\\Users\\<you>\\OneDrive - ...\\thesis-inbox\\current"\n'
            "or pass --source PATH.",
            file=sys.stderr)
        return 2

    source = Path(args.source)
    if not source.exists():
        print(f"ERROR: source folder does not exist: {source}", file=sys.stderr)
        return 2

    dest = INBOX / args.week
    dest.mkdir(parents=True, exist_ok=True)

    copied: list[tuple[Path, int]] = []
    for src_file in sorted(source.rglob("*")):
        if src_file.is_dir() or src_file.name.startswith("~$"):
            continue  # skip dirs and Office lock files
        rel = src_file.relative_to(source)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, target)
        copied.append((rel, src_file.stat().st_size))

    notes = [rel for rel, _ in copied if rel.name.lower().startswith("notes")]
    lines = [
        f"# Inbox staging manifest — {args.week}",
        "",
        f"- Source: `{source}`",
        f"- Staged: **{len(copied)}** files into `_inbox/{args.week}/`",
        "",
        "## Rolling notes",
        "",
        (", ".join(f"`{n.as_posix()}`" for n in notes) if notes
         else "_No `notes-*` file found in the dump._"),
        "",
        "## Files",
        "",
        "| File | Size |",
        "|---|---|",
    ]
    lines += [f"| `{rel.as_posix()}` | {human_size(size)} |"
              for rel, size in copied]
    lines += [
        "",
        "---",
        "Next: run the `/disperse` skill in Claude Code, pointed at this folder, "
        "to propose routes (weekly-update draft + file moves) for approval.",
    ]
    manifest = dest / "_manifest.md"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Staged {len(copied)} files into {dest.relative_to(ROOT)}/")
    print(f"Wrote manifest: {manifest.relative_to(ROOT)}")
    if notes:
        print(f"Rolling notes: {', '.join(n.as_posix() for n in notes)}")
    print("Next: run the /disperse skill in Claude Code against this folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
