# /// script
# requires-python = ">=3.10"
# ///
"""Publish orchestrator: render -> link_check -> prose_check -> publish gh-pages.

Stops on a failing render or broken internal links; prose checks are advisory
(don't gate). Run a manual grammar pass via the /grammar-review Claude Code
skill before invoking this for a final pre-publish polish.

Run:  python scripts/render/publish.py"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


PRERENDER = ["build_listings.py", "build_gantt.py", "build_file_trees.py",
             "build_revisions.py", "build_board.py"]


def run(cmd: list[str]) -> int:
    print("==", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    if run([sys.executable, str(HERE / "audit_items.py")]) != 0:
        print("publish: item front-matter drift — run audit_items.py --fix.")
        return 1
    # Prime the generated include partials before `quarto render`: the book
    # expands `{{< include _board.md >}}` (and the SOP `_revisions-*.md`)
    # at config time, BEFORE the pre-render hooks run, so a fresh clone
    # would fail the render without this. Write-only-if-changed, so this is
    # a no-op on a warm tree.
    for script in PRERENDER:
        if run([sys.executable, str(HERE / script)]) != 0:
            print(f"publish: {script} FAILED — aborting.")
            return 1
    if run(["quarto", "render"]) != 0:
        print("publish: render FAILED — aborting.")
        return 1
    if run([sys.executable, str(HERE / "qc" / "link_check.py")]) != 0:
        print("publish: broken local links — fix before publishing.")
        return 1
    run([sys.executable, str(HERE / "qc" / "prose_check.py")])  # advisory
    if run(["quarto", "publish", "gh-pages", "--no-prompt"]) != 0:
        print("publish: gh-pages publish FAILED.")
        return 1
    print("publish: done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
