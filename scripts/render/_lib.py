"""Shared helpers for the tier-1 render-pipeline scripts.

Single home for the repo root, front-matter parsing/serialization,
change-aware file writes, and the one-pass git history reader.

Every generator routes its writes through ``write_*_if_changed`` so an
idempotent re-run never bumps an mtime: the satellite render cache
(``render_satellites.py``) fingerprints generated partials by content
and binary assets by size+mtime, and a no-op rewrite would otherwise
invalidate every page on every render.

Scripts in this directory run with their own directory on ``sys.path``
(both as Quarto hooks and from the CLI), so a plain ``import _lib``
works everywhere.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, NamedTuple

import yaml

ROOT = Path(__file__).resolve().parents[2]

# Owner used by `audit_items.py --fix` and `new_item.py` when none is given.
# Personalize this once per clone (see GETTING-STARTED.md).
DEFAULT_OWNER = "TODO Owner"

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_front_matter(text: str) -> tuple[dict | None, str]:
    """Return (front_matter_dict, body) or (None, text) if absent."""
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return None, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None, text
    body = text[m.end():]
    return fm, body


def emit_front_matter(fm: dict, field_order: Iterable[str] = ()) -> str:
    """Serialize the dict with known fields first (in ``field_order``),
    preserving anything else by appending it in source order.
    """
    ordered: dict[str, Any] = {}
    for k in field_order:
        if k in fm:
            ordered[k] = fm[k]
    for k, v in fm.items():
        if k not in ordered:
            ordered[k] = v
    text = yaml.safe_dump(
        ordered,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10_000,    # keep one-line strings on one line
    )
    return f"---\n{text}---\n"


def read_front_matter(qmd: Path) -> dict:
    """Read-only front-matter load; {} on missing file / parse error."""
    try:
        text = qmd.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        print(f"WARN: could not parse front matter in {qmd}: {exc}",
              file=sys.stderr)
        return {}


def write_text_if_changed(path: Path, text: str) -> bool:
    """Write ``text`` only when it differs from what's on disk.

    Returns True if the file was (re)written.
    """
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == text:
                return False
        except (OSError, UnicodeDecodeError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def write_bytes_if_changed(path: Path, data: bytes) -> bool:
    """Binary twin of ``write_text_if_changed``."""
    if path.exists():
        try:
            if path.read_bytes() == data:
                return False
        except OSError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def stat_manifest(base: Path, paths: Iterable[Path]) -> list[list]:
    """Cheap fingerprint of file trees: sorted [relpath, size, mtime_ns].

    size+mtime instead of content hashes because asset trees run to
    gigabytes (video, CAD) — hashing them every render would cost more
    than the renders the cache avoids. Safe because all generators are
    write-only-if-changed; the worst case (fresh clone resets mtimes)
    is one spurious re-render, never a stale page.
    """
    entries: list[list] = []
    for p in paths:
        if p.is_file():
            st = p.stat()
            entries.append([p.relative_to(base).as_posix(),
                            st.st_size, st.st_mtime_ns])
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    st = f.stat()
                    entries.append([f.relative_to(base).as_posix(),
                                    st.st_size, st.st_mtime_ns])
    entries.sort()
    return entries


class Commit(NamedTuple):
    sha: str
    date: str      # YYYY-MM-DD
    author: str
    subject: str


_GIT_LOG_PRETTY = "--pretty=format:\x01%H\x09%ad\x09%an\x09%s"


def git_file_history(root: Path = ROOT) -> dict[str, list[Commit]]:
    """Per-file commit history (newest first) from ONE ``git log`` pass.

    Returns {} when git or the repo is unavailable so render hooks
    degrade to stub output instead of failing the render.
    """
    try:
        proc = subprocess.run(
            # core.quotepath=false: keep non-ASCII path bytes raw (UTF-8)
            # instead of git's default octal-escaped, double-quoted form,
            # so the keys match the as_posix() paths consumers compute.
            ["git", "-c", "core.quotepath=false", "log", "--name-only",
             "--no-renames", "--date=short", _GIT_LOG_PRETTY],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError:
        return {}
    if proc.returncode != 0:
        return {}
    history: dict[str, list[Commit]] = {}
    current: Commit | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("\x01"):
            sha, _, rest = line[1:].partition("\t")
            cdate, _, rest = rest.partition("\t")
            author, _, subject = rest.partition("\t")
            current = Commit(sha, cdate, author, subject)
        elif line.strip() and current is not None:
            history.setdefault(line.strip(), []).append(current)
    return history
