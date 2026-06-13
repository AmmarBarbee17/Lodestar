"""Generate per-item ``_files.md`` partials listing every file an item holds.

The thesis structure (CLAUDE.md v2) gives each item — experiment, feature,
issue — its own directory under
``initiatives/<initiative>/epics/<epic>/{experiments,features,issues}/<item>/``.
Each item carries a `README.qmd` plus subdirectories for data, images,
videos, and per-item media. Many of those files (CAD `.step`, Blender
`.blend`, OBJ meshes, raw video frames, scan outputs) **don't render to
HTML**, so a reader of the rendered item page can't easily see what else
the item owns on disk.

This script generates a ``_files.md`` partial inside each item directory
that lists everything the item references — files on disk grouped by
subdir, plus external embeds (OneDrive, Google Drive) parsed from the
README. The item's ``README.qmd`` includes the partial at the bottom via
``{{< include _files.md >}}``, so the rendered page closes with an
authoritative file inventory.

Runs as a pre-render hook (see ``_quarto.yml``) and idempotent. Also safe
to invoke from the ``/disperse`` skill after the inbox-to-repo move so
new dispersed files appear in the inventory immediately.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from _lib import ROOT, write_text_if_changed

INITIATIVES_DIR = ROOT / "initiatives"
ITEM_KINDS = ("experiments", "features", "issues")
SUBDIR_ORDER = ("data", "images", "videos", "media")
SKIP_NAMES = {
    ".gitkeep",
    ".DS_Store",
    "Thumbs.db",
    "_files.md",
    "_listing.md",
    "_listing.yml",
    "_revisions.md",
}
SKIP_DIRS = {"__pycache__", ".quarto"}
TREE_MAX_DEPTH = 4

# External-embed patterns parsed from README markdown. Add new platforms
# here if/when the project starts embedding from them.
EMBED_PATTERNS = [
    ("OneDrive (SharePoint Stream)",
     re.compile(r"UniqueId=([0-9a-f-]{36})", re.IGNORECASE)),
    ("Google Drive",
     re.compile(r"drive\.google\.com/file/d/([\w-]+)")),
    ("YouTube",
     re.compile(r"(?:youtube\.com/embed/|youtu\.be/)([\w-]{11})")),
]


def iter_items():
    """Yield every item directory under initiatives/<I>/epics/<E>/<kind>/."""
    if not INITIATIVES_DIR.exists():
        return
    for initiative in sorted(INITIATIVES_DIR.iterdir()):
        if not initiative.is_dir() or initiative.name.startswith("_"):
            continue
        epics_dir = initiative / "epics"
        if not epics_dir.exists():
            continue
        for epic in sorted(epics_dir.iterdir()):
            if not epic.is_dir():
                continue
            for kind in ITEM_KINDS:
                kind_dir = epic / kind
                if not kind_dir.exists():
                    continue
                for item in sorted(kind_dir.iterdir()):
                    if item.is_dir() and (item / "README.qmd").exists():
                        yield item


def walk_subdir(subdir: Path, item_root: Path, depth: int = 0) -> list[str]:
    """Return indented markdown bullets for everything under ``subdir``.

    Files are listed at each level; directories recurse up to
    ``TREE_MAX_DEPTH``. Paths are shown relative to the item root so the
    user reads them the same way they'd type them.
    """
    lines: list[str] = []
    if depth >= TREE_MAX_DEPTH:
        return lines
    entries = sorted(
        subdir.iterdir(),
        key=lambda p: (not p.is_dir(), p.name.lower()),
    )
    for entry in entries:
        if entry.name in SKIP_NAMES:
            continue
        if entry.is_dir() and entry.name in SKIP_DIRS:
            continue
        rel = entry.relative_to(item_root).as_posix()
        indent = "  " * depth
        if entry.is_dir():
            children = walk_subdir(entry, item_root, depth + 1)
            lines.append(f"{indent}- **`{rel}/`**")
            if children:
                lines.extend(children)
            else:
                lines.append(f"{indent}  - *(empty)*")
        else:
            # Render as a clickable markdown link so non-renderable
            # binaries (CAD, .blend, .obj, etc.) download directly from
            # the page. `render_satellites.py` already mirrors data/,
            # images/, videos/, media/ into _site/<item>/ so the relative
            # href resolves at serve time.
            lines.append(f"{indent}- [`{rel}`]({rel})")
    return lines


def collect_root_files(item_dir: Path) -> list[str]:
    """Loose files directly under the item dir (excluding subdirs)."""
    return sorted(
        f.name for f in item_dir.iterdir()
        if f.is_file() and f.name not in SKIP_NAMES
    )


def find_embeds(item_dir: Path) -> list[tuple[str, str, str]]:
    """Scan all readable text files for known embed signatures.

    Returns ``(platform, identifier, source_filename)`` triples.
    """
    found: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(item_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".qmd", ".md", ".txt", ".yml", ".yaml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(item_dir).as_posix()
        for label, pattern in EMBED_PATTERNS:
            for match in pattern.finditer(text):
                ident = match.group(1)
                key = (label, ident)
                if key in seen:
                    continue
                seen.add(key)
                found.append((label, ident, rel))
    return found


def render_item_partial(item_dir: Path) -> str:
    lines: list[str] = [
        "<!-- Auto-generated by scripts/render/build_file_trees.py.",
        "     Do not edit by hand — re-run the script or `quarto render`. -->",
        "",
        "## Files",
        "",
    ]

    # On-disk tree
    subdir_sections: list[tuple[str, list[str]]] = []
    for name in SUBDIR_ORDER:
        sub = item_dir / name
        if sub.exists() and sub.is_dir():
            bullets = walk_subdir(sub, item_dir)
            subdir_sections.append((name, bullets))
    # Any other subdirs the item happens to contain (e.g. `scripts/`)
    other = sorted(
        p for p in item_dir.iterdir()
        if p.is_dir()
        and p.name not in SUBDIR_ORDER
        and p.name not in SKIP_DIRS
        and not p.name.startswith(".")
    )
    for sub in other:
        bullets = walk_subdir(sub, item_dir)
        subdir_sections.append((sub.name, bullets))

    root_files = collect_root_files(item_dir)

    if not subdir_sections and not root_files:
        lines.append("*(no files)*")
        lines.append("")
    else:
        for name, bullets in subdir_sections:
            lines.append(f"**`{name}/`**")
            lines.append("")
            if bullets:
                lines.extend(bullets)
            else:
                lines.append("- *(empty)*")
            lines.append("")
        if root_files:
            lines.append("**Root**")
            lines.append("")
            for fname in root_files:
                lines.append(f"- [`{fname}`]({fname})")
            lines.append("")

    embeds = find_embeds(item_dir)
    if embeds:
        lines.append("### External media")
        lines.append("")
        for label, ident, source in embeds:
            lines.append(f"- {label}: `{ident}` *(referenced in `{source}`)*")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    written = 0
    for item in iter_items():
        partial = render_item_partial(item)
        target = item / "_files.md"
        if not write_text_if_changed(target, partial):
            continue
        written += 1
        print(f"  wrote {target.relative_to(ROOT)}")
    if written == 0:
        print("file-trees: nothing to update")
    else:
        print(f"file-trees: {written} partial(s) regenerated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
