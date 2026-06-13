"""Build listing manifests for Quarto appendix pages.

Quarto book projects don't extract front matter from files outside
`book.chapters` / `book.appendices`, which leaves appendix listings
(updates, initiatives) with blank cards. This script reads each
satellite .qmd's front matter and writes a `listing.yml` manifest per
directory; each `index.qmd` consumes its manifest via
`listing.contents: listing.yml`, bypassing the book's metadata pipeline.

Runs as a pre-render hook (see `_quarto.yml`). Idempotent — overwrites
manifests on every render.

Output paths in each manifest are relative to the index.qmd:
    updates/listing.yml:      "WU-<date>-week-NN/index.html"
    initiatives/listing.yml:  "<initiative>/README.html"

Initiative + epic READMEs are rendered as standalone satellite pages by
`scripts/render/render_satellites.py`; Quarto `listing:` front matter
is a no-op in that context (it only populates inside a project/book
render), so for those pages we additionally emit `_listing.md`
markdown-table partials that the satellite pages include verbatim.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import yaml

from _lib import ROOT, read_front_matter, write_text_if_changed

# Fields beyond title/date/description/categories that we preserve when
# present in the source front matter. Quarto listings use these for the
# `fields:` display option on the index pages.
EXTRA_FIELDS = [
    "experiment-id", "problem", "status",
    "attendees", "related-tasks", "related-experiments",
    "author", "owner",
    # Initiative / epic listing fields
    "initiative-id", "gantt-section", "epic-id", "gantt-id",
]


def build_item(qmd: Path, href: str) -> dict | None:
    fm = read_front_matter(qmd)
    if not fm.get("title"):
        return None
    item: dict = {"path": href, "title": fm["title"]}
    if "date" in fm:
        item["date"] = str(fm["date"])
    if "description" in fm:
        item["description"] = fm["description"]
    if "categories" in fm:
        item["categories"] = fm["categories"]
    for key in EXTRA_FIELDS:
        if key in fm:
            item[key] = fm[key]
    return item


def write_manifest(items: list[dict], out_file: Path) -> None:
    # write-only-if-changed: an idempotent rewrite must not bump the
    # mtime, or the satellite render cache invalidates on every run.
    text = yaml.safe_dump(items, sort_keys=False, allow_unicode=True)
    if write_text_if_changed(out_file, text):
        print(f"Wrote {len(items)} items -> {out_file.relative_to(ROOT)}")
    else:
        print(f"Unchanged -> {out_file.relative_to(ROOT)}")


def build_flat_manifest(source_dir: Path, pattern: str,
                        href_from: Callable[[Path], str],
                        out_file: Path) -> None:
    items: list[dict] = []
    for qmd in sorted(source_dir.glob(pattern)):
        if qmd.name.startswith("_"):
            continue
        item = build_item(qmd, href_from(qmd))
        if item is not None:
            items.append(item)
    write_manifest(items, out_file)


def _md_link(title: str, href: str) -> str:
    title = str(title).replace("|", "\\|")
    return f"[{title}]({href})"


def write_md_table(out_file: Path, headers: list[str],
                   rows: list[list[str]], empty_note: str) -> None:
    """Write a generated markdown table partial (consumed via `{{< include >}}`).

    Static markdown renders in any context — unlike Quarto `listing:` front
    matter, which only populates inside a website/book project and would be a
    no-op in the standalone satellite render (see scripts/render_satellites.py).
    """
    if rows:
        head = "| " + " | ".join(headers) + " |"
        sep = "| " + " | ".join("---" for _ in headers) + " |"
        body = "\n".join("| " + " | ".join(str(c) for c in r) + " |"
                         for r in rows)
        text = f"{head}\n{sep}\n{body}\n"
    else:
        text = f"{empty_note}\n"
    if write_text_if_changed(out_file, text):
        print(f"Wrote {len(rows)} rows -> {out_file.relative_to(ROOT)}")
    else:
        print(f"Unchanged -> {out_file.relative_to(ROOT)}")


def _collect_item_rows(items_dir: Path, kind: str) -> list[list[str]]:
    """Listing rows for items of a given kind under an epic.

    Returns ``[link, status, third]`` rows where ``third`` is the priority
    for issues and the date (experiment date or opened-date) for
    experiments and features.
    """
    rows: list[list[str]] = []
    for readme in sorted(items_dir.glob("*/README.qmd")):
        fm = read_front_matter(readme)
        if not fm.get("title"):
            continue
        item_id = fm.get("item-id") or fm.get("experiment-id") or ""
        label = f"{item_id} — {fm['title']}".strip(" —")
        href = f"{kind}/{readme.parent.name}/README.html"
        link = _md_link(label, href)
        if kind == "issues":
            third = fm.get("priority", "")
        else:
            third = str(fm.get("date") or fm.get("opened-date") or "")
        rows.append([link, fm.get("status", ""), third,
                     fm.get("owner", "")])
    return rows


# Per-kind section schema used by both the epic `_listing.md` partial and
# the per-page section headings. Order here = render order on the epic page.
EPIC_SECTIONS: tuple[tuple[str, str, list[str]], ...] = (
    ("experiments", "Experiments", ["Experiment", "Status", "Date", "Owner"]),
    ("features",    "Features",    ["Feature",    "Status", "Opened", "Owner"]),
    ("issues",      "Issues",      ["Issue",      "Status", "Priority", "Owner"]),
)


def write_epic_items_partial(epic: Path) -> None:
    """Write `_listing.md` for one epic with a section per item kind.

    Sections are emitted only when they contain at least one item; an
    entirely-empty epic falls back to a single placeholder line so the
    epic page doesn't crash on the include.
    """
    lines: list[str] = []
    for kind, heading, columns in EPIC_SECTIONS:
        items_dir = epic / kind
        if not items_dir.exists():
            continue
        rows = _collect_item_rows(items_dir, kind)
        if not rows:
            continue
        lines.append(f"## {heading}")
        lines.append("")
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join("---" for _ in columns) + " |")
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    if not lines:
        lines = ["_No items in this epic yet._", ""]
    out_file = epic / "_listing.md"
    if write_text_if_changed(out_file, "\n".join(lines)):
        print(f"Wrote epic partial -> {out_file.relative_to(ROOT)}")
    else:
        print(f"Unchanged epic partial -> {out_file.relative_to(ROOT)}")


def build_initiatives_partials() -> None:
    """Emit `_listing.md` markdown-table partials for the Initiative tree.

    Three levels, each included by the README at that level:
      initiatives/_listing.md                -> initiatives/index.qmd (initiatives)
      initiatives/<I>/_listing.md            -> initiatives/<I>/README.qmd (epics)
      initiatives/<I>/epics/<E>/_listing.md  -> .../epics/<E>/README.qmd (experiments)

    Hrefs are relative to the consuming page so the standalone satellite HTML
    resolves in _site/.
    """
    base = ROOT / "initiatives"
    if not base.exists():
        return

    # initiatives/index.qmd is a book appendix, so it uses a Quarto `listing:`
    # (resolved at render time) rather than an include (expanded at config time,
    # before this hook runs). Generate its yaml manifest here.
    initiative_items: list[dict] = []
    initiative_rows: list[list[str]] = []
    for initiative in sorted(p for p in base.iterdir() if p.is_dir()):
        if initiative.name.startswith("_"):
            continue  # skip _template/ (and any future underscore-prefixed scaffolding)
        ifm = read_front_matter(initiative / "README.qmd")
        if ifm.get("title"):
            item = build_item(initiative / "README.qmd",
                              f"{initiative.name}/README.html")
            if item is not None:
                initiative_items.append(item)
            initiative_rows.append([
                _md_link(ifm["title"], f"{initiative.name}/README.html"),
                ifm.get("gantt-section", ""),
                ifm.get("status", ""),
            ])

        epics_dir = initiative / "epics"
        if not epics_dir.exists():
            continue

        epic_rows: list[list[str]] = []
        for epic in sorted(p for p in epics_dir.iterdir() if p.is_dir()):
            efm = read_front_matter(epic / "README.qmd")
            if efm.get("title"):
                epic_rows.append([
                    _md_link(efm["title"], f"epics/{epic.name}/README.html"),
                    str(efm.get("gantt-id", "")),
                    efm.get("status", ""),
                    efm.get("owner", ""),
                ])

            write_epic_items_partial(epic)

        write_md_table(initiative / "_listing.md",
                       ["Epic", "Gantt", "Status", "Owner"], epic_rows,
                       "_No epics yet._")

    write_md_table(base / "_listing.md",
                   ["Initiative", "Section", "Status"], initiative_rows,
                   "_No initiatives yet._")
    write_manifest(initiative_items, base / "listing.yml")


def main() -> int:
    build_flat_manifest(
        ROOT / "updates", "WU-*/index.qmd",
        lambda p: f"{p.parent.name}/index.html",
        ROOT / "updates" / "listing.yml",
    )
    build_initiatives_partials()
    return 0


if __name__ == "__main__":
    sys.exit(main())
