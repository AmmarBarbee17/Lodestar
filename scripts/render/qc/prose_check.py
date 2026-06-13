# /// script
# requires-python = ">=3.10"
# ///
"""Prose check orchestrator — invokes cspell and Vale if they're on PATH; reports
results, doesn't gate render. Designed to be invoked pre-publish (alongside
link_check.py and an optional Claude grammar pass via the /grammar-review
skill). Both tools opt-in: if absent, prints how to install, continues.

Run:  python scripts/render/qc/prose_check.py [path-glob]"""
from __future__ import annotations
import shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def run_cspell() -> int:
    if not have("cspell"):
        print("prose_check: cspell not found — install with "
              "`npm i -g cspell` (uses the project .cspell.json).")
        return 0
    return subprocess.call(
        ["cspell", "--no-progress", "**/*.qmd", "**/*.md"], cwd=ROOT)


def run_vale() -> int:
    if not have("vale"):
        print("prose_check: vale not found — install via "
              "https://vale.sh/docs/vale-cli/installation/  (optional).")
        return 0
    return subprocess.call(["vale", "--no-exit", "chapters", "initiatives"],
                           cwd=ROOT)


def main() -> int:
    rc1 = run_cspell()
    rc2 = run_vale()
    return rc1 | rc2  # don't gate the render; CI can decide what to do with rc


if __name__ == "__main__":
    raise SystemExit(main())
