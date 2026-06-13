"""Scaffold a new experiment / feature / issue / epic / weekly update.

One command creates a correctly-structured unit of work — directory,
README from the matching template in ``initiatives/_template/``, next
free ID, canonical front matter — so neither humans nor agents ever
hand-roll structure. ``audit_items.py`` validates; this prevents.

Usage (via ``thesis.ps1 new …`` or directly):

    new_item.py experiment --epic A5 --slug head-cad-revalidation \
        --title "Does the revised head CAD change collision results?"
    new_item.py feature    --epic A6 --slug opcua-bridge --title "…"
    new_item.py issue      --epic A9 --slug network-drop --title "…" \
        [--priority high]
    new_item.py epic --initiative research-problems --gantt-id A10 \
        --slug thermal-mapping --title "Thermal Mapping" \
        [--dates 2026-07-01 2026-08-01]
    new_item.py wu [--date 2026-06-18] [--week 23] [--title "topic"]

Conventions enforced (see docs/workflow-item-lifecycle.md):

- Item IDs are epic-scoped: ``<gantt-id>-<EX|FE|IS>-<NNN>`` with NNN =
  max existing in that epic+kind, plus one, zero-padded to 3.
- WU week numbers are SEMESTER-relative, not ISO — inferred from the
  existing ``updates/WU-*-week-NN`` dirs (+1 per elapsed 7 days since
  the latest), printed for confirmation; ``--week`` overrides.
- After scaffolding an item, ``audit_items.audit_item`` must report
  zero drift — anything else is a scaffolder bug and fails loudly.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import audit_items
from _lib import (
    DEFAULT_OWNER,
    ROOT,
    emit_front_matter,
    parse_front_matter,
)

INITIATIVES = ROOT / "initiatives"
TEMPLATES = INITIATIVES / "_template"
UPDATES = ROOT / "updates"

KIND_CODE = {"experiment": "EX", "feature": "FE", "issue": "IS"}
KIND_DIR = {"experiment": "experiments", "feature": "features",
            "issue": "issues"}
# Experiments carry evidence subdirs; features/issues keep a media/ dir
# (decision 17: items own all media).
KIND_SUBDIRS = {"experiment": ("data", "images", "videos"),
                "feature": ("media",), "issue": ("media",)}

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def die(msg: str) -> "NoReturn":  # noqa: F821
    print(f"new_item: {msg}", file=sys.stderr)
    raise SystemExit(1)


def check_slug(slug: str) -> str:
    if not SLUG_RE.match(slug):
        die(f"slug {slug!r} must be kebab-case (lowercase, digits, dashes)")
    return slug


def parse_iso(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        die(f"date {value!r} is not ISO (YYYY-MM-DD)")


def find_epic_dir(gantt_id: str) -> Path:
    matches = sorted(INITIATIVES.glob(f"*/epics/{gantt_id}-*"))
    matches = [m for m in matches if m.is_dir()]
    if not matches:
        die(f"no epic directory matches {gantt_id}-* under initiatives/*/epics/")
    if len(matches) > 1:
        die(f"gantt-id {gantt_id} is ambiguous: "
            + ", ".join(str(m.relative_to(ROOT)) for m in matches))
    return matches[0]


def next_item_number(epic_dir: Path, gantt_id: str, code: str) -> int:
    rx = re.compile(rf"^{re.escape(gantt_id)}-{code}-(\d+)")
    highest = 0
    for kind_dir in (epic_dir / d for d in KIND_DIR.values()):
        if not kind_dir.exists():
            continue
        for child in kind_dir.iterdir():
            m = rx.match(child.name)
            if m:
                highest = max(highest, int(m.group(1)))
    return highest + 1


def load_template(kind: str) -> tuple[dict, str]:
    template = TEMPLATES / kind / "README.qmd"
    if not template.exists():
        die(f"template missing: {template.relative_to(ROOT)}")
    fm, body = parse_front_matter(template.read_text(encoding="utf-8"))
    if fm is None:
        die(f"template has no front matter: {template.relative_to(ROOT)}")
    return fm, body


def create_item(args) -> int:
    kind = args.kind
    slug = check_slug(args.slug)
    epic_dir = find_epic_dir(args.epic)
    gantt_id = audit_items.epic_gantt_id(epic_dir) or args.epic
    code = KIND_CODE[kind]
    number = next_item_number(epic_dir, gantt_id, code)
    item_id = f"{gantt_id}-{code}-{number:03d}"
    item_dir = epic_dir / KIND_DIR[kind] / f"{item_id}-{slug}"
    if item_dir.exists():
        die(f"already exists: {item_dir.relative_to(ROOT)}")

    fm, body = load_template(kind)
    today = args.date or date.today().isoformat()
    fm["title"] = args.title
    fm["item-id"] = item_id
    fm["type"] = kind
    fm["epic-id"] = epic_dir.name
    fm["initiative"] = epic_dir.parent.parent.name
    fm["gantt-id"] = gantt_id
    fm["status"] = "open"
    fm["owner"] = args.owner
    if kind == "experiment":
        fm["date"] = today
    else:
        fm["opened-date"] = today
    if kind == "issue":
        fm["priority"] = args.priority
    # Swap the template's placeholder ID in body references
    # (images/TODO-EX-NNN-IMG-… etc.) for the real one.
    body = body.replace(f"TODO-{code}-NNN", item_id)

    item_dir.mkdir(parents=True)
    (item_dir / "README.qmd").write_text(
        emit_front_matter(fm, audit_items.FIELD_ORDER) + body,
        encoding="utf-8")
    for sub in KIND_SUBDIRS[kind]:
        (item_dir / sub).mkdir()
        (item_dir / sub / ".gitkeep").touch()

    # Round-trip guarantee: the scaffold must satisfy the audit contract.
    drift = audit_items.audit_item(item_dir, fix=False, owner=args.owner)
    if drift:
        print("\n".join(drift), file=sys.stderr)
        die("scaffolded item fails audit_items — this is a scaffolder bug")

    rel = item_dir.relative_to(ROOT)
    print(f"created {kind} {item_id} -> {rel}")
    print(f"  next: edit {rel}\\README.qmd, then `thesis.ps1 render-one "
          f"{item_id}` to preview")
    return 0


def create_epic(args) -> int:
    slug = check_slug(args.slug)
    gantt_id = args.gantt_id
    init_dir = INITIATIVES / args.initiative
    if not init_dir.is_dir():
        options = ", ".join(p.name for p in sorted(INITIATIVES.iterdir())
                            if p.is_dir() and not p.name.startswith("_"))
        die(f"initiative {args.initiative!r} not found (have: {options})")
    clash = [p for p in INITIATIVES.glob(f"*/epics/{gantt_id}-*")
             if p.is_dir()]
    if clash:
        die(f"gantt-id {gantt_id} already used by "
            f"{clash[0].relative_to(ROOT)}")

    epic_dir = init_dir / "epics" / f"{gantt_id}-{slug}"
    fm, body = load_template("epic")
    fm["title"] = args.title
    fm["epic-id"] = epic_dir.name
    fm["initiative"] = init_dir.name
    fm["gantt-id"] = gantt_id
    if args.dates:
        fm["gantt-dates"] = [parse_iso(args.dates[0]),
                             parse_iso(args.dates[1])]
    fm["status"] = "open"
    fm["owner"] = args.owner

    epic_dir.mkdir(parents=True)
    (epic_dir / "README.qmd").write_text(
        emit_front_matter(fm, audit_items.EPIC_FIELD_ORDER) + body,
        encoding="utf-8")

    drift = audit_items.audit_epic(epic_dir, fix=False, owner=args.owner)
    if drift:
        print("\n".join(drift), file=sys.stderr)
        die("scaffolded epic fails audit_items — this is a scaffolder bug")

    rel = epic_dir.relative_to(ROOT)
    print(f"created epic {gantt_id} -> {rel}")
    print(f"  next: 1) fill customer/need/benefit in {rel}\\README.qmd")
    print("        2) add a matching bar to the Mermaid gantt in index.qmd")
    return 0


WU_DIR_RE = re.compile(r"^WU-(\d{4}-\d{2}-\d{2})-week-(\d+)$")


def infer_week(wu_date: date) -> tuple[int, str]:
    latest: tuple[date, int] | None = None
    for d in UPDATES.glob("WU-*"):
        m = WU_DIR_RE.match(d.name)
        if not m:
            continue
        d_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        if latest is None or d_date > latest[0]:
            latest = (d_date, int(m.group(2)))
    if latest is None:
        return 1, "no existing WU dirs — defaulting to week 1"
    elapsed_weeks = max(1, round((wu_date - latest[0]).days / 7))
    nn = latest[1] + elapsed_weeks
    return nn, (f"inferred from {latest[0]} (week {latest[1]}) + "
                f"{elapsed_weeks} week(s) — week numbers are "
                f"semester-relative, use --week to override")


def create_wu(args) -> int:
    wu_date = datetime.strptime(parse_iso(args.date), "%Y-%m-%d").date() \
        if args.date else date.today()
    if args.week is not None:
        week = args.week
    else:
        week, how = infer_week(wu_date)
        print(f"week {week}: {how}")
    wu_dir = UPDATES / f"WU-{wu_date.isoformat()}-week-{week:02d}"
    if wu_dir.exists():
        die(f"already exists: {wu_dir.relative_to(ROOT)}")
    template = UPDATES / "_template"
    if not template.exists():
        die(f"template missing: {template.relative_to(ROOT)}")
    shutil.copytree(template, wu_dir)

    # Patch front-matter lines textually (NOT a YAML round-trip — the
    # template's format block carries comments worth keeping).
    qmd = wu_dir / "index.qmd"
    text = qmd.read_text(encoding="utf-8")
    title = f"Week {week} — {args.title}" if args.title \
        else f"Week {week} — TODO topic"
    text = text.replace('title: "Week TODO — short topic"',
                        f'title: "{title}"')
    text = text.replace("date: YYYY-MM-DD", f"date: {wu_date.isoformat()}")
    text = text.replace("owner: TODO-owner", f"owner: {args.owner}")
    qmd.write_text(text, encoding="utf-8")

    rel = wu_dir.relative_to(ROOT)
    print(f"created weekly update -> {rel}")
    print(f"  next: 1) fill the deck in {rel}\\index.qmd")
    print("        2) run `thesis.ps1 gantt` to drop this week's frozen "
          "schedule snapshot")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Scaffold experiments / features / issues / epics / "
                    "weekly updates with canonical structure.")
    sub = ap.add_subparsers(dest="kind", required=True)

    for kind in ("experiment", "feature", "issue"):
        p = sub.add_parser(kind, help=f"new {kind} under an epic")
        p.add_argument("--epic", required=True, metavar="GANTT_ID",
                       help="parent epic's gantt-id (e.g. A5)")
        p.add_argument("--slug", required=True,
                       help="kebab-case descriptive slug")
        p.add_argument("--title", required=True)
        p.add_argument("--owner", default=DEFAULT_OWNER)
        p.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                       help="trial/opened date (default: today)")
        if kind == "issue":
            p.add_argument("--priority", default="medium",
                           choices=["low", "medium", "high", "critical"])
        p.set_defaults(func=create_item)

    p = sub.add_parser("epic", help="new epic under an initiative")
    p.add_argument("--initiative", required=True,
                   help="initiative slug (e.g. research-problems)")
    p.add_argument("--gantt-id", required=True, dest="gantt_id",
                   help="new unique gantt-id (e.g. A10)")
    p.add_argument("--slug", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p.add_argument("--dates", nargs=2, metavar=("START", "END"),
                   default=None, help="gantt-dates (ISO)")
    p.set_defaults(func=create_epic)

    p = sub.add_parser("wu", help="new weekly-update deck")
    p.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                   help="update date (default: today)")
    p.add_argument("--week", type=int, default=None,
                   help="semester week number (default: inferred)")
    p.add_argument("--title", default=None, help="topic for the WU title")
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p.set_defaults(func=create_wu)

    args = ap.parse_args(argv)
    if getattr(args, "date", None):
        args.date = parse_iso(args.date)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
