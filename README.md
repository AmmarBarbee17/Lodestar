# Quarto Thesis + PM Template

Template for running a graduate thesis as a **Quarto book** fused with
a file-based **project-management surface**: a top-level Gantt + kanban
dashboard, an Initiative → Epic → Item work tree with per-page
ownership and revision history, weekly advisor decks, and an archive —
all plain text, git-tracked, rendered into one HTML site (plus a PDF
of the thesis chapters).

**New clone? Start with [GETTING-STARTED.md](GETTING-STARTED.md)** —
the personalization checklist plus a guided first render.

- **Workflow documentation lives in [`docs/`](docs/README.md)** — one
  page per workflow (render pipeline + caching, item lifecycle, inbox
  dispersal, weekly updates, publish/QC) plus the
  [decision log](docs/decisions.md).
- **Agent guardrails live in [`CLAUDE.md`](CLAUDE.md).**

## First-time setup (once per clone)

```powershell
git config core.longpaths true                 # deep generated paths > Windows MAX_PATH
git config core.hooksPath scripts/git-hooks    # video-size + front-matter-drift guards
git lfs install --skip-repo                    # LFS filters (hooks come from hooksPath)
py -3.12 -m venv .venv                         # project venv (used by the Quarto hooks)
.venv\Scripts\python.exe -m pip install -r requirements.txt
.\thesis.ps1 doctor                            # verifies all of the above
```

macOS/Linux: same idea with `python3 -m venv .venv` and
`.venv/bin/python3`; the hook commands in `_quarto.yml` assume Windows
paths — adjust there if you work cross-platform.

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

Tier-2 tools live under `scripts/tools/<area>/` with their own deps
(the included `google-drive-embed/` pipeline hosts large videos on
Google Drive because GitHub Pages won't serve git-LFS files). Claude
Code skills: `/disperse` (weekly routing) and `/grammar-review`
(pre-publish prose pass) under `.claude/skills/`.

## Repo layout

```
index.qmd          dashboard: Gantt + generated board (kanban, stale items)
chapters/          THESIS BOOK — the only book-rendered content (incl. SOPs)
initiatives/       PM tree: <initiative>/epics/<epic>/{experiments,features,issues}/
updates/           weekly advisor decks: WU-YYYY-MM-DD-week-NN/
archive/           historical source material (LFS-backed buckets)
docs/              contributor workflow docs (this machine's manual)
scripts/render/    tier-1 render pipeline (table above)
scripts/tools/     tier-2 cross-cutting tools
scripts/git-hooks/ pre-commit guards (video size, front-matter drift)
_extensions/       Lua shortcodes (tool, model, revisions) + patent format
styles/            SCSS + LaTeX preamble
thesis.ps1         the command surface
GETTING-STARTED.md personalization checklist for a fresh clone
```

## Publishing

`.\thesis.ps1 publish` runs the gated pipeline and pushes to GitHub
Pages. Snapshot zips and self-hosting are documented in
[docs/workflow-publish-qc.md](docs/workflow-publish-qc.md).

## VS Code

The repo recommends extensions via `.vscode/extensions.json`. Project
jargon lives in `.cspell.json` — extend it as the spell checker flags
new terms.
