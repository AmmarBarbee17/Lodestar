"""Audit and (optionally) migrate front matter to the canonical shape.

Three audit passes, all gated the same way (pre-commit hook when
``initiatives/`` is staged; first step of ``publish.py``):

**Items** — every README under
``initiatives/<I>/epics/<E>/{experiments,features,issues}/<item>/``:

- ``item-id`` matches the directory slug stem (e.g. dir
  ``A4-EX-001-rough-primer-only`` -> ``item-id: A4-EX-001``).
- ``type`` matches the kind directory (``experiment`` / ``feature`` / ``issue``).
- ``epic-id`` matches the parent epic dir's slug.
- ``initiative`` matches the grand-parent initiative dir's slug.
- ``gantt-id`` matches the epic's own ``gantt-id``.
- ``status`` ∈ {``open``, ``in-progress``, ``blocked``, ``done``}.
- ``owner`` present (advisory ownership — see docs/workflow-item-lifecycle.md).

**Epics + initiatives** — hub READMEs:

- ``epic-id`` == epic dir name (gantt-prefixed), ``gantt-id`` == dir
  prefix, ``initiative`` == parent initiative slug, canonical
  ``status``, ``owner`` present.
- ``initiative-id`` == initiative dir name, ``owner`` present.

**SOPs** — ``chapters/03-operation/sops/SOP-*.qmd``:

- ``owner`` present; if a ``revisions:`` block exists (rendered by the
  ``{{< revisions >}}`` shortcode), every entry has ``rev`` / ``date``
  (ISO) / ``description``.

Run:
    python scripts/render/audit_items.py                  # report, exit 1 on drift
    python scripts/render/audit_items.py --fix            # rewrite in place
    python scripts/render/audit_items.py --fix --owner X  # fill owner with X

Body content is never touched; only the front-matter YAML is rewritten.
Fields beyond the canonical contract are preserved in source order.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from _lib import DEFAULT_OWNER, ROOT, emit_front_matter, parse_front_matter

INITIATIVES = ROOT / "initiatives"
SOPS_DIR = ROOT / "chapters" / "03-operation" / "sops"

KIND_TO_TYPE = {"experiments": "experiment", "features": "feature", "issues": "issue"}
VALID_STATUSES = {"open", "in-progress", "blocked", "done"}
STATUS_MIGRATIONS = {
    "complete": "done", "completed": "done", "closed": "done",
    "planned": "open", "planning": "open",
    # "critical" was schedule emphasis, not a workflow state — the crit
    # flag lives on the Gantt bar (index.qmd mermaid block).
    "critical": "open",
}

# Canonical field order on the rendered front matter. Anything not listed
# here is appended at the end in source-of-truth order.
FIELD_ORDER = [
    "title",
    "item-id",
    "type",
    "epic-id",
    "initiative",
    "gantt-id",
    "status",
    "owner",
    "priority",          # issues only — leave absent on others
    "date",              # experiments
    "opened-date",       # features / issues
    "closed-date",       # features / issues
    "description",
    "related-items",
    "categories",
    "problem",           # legacy on experiments — keep if present
]

EPIC_FIELD_ORDER = [
    "title", "epic-id", "initiative", "gantt-id", "gantt-dates",
    "status", "owner", "customer", "need", "benefit",
    "thesis-chapters", "related-epics",
]

INITIATIVE_FIELD_ORDER = [
    "title", "initiative-id", "gantt-section", "status", "owner",
    "description",
]

SOP_FIELD_ORDER = ["title", "owner", "revisions"]

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def epic_gantt_id(epic_dir: Path) -> str | None:
    fm, _ = parse_front_matter((epic_dir / "README.qmd").read_text(encoding="utf-8"))
    if not fm:
        return None
    val = fm.get("gantt-id")
    return str(val) if val is not None else None


def expected_item_id(item_dir: Path) -> str | None:
    """Strip the descriptive slug off the dir to recover the bare item-id.

    Convention: dir = ``<gantt-id>-<KIND>-<NNN>-<slug>``, item-id =
    ``<gantt-id>-<KIND>-<NNN>``.
    """
    parts = item_dir.name.split("-")
    if len(parts) < 3:
        return None
    return "-".join(parts[:3])


def _migrate_status(new_fm: dict, drift: list[str]) -> None:
    raw_status = new_fm.get("status")
    if isinstance(raw_status, str):
        if raw_status in STATUS_MIGRATIONS:
            mapped = STATUS_MIGRATIONS[raw_status]
            drift.append(f"  status: {raw_status!r} -> {mapped!r}")
            new_fm["status"] = mapped
        elif raw_status not in VALID_STATUSES:
            drift.append(f"  status: {raw_status!r} not in canonical set")


def _ensure_owner(new_fm: dict, drift: list[str], owner: str) -> None:
    if not new_fm.get("owner"):
        drift.append(f"  owner: missing -> {owner!r}")
        new_fm["owner"] = owner


def _finish(readme: Path, drift: list[str], new_fm: dict, body: str,
            fix: bool, field_order: list[str]) -> list[str]:
    if not drift:
        return []
    header = [f"{readme.relative_to(ROOT)}:"]
    if fix:
        readme.write_text(emit_front_matter(new_fm, field_order) + body,
                          encoding="utf-8")
        header[0] += " FIXED"
    return header + drift


def audit_item(item_dir: Path, fix: bool, owner: str = DEFAULT_OWNER) -> list[str]:
    """Audit one item README; return list of drift messages.

    With ``fix=True``, rewrites the README in place. Body is never touched.
    """
    readme = item_dir / "README.qmd"
    if not readme.exists():
        return []
    text = readme.read_text(encoding="utf-8")
    fm, body = parse_front_matter(text)
    if fm is None:
        return [f"{readme}: no parseable front matter"]

    drift: list[str] = []
    new_fm = dict(fm)

    # Inferred canonical values
    kind = item_dir.parent.name  # experiments | features | issues
    expected_type = KIND_TO_TYPE.get(kind)
    expected_iid = expected_item_id(item_dir)
    epic_dir = item_dir.parent.parent
    expected_eid = epic_dir.name
    initiative_dir = epic_dir.parent.parent  # epics/<E>/.. -> initiatives/<I>
    expected_init = initiative_dir.name
    expected_gid = epic_gantt_id(epic_dir)

    def ensure(field: str, expected: Any, label: str) -> None:
        actual = new_fm.get(field)
        if actual == expected:
            return
        drift.append(f"  {label}: have={actual!r} want={expected!r}")
        new_fm[field] = expected

    # Legacy `experiment-id` -> `item-id` migration
    if "experiment-id" in new_fm and "item-id" not in new_fm:
        drift.append("  rename experiment-id -> item-id")
        new_fm["item-id"] = new_fm.pop("experiment-id")
    elif "experiment-id" in new_fm and "item-id" in new_fm:
        # Both present — drop the legacy field
        drift.append("  drop duplicate experiment-id (item-id present)")
        new_fm.pop("experiment-id")

    _migrate_status(new_fm, drift)

    # Canonical fields
    if expected_iid:
        ensure("item-id", expected_iid, "item-id")
    if expected_type:
        ensure("type", expected_type, "type")
    ensure("epic-id", expected_eid, "epic-id")
    ensure("initiative", expected_init, "initiative")
    if expected_gid:
        ensure("gantt-id", expected_gid, "gantt-id")

    _ensure_owner(new_fm, drift, owner)

    # related-items default to [] if missing (so front matter has the field
    # to fill in later without re-editing)
    if "related-items" not in new_fm:
        drift.append("  add related-items: []")
        new_fm["related-items"] = []

    return _finish(readme, drift, new_fm, body, fix, FIELD_ORDER)


def audit_epic(epic_dir: Path, fix: bool, owner: str = DEFAULT_OWNER) -> list[str]:
    readme = epic_dir / "README.qmd"
    if not readme.exists():
        return []
    fm, body = parse_front_matter(readme.read_text(encoding="utf-8"))
    if fm is None:
        return [f"{readme}: no parseable front matter"]

    drift: list[str] = []
    new_fm = dict(fm)

    expected_eid = epic_dir.name                       # gantt-prefixed slug
    expected_gid = epic_dir.name.split("-")[0]         # A5 from A5-…
    expected_init = epic_dir.parent.parent.name        # initiatives/<I>/epics

    def ensure(field: str, expected: Any) -> None:
        actual = new_fm.get(field)
        if actual == expected:
            return
        drift.append(f"  {field}: have={actual!r} want={expected!r}")
        new_fm[field] = expected

    ensure("epic-id", expected_eid)
    ensure("gantt-id", expected_gid)
    ensure("initiative", expected_init)
    _migrate_status(new_fm, drift)
    _ensure_owner(new_fm, drift, owner)

    return _finish(readme, drift, new_fm, body, fix, EPIC_FIELD_ORDER)


def audit_initiative(init_dir: Path, fix: bool,
                     owner: str = DEFAULT_OWNER) -> list[str]:
    readme = init_dir / "README.qmd"
    if not readme.exists():
        return []
    fm, body = parse_front_matter(readme.read_text(encoding="utf-8"))
    if fm is None:
        return [f"{readme}: no parseable front matter"]

    drift: list[str] = []
    new_fm = dict(fm)
    expected_id = init_dir.name
    if new_fm.get("initiative-id") != expected_id:
        drift.append(f"  initiative-id: have={new_fm.get('initiative-id')!r} "
                     f"want={expected_id!r}")
        new_fm["initiative-id"] = expected_id
    _migrate_status(new_fm, drift)
    _ensure_owner(new_fm, drift, owner)

    return _finish(readme, drift, new_fm, body, fix, INITIATIVE_FIELD_ORDER)


def audit_sop(sop: Path, fix: bool, owner: str = DEFAULT_OWNER) -> list[str]:
    fm, body = parse_front_matter(sop.read_text(encoding="utf-8"))
    if fm is None:
        return [f"{sop}: no parseable front matter"]

    drift: list[str] = []
    new_fm = dict(fm)
    _ensure_owner(new_fm, drift, owner)

    revisions = new_fm.get("revisions")
    if revisions is not None:
        if not isinstance(revisions, list):
            drift.append("  revisions: must be a list of entries")
        else:
            for i, entry in enumerate(revisions):
                if not isinstance(entry, dict):
                    drift.append(f"  revisions[{i}]: not a mapping")
                    continue
                for required in ("rev", "date", "description"):
                    if not entry.get(required):
                        drift.append(f"  revisions[{i}]: missing {required!r}")
                d = entry.get("date")
                if d and not isinstance(d, date) \
                        and not ISO_DATE_RE.match(str(d)):
                    drift.append(f"  revisions[{i}]: date {d!r} not ISO "
                                 "(YYYY-MM-DD)")

    return _finish(sop, drift, new_fm, body, fix, SOP_FIELD_ORDER)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Audit item/epic/initiative/SOP front matter.")
    ap.add_argument("--fix", action="store_true",
                    help="rewrite drifted front matter in place")
    ap.add_argument("--owner", default=DEFAULT_OWNER,
                    help=f"owner used to fill missing owner fields "
                         f"(default: {DEFAULT_OWNER!r})")
    args = ap.parse_args(argv)
    fix, owner = args.fix, args.owner

    if not INITIATIVES.exists():
        print(f"{INITIATIVES} not found")
        return 1
    all_drift: list[str] = []
    fixed_count = 0

    def collect(msgs: list[str]) -> None:
        nonlocal fixed_count
        if msgs:
            all_drift.extend(msgs)
            if fix:
                fixed_count += 1

    for initiative in sorted(p for p in INITIATIVES.iterdir()
                             if p.is_dir() and not p.name.startswith("_")):
        collect(audit_initiative(initiative, fix=fix, owner=owner))
        epics_dir = initiative / "epics"
        if not epics_dir.exists():
            continue
        for epic in sorted(p for p in epics_dir.iterdir() if p.is_dir()):
            collect(audit_epic(epic, fix=fix, owner=owner))
            for kind in ("experiments", "features", "issues"):
                k = epic / kind
                if not k.exists():
                    continue
                for item in sorted(p for p in k.iterdir() if p.is_dir()):
                    collect(audit_item(item, fix=fix, owner=owner))

    if SOPS_DIR.exists():
        for sop in sorted(SOPS_DIR.glob("SOP-*.qmd")):
            collect(audit_sop(sop, fix=fix, owner=owner))

    if not all_drift:
        print("audit: all items canonical")
        return 0
    print("\n".join(all_drift))
    if fix:
        print(f"\naudit: rewrote {fixed_count} file(s)")
        return 0
    print(f"\naudit: {sum(1 for m in all_drift if m.endswith(':') or m.endswith(': FIXED'))} file(s) drift")
    print("Run with --fix to rewrite front matter in place.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
