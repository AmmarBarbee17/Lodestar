# Quarto Thesis + PM Template

Run your thesis **and** the project management behind it from a single
plain-text git repo, rendered to one navigable website. The thesis
prose, the schedule, the weekly advisor decks, and the entire
experiment record live together, all linked, all searchable, all
portable — `quarto render` reproduces the whole artifact, and nothing
lives behind a login.

**New clone? Start with [GETTING-STARTED.md](GETTING-STARTED.md).**

---

## Why this exists

Running a thesis usually means juggling half a dozen tools that don't
talk to each other. Drafts in Word with inter-file links that break
when a folder moves. Meeting notes in OneNote. Weekly update slides in
PowerPoints you email once and forget. Experimental data — CSVs,
videos, prototype photos — scattered across the lab PC, your laptop,
and a cloud drive, with no consistent way to tie a given trial to the
research question it was meant to answer.

The pain is concrete. Every week you assemble an advisor update from
scratch — fishing through notes for last week's discussion, hunting for
the right screenshot, copying numbers from a spreadsheet that has since
drifted from the version cited in the draft. Notion and Confluence
solve some of this, but you can't hand a Notion-resident thesis to your
advisor — or to whoever continues the work after you — as a
self-contained artifact. It all depends on credentials, subscriptions,
and platforms that might not exist in five years.

This template is the answer: **one repo, plain text everywhere, one
rendered site** holding the thesis, the schedule, the meeting notes,
the update decks, and the experiment record — all linked, all
searchable, all portable. Anyone with the repo reproduces the entire
artifact with `quarto render`. Nothing depends on a vendor. The deepest
payoff is **handoff**: a future collaborator (or a future you) clones
one repo and inherits the full history of decisions, evidence, and
writing in one place.

## The model in one minute

Two halves share the repo:

- **The thesis** — chapters in `chapters/`, the only content bound into
  the book (HTML + PDF).
- **The project-management surface** — a tree of work in
  `initiatives/`, surfaced as appendix pages on the same site:
  - an **initiative** is a top-level track (one Gantt section),
  - an **epic** is a unit of work inside it (one Gantt bar),
  - an **item** is the atomic thing — an **experiment** (a question you
    answer), a **feature** (a thing you build), or an **issue** (a
    problem you solve) — living under its epic, owning its own evidence.

The thesis never mentions a meeting or a weekly update; it references
only the *content* — an image, a dataset, a result — that an item
produced. The PM surface carries the process; the book stays clean.

## How the value shows up

### 1. The weekly advisor cycle

Updates are revealjs decks that embed a **frozen-in-time snapshot of the
Gantt as of the meeting date** — your advisor sees what you were
planning *that* week, not what you're planning today. The snapshot is
generated automatically (`build_gantt.py`) and freezes once the week
passes, so the deck is a faithful record forever. Each deck references
the experiments and notes it draws from by relative path, so a year
later you can still trace what evidence supported what claim.

```powershell
.\thesis.ps1 new wu --title "tension calibration results"
```

### 2. The lab inbox → filed, attributable evidence

Raw output from each work session — videos, CSVs, prototype photos —
lands in one inbox folder (`$THESIS_INBOX`). Once a week you **sort**:

```powershell
.\thesis.ps1 disperse              # stage the week's dump into _inbox/<week>/
# then the /disperse skill proposes where each file goes — you approve
```

Every piece of evidence is filed into the **experiment, issue, or
feature it belongs to**, under the epic that justifies the work — into
an existing item, or a freshly scaffolded one (`thesis.ps1 new
experiment …`, IDs allocated for you). Oversized videos that GitHub
Pages won't serve are uploaded to **Google Drive and embedded by
iframe** (`scripts/tools/google-drive-embed/`), so the repo holds the
*link*, not the bytes. Every item page also ends with an
auto-generated **file-tree** of everything it owns — including
non-renderable binaries (CAD, `.blend`, raw scans) — as clickable
download links, so evidence stays reachable even when it can't render.
By the time the inbox is empty, the week's work is filed, attributable,
and citable from any chapter that needs it.

### 3. The archive as a knowledge base

Source material that predates the repo — prior proposals, vendor
datasheets, reference papers, old CAD — becomes a **searchable
knowledge base**, not a dead folder. The pattern (borrowed from a
sister project that runs it at ~1.7 GB scale):

- **Commit the index, host the binaries.** The repo carries a
  manifest + browsable index pages; the raw files live in Google Drive,
  mapped path → Drive file-id, with a `[Drive]` link rendered next to
  each document.
- **Validate by reference.** A fresh clone is fully functional with no
  multi-GB download: links validate against manifest *membership*, not
  local disk, and resolve to Drive for anyone with view access.

The template ships the bucketed `archive/` skeleton plus an
[external index](archive/external-index.qmd) for files too large to
carry in git — the starting point you grow into the full knowledge base.

### 4. Search and handoff

Because everything is plain text in one repo, the rendered site's
full-text search spans the thesis, the SOPs, every meeting note, every
experiment log. "When did we first discuss the calibration issue?"
stops being a four-tool tab hunt and becomes one query. Per-page
**ownership** and an auto-generated **revision history** (from git)
make multi-person work and successor handoff legible: every page shows
who owns it and how it changed.

---

## Quick start (once per clone)

```powershell
git config core.longpaths true                 # deep generated paths > Windows MAX_PATH
git config core.hooksPath scripts/git-hooks    # video-size + front-matter-drift guards
git lfs install --skip-repo                    # LFS filters (hooks come from hooksPath)
py -3.12 -m venv .venv                         # project venv (used by the Quarto hooks)
.venv\Scripts\python.exe -m pip install -r requirements.txt
.\thesis.ps1 doctor                            # verifies all of the above
```

macOS/Linux: `python3 -m venv .venv` and `.venv/bin/python3`; the hook
commands in `_quarto.yml` assume Windows paths — adjust there for
cross-platform work.

## Daily driver: `thesis.ps1`

One command surface; every subcommand names the script it wraps, and
the python scripts are directly callable on any OS.

```powershell
.\thesis.ps1 render                  # HTML site — unchanged pages come from cache
.\thesis.ps1 render-one A1-EX-001    # iterate on ONE page in seconds
.\thesis.ps1 preview                 # live reload for book chapters
.\thesis.ps1 new experiment --epic A1 --slug first-trial --title "..."
.\thesis.ps1 audit --fix             # repair front-matter drift
.\thesis.ps1 publish                 # gated publish to GitHub Pages
.\thesis.ps1 help                    # the full table
```

A note on speed: the PM pages render through a **content-hash cache**,
so a no-change rebuild restores in seconds instead of re-running ~50
Quarto subprocesses. See [docs/render-pipeline.md](docs/render-pipeline.md).

## Script inventory

| Script (`scripts/render/`) | Purpose | Runs | Docs |
|---|---|---|---|
| `_lib.py` | Shared helpers: front matter, write-only-if-changed, one-pass git history | imported | [render-pipeline](docs/render-pipeline.md) |
| `build_listings.py` | `listing.yml` + `_listing.md` tables from front matter | pre-render hook | [render-pipeline](docs/render-pipeline.md) |
| `build_gantt.py` | Frozen per-WU Gantt PNGs from the Mermaid block in `index.qmd` | pre-render hook | [weekly-update](docs/workflow-weekly-update.md) |
| `build_file_trees.py` | Per-item `_files.md` file inventories | pre-render hook | [item-lifecycle](docs/workflow-item-lifecycle.md) |
| `build_revisions.py` | Per-page `_revisions.md` change history from git | pre-render hook | [item-lifecycle](docs/workflow-item-lifecycle.md) |
| `build_board.py` | `_board.md`: epic tables + kanban + stale items | pre-render hook | [item-lifecycle](docs/workflow-item-lifecycle.md) |
| `render_satellites.py` | Renders PM/update pages to standalone HTML, **content-hash cached** | post-render hook | [render-pipeline](docs/render-pipeline.md) |
| `new_item.py` | Scaffolds experiments / features / issues / epics / WUs | `thesis.ps1 new` | [item-lifecycle](docs/workflow-item-lifecycle.md) |
| `audit_items.py` | Front-matter contract check (`--fix` repairs) | pre-commit hook + publish gate | [item-lifecycle](docs/workflow-item-lifecycle.md) |
| `disperse.py` | Stages `$THESIS_INBOX` → `_inbox/<week>/` for the `/disperse` skill | weekly | [inbox-dispersal](docs/workflow-inbox-dispersal.md) |
| `publish.py` | audit → render → link check → prose check → gh-pages | `thesis.ps1 publish` | [publish-qc](docs/workflow-publish-qc.md) |
| `qc/link_check.py` | Broken-internal-link gate over `_site/` | inside publish | [publish-qc](docs/workflow-publish-qc.md) |
| `qc/prose_check.py` | cspell + Vale wrappers (advisory) | inside publish | [publish-qc](docs/workflow-publish-qc.md) |

Tier-2 tools live under `scripts/tools/<area>/` (the included
`google-drive-embed/` hosts large videos off-repo). Claude Code skills:
`/disperse` (weekly routing) and `/grammar-review` (pre-publish prose
pass) under `.claude/skills/`.

## Repo layout

```
index.qmd          dashboard: Gantt + generated board (kanban, stale items)
chapters/          THESIS BOOK — the only book-rendered content (incl. SOPs)
initiatives/       PM tree: <initiative>/epics/<epic>/{experiments,features,issues}/
updates/           weekly advisor decks: WU-YYYY-MM-DD-week-NN/
archive/           source-material knowledge base (index in repo, binaries in Drive)
docs/              contributor workflow docs (this machine's manual)
scripts/render/    tier-1 render pipeline (table above)
scripts/tools/     tier-2 cross-cutting tools
scripts/git-hooks/ pre-commit guards (video size, front-matter drift)
_extensions/       Lua shortcodes (tool, model, revisions) + patent format
styles/            SCSS + LaTeX preamble
thesis.ps1         the command surface
GETTING-STARTED.md personalization checklist for a fresh clone
```

## Where to read next

- [GETTING-STARTED.md](GETTING-STARTED.md) — personalize a fresh clone
- [docs/](docs/README.md) — the workflow manual (render pipeline +
  cache, item lifecycle, inbox dispersal, weekly updates, publish/QC)
- [CLAUDE.md](CLAUDE.md) — guardrails for AI agents working in the repo
- [docs/decisions.md](docs/decisions.md) — the architectural decision log

## Publishing

`.\thesis.ps1 publish` runs the gated pipeline (audit → render → link
check → gh-pages). Snapshot zips and self-hosting are in
[docs/workflow-publish-qc.md](docs/workflow-publish-qc.md). VS Code
recommends extensions via `.vscode/extensions.json`; project jargon
lives in `.cspell.json`.
