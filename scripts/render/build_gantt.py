"""Render frozen-in-time PNG snapshots of the top-level thesis Gantt.

Parses the Mermaid ``gantt`` block in ``index.qmd`` (the single source
of truth for the schedule) and emits one matplotlib PNG per weekly
update:

``updates/WU-YYYY-MM-DD-week-NN/media/gantt.png`` — frozen snapshot
with the red "today" marker on that WU's date rather than the actual
current date. Committed to the repo so the WU always shows the
schedule as it looked the week it was written.

The freeze is automatic: a per-WU PNG is regenerated only if (a) it
doesn't exist yet, (b) the WU's date is today or later (draft window),
or (c) ``--force`` is passed. Once a WU's date is in the past and its
PNG is on disk, ``build_gantt.py`` leaves it alone on subsequent runs.

Handles the subset of Mermaid gantt syntax actually used in the thesis:

- ``section <name>`` — groups rows under a horizontal band.
- ``<label> :<tags>, <id>, <start>, <end-or-duration>`` — a task.
  Tags include ``done`` / ``crit`` / ``milestone`` (comma-separated,
  optional).
- End field is either ``YYYY-MM-DD``, ``Nd`` (duration days), or
  ``after <id>`` (start = referenced task's end).

Skips lines that don't match (title/dateFormat/axisFormat/etc. are
parsed separately for metadata).
"""

from __future__ import annotations

import io
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from _lib import ROOT, read_front_matter, write_bytes_if_changed

SOURCE = ROOT / "index.qmd"
UPDATES_DIR = ROOT / "updates"

STATUS_COLORS = {
    "done": {"fill": "#c9c9c9", "edge": "#8a8a8a", "text": "#4a4a4a"},
    "active": {"fill": "#81b9d6", "edge": "#4789a5", "text": "#1a1a1a"},
    "crit": {"fill": "#ff9e9e", "edge": "#c94b4b", "text": "#1a1a1a"},
    "milestone": {"fill": "#fff9c2", "edge": "#7a6b2f", "text": "#1a1a1a"},
    "pending": {"fill": "#bfdffa", "edge": "#5193c4", "text": "#1a1a1a"},
}
SECTION_BAND_COLOR = "#f3f4f6"

GANTT_BLOCK_RE = re.compile(r"```\{mermaid\}\s*\ngantt\s*\n(.*?)\n```", re.DOTALL)


def parse_block(text: str) -> tuple[str, list[dict]]:
    """Return (title, rows). Rows are either section markers or tasks."""
    title = "Thesis schedule"
    rows: list[dict] = []
    current_section: str | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("title "):
            title = line[len("title "):].strip()
            continue
        if line.startswith("section "):
            current_section = line[len("section "):].strip()
            rows.append({"type": "section", "name": current_section})
            continue
        if line.startswith(("dateFormat", "axisFormat", "tickInterval")):
            continue
        if ":" not in line:
            continue
        label, _, rest = line.partition(":")
        label = label.strip()
        parts = [p.strip() for p in rest.split(",")]
        # tags come before the id. id is the first bareword token that
        # looks like an identifier and is followed by a date/duration.
        tags: list[str] = []
        i = 0
        while i < len(parts):
            token = parts[i]
            if re.fullmatch(r"(done|crit|active|milestone)", token):
                tags.append(token)
                i += 1
            else:
                break
        if len(parts) - i < 2:
            continue
        task_id = parts[i]
        start_token = parts[i + 1]
        end_token = parts[i + 2] if len(parts) - i >= 3 else None
        rows.append(
            {
                "type": "task",
                "label": label,
                "id": task_id,
                "tags": tags,
                "start": start_token,
                "end": end_token,
                "section": current_section,
            }
        )
    return title, rows


def resolve_dates(rows: list[dict]) -> list[dict]:
    """Convert start/end tokens into datetime.date objects."""
    by_id: dict[str, dict] = {}
    resolved: list[dict] = []
    for row in rows:
        if row["type"] != "task":
            resolved.append(row)
            continue
        start_token = row["start"]
        end_token = row["end"]
        # start
        if start_token.startswith("after "):
            ref_id = start_token[len("after "):].strip()
            ref = by_id.get(ref_id)
            start = ref["end"] if ref else None
        else:
            start = datetime.strptime(start_token, "%Y-%m-%d").date()
        # end
        if end_token is None:
            end = start
        elif re.fullmatch(r"\d+d", end_token):
            days = int(end_token[:-1])
            end = (start + timedelta(days=days)) if start else None
        else:
            end = datetime.strptime(end_token, "%Y-%m-%d").date()
        row = {**row, "start": start, "end": end}
        by_id[row["id"]] = row
        resolved.append(row)
    return resolved


def pick_style(tags: list[str]) -> dict:
    for tag in ("milestone", "crit", "done", "active"):
        if tag in tags:
            return STATUS_COLORS[tag]
    return STATUS_COLORS["pending"]


def _layout(rows: list[dict]) -> tuple[list[dict], list[dict], list[tuple[int, int, int]]]:
    """Assign y-positions to section headers and tasks.

    Returns:
        header_rows: list of {"y", "name"} — each section gets its own
            row, rendered as a bold y-tick label.
        task_rows:   list of task dicts with a "y" key, same shape as
            the parsed rows otherwise.
        bands:       list of (y_start, y_end, section_index) spans used
            to draw alternating background bands behind section tasks.
    """
    header_rows: list[dict] = []
    task_rows: list[dict] = []
    bands: list[tuple[int, int, int]] = []
    current_start: int | None = None
    section_index = -1
    y = 0
    for row in rows:
        if row["type"] == "section":
            if current_start is not None:
                bands.append((current_start, y - 1, section_index))
            section_index += 1
            header_rows.append({"y": y, "name": row["name"]})
            current_start = y
            y += 1
            continue
        task_rows.append({**row, "y": y})
        y += 1
    if current_start is not None:
        bands.append((current_start, y - 1, section_index))
    return header_rows, task_rows, bands


def render(title: str, rows: list[dict], today: date, out_path: Path) -> bool:
    headers, tasks, bands = _layout(rows)
    total_rows = len(headers) + len(tasks)
    height = max(4.5, 0.32 * total_rows + 1.6)
    fig, ax = plt.subplots(figsize=(14.5, height))

    # Alternating section bands (odd-indexed sections get a tint).
    for y0, y1, section_idx in bands:
        if section_idx % 2 == 1:
            ax.axhspan(y0 + 0.5, y1 + 0.5, color=SECTION_BAND_COLOR,
                       zorder=0)

    # Bars and milestones.
    for t in tasks:
        start, end = t["start"], t["end"]
        if not start or not end:
            continue
        style = pick_style(t["tags"])
        if "milestone" in t["tags"]:
            ax.plot(start, t["y"], marker="D", markersize=10,
                    markerfacecolor=style["fill"],
                    markeredgecolor=style["edge"],
                    markeredgewidth=1.2, zorder=3)
        else:
            width_days = (end - start).days or 1
            ax.barh(t["y"], width_days, left=start, height=0.52,
                    color=style["fill"], edgecolor=style["edge"],
                    linewidth=0.9, zorder=2)

    # Combined y-tick layout: section header rows get the bold name,
    # task rows get the task label.
    y_positions = [h["y"] for h in headers] + [t["y"] for t in tasks]
    y_labels = [h["name"] for h in headers] + [t["label"] for t in tasks]
    order = sorted(range(len(y_positions)), key=lambda i: y_positions[i])
    y_positions = [y_positions[i] for i in order]
    y_labels = [y_labels[i] for i in order]
    header_ys = {h["y"] for h in headers}

    ax.set_yticks(y_positions)
    tick_labels = ax.set_yticklabels(
        y_labels, fontsize=9, color="#1f2a36",
    )
    for y, tl in zip(y_positions, tick_labels):
        if y in header_ys:
            tl.set_fontweight("bold")
            tl.set_fontsize(10)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.invert_yaxis()
    ax.set_ylim(total_rows - 0.5, -0.5)

    # Date axis on top, like Mermaid.
    ax.xaxis_date()
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.tick_params(axis="x", labelsize=9, length=0, pad=6, colors="#555")

    # Today line.
    ax.axvline(today, color="#c94b4b", linewidth=1.3, linestyle="-",
               alpha=0.85, zorder=4)
    ax.text(
        today, -0.6,
        f"  {today:%Y-%m-%d}",
        color="#c94b4b", fontsize=8.5, va="bottom", ha="left",
        fontweight="bold",
    )

    # Soft vertical grid per month; no horizontal grid.
    ax.grid(axis="x", linestyle="-", linewidth=0.5, color="#dde1e6",
            zorder=1)
    ax.set_axisbelow(True)

    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#cfd3d8")

    ax.set_title(title, fontsize=12.5, fontweight="bold",
                 color="#1f2a36", pad=14)

    handles = [
        mpatches.Patch(facecolor=STATUS_COLORS["pending"]["fill"],
                       edgecolor=STATUS_COLORS["pending"]["edge"],
                       linewidth=0.9, label="planned"),
        mpatches.Patch(facecolor=STATUS_COLORS["active"]["fill"],
                       edgecolor=STATUS_COLORS["active"]["edge"],
                       linewidth=0.9, label="active"),
        mpatches.Patch(facecolor=STATUS_COLORS["done"]["fill"],
                       edgecolor=STATUS_COLORS["done"]["edge"],
                       linewidth=0.9, label="done"),
        mpatches.Patch(facecolor=STATUS_COLORS["crit"]["fill"],
                       edgecolor=STATUS_COLORS["crit"]["edge"],
                       linewidth=0.9, label="critical"),
        mpatches.Patch(facecolor=STATUS_COLORS["milestone"]["fill"],
                       edgecolor=STATUS_COLORS["milestone"]["edge"],
                       linewidth=0.9, label="milestone"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8.5,
              framealpha=0.92, edgecolor="#cfd3d8", ncol=5,
              bbox_to_anchor=(1.0, -0.14))

    fig.tight_layout()
    # Render to memory and write-only-if-changed: an unchanged PNG must
    # not bump its mtime, or the satellite render cache treats every WU
    # deck as dirty on every run. Agg PNG output is deterministic for
    # fixed inputs; strip the Software field so matplotlib version
    # bumps alone don't churn the bytes.
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight",
                facecolor="white", metadata={"Software": None})
    plt.close(fig)
    return write_bytes_if_changed(out_path, buf.getvalue())


def read_wu_date(qmd: Path) -> date | None:
    fm = read_front_matter(qmd)
    value = fm.get("date")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def build_weekly_update_snapshots(
    title: str, rows: list[dict], force: bool
) -> None:
    if not UPDATES_DIR.exists():
        return
    today = date.today()
    # Each weekly update is now a directory (updates/WU-YYYY-MM-DD-week-NN/);
    # its frozen Gantt snapshot lives in that WU's own media/gantt.png.
    for qmd in sorted(UPDATES_DIR.glob("WU-*/index.qmd")):
        wu_date = read_wu_date(qmd)
        if wu_date is None:
            print(f"  skip {qmd.parent.name}: no valid date in front matter")
            continue
        media = qmd.parent / "media"
        media.mkdir(parents=True, exist_ok=True)
        out = media / "gantt.png"
        if out.exists() and wu_date < today and not force:
            print(f"  freeze {qmd.parent.name}/media/gantt.png (WU dated {wu_date}, already on disk)")
            continue
        existed = out.exists()
        if render(title, rows, wu_date, out):
            status = "force" if force and existed else "draft" if wu_date >= today else "first render"
            print(f"  wrote {out.relative_to(ROOT)} ({status}, today marker = {wu_date})")
        else:
            print(f"  unchanged {out.relative_to(ROOT)} (today marker = {wu_date})")


def main(argv: list[str]) -> int:
    force = "--force" in argv[1:]
    if not SOURCE.exists():
        print(f"{SOURCE} not found")
        return 1
    text = SOURCE.read_text(encoding="utf-8")
    match = GANTT_BLOCK_RE.search(text)
    if not match:
        print("No mermaid gantt block found in index.qmd")
        return 1
    title, rows = parse_block(match.group(1))
    rows = resolve_dates(rows)
    build_weekly_update_snapshots(title, rows, force=force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
