# Quarto thesis — agent guide

A Quarto **book** (thesis chapters in `chapters/`, the only
book-rendered content) plus a file-based PM surface rendered as
satellite pages: `initiatives/<I>/epics/<E>/{experiments,features,issues}/<item>/`,
weekly decks in `updates/WU-*/`, history in `archive/`. One site, one
repo, all plain text.

**The workflow manual lives in [`docs/`](docs/README.md) — read the
relevant page before structural work.** This file is only the
guardrails an agent must not violate. Decision log:
[docs/decisions.md](docs/decisions.md). Fresh clone? Walk the human
through [GETTING-STARTED.md](GETTING-STARTED.md) first.

| Before you… | Read |
|---|---|
| Touch the render pipeline, hooks, or anything generated | [docs/render-pipeline.md](docs/render-pipeline.md) |
| Create/move/edit epics, items, owners, statuses | [docs/workflow-item-lifecycle.md](docs/workflow-item-lifecycle.md) |
| Route inbox files / run `/disperse` | [docs/workflow-inbox-dispersal.md](docs/workflow-inbox-dispersal.md) |
| Draft a weekly update / touch the Gantt | [docs/workflow-weekly-update.md](docs/workflow-weekly-update.md) |
| Publish or change QC | [docs/workflow-publish-qc.md](docs/workflow-publish-qc.md) |

## Hard guardrails

1. **Never hand-create PM structure.** Scaffold with
   `.\thesis.ps1 new experiment|feature|issue|epic|wu …`
   (`scripts/render/new_item.py`). It allocates IDs and self-checks
   against the audit.
2. **Never edit generated files**: `_listing.md`, `_files.md`,
   `_revisions.md`, `_board.md`, `listing.yml`, `updates/*/media/gantt.png`.
   They regenerate every render; fix the *source* (front matter, git
   history, the Mermaid Gantt in `index.qmd`).
3. **Run `.\thesis.ps1 audit` after touching anything under
   `initiatives/`** (the pre-commit hook and publish gate will anyway).
   Canonical statuses: `open / in-progress / blocked / done` — nothing
   else. Schedule emphasis (`crit`) lives on Gantt bars, not in
   `status`.
4. **Cache discipline.** Generated inputs must be written via
   `_lib.write_text_if_changed` / `write_bytes_if_changed`; anything
   new copied into the satellite render mirror for all pages must join
   `global_key()` in `render_satellites.py`. Violating either silently
   turns every render into a full multi-minute rebuild.
5. **The book stays chapters-only.** Don't add PM content to
   `book.chapters`; don't touch chapters during dispersal.
6. **Items own all media; epics own none.** Evidence files live under
   the item (`<item>/{images,videos,data,media}/`), named
   `<item-id>-IMG|VID|DATA-<slug>.<ext>`. Epic-level `media/` is a
   smell.
7. **Epic README sections**: `## Background`, `## Status log` (dated
   bullets, newest first, each linking its WU), `## Resolution` when
   done. The generated listing include owns the item-table headings —
   never wrap it in your own heading.
8. **Frozen Gantt PNGs are history.** Never run
   `build_gantt.py --force` unless explicitly asked to rewrite past
   WU snapshots.
9. **Ownership is advisory.** Respect `owner:` (don't reassign without
   being asked), keep it present on every initiative/epic/item/SOP/WU.
   SOP `revisions:` blocks are formal records — append rows, never
   rewrite existing ones, leave `approved-by` for humans.
10. **Mermaid Gantt in `index.qmd` is the schedule's single source of
    truth.** New epic ⇒ add a bar there (the scaffolder reminds you).
11. **Large media**: videos > 50 MB are blocked by the pre-commit
    hook — upload via
    `scripts/tools/google-drive-embed/upload_item_video.py` instead
    (adapt its paths first; see GETTING-STARTED.md). Files > 95 MB
    never ship to `_site/`.
12. **`thesis.ps1` must stay pure ASCII** (PowerShell 5.1 reads
    BOM-less scripts as ANSI).

## Naming quick reference

| Type | Pattern | Example |
|---|---|---|
| Epic dir | `<gantt-id>-<slug>/` | `A1-example-epic/` |
| Item dir | `<gantt-id>-<EX\|FE\|IS>-<NNN>-<slug>/` | `A1-EX-001-example-experiment/` |
| WU dir | `WU-YYYY-MM-DD-week-NN/` (semester week, not ISO) | `WU-2026-06-12-week-01/` |
| Item media | `<item-id>-<IMG\|VID\|DATA>-<slug>.<ext>` | `A1-EX-001-IMG-trial-01-result.jpg` |
| SOP | `SOP-NN-<slug>.qmd` | `SOP-01-example-procedure.qmd` |

Full schemas: [docs/workflow-item-lifecycle.md](docs/workflow-item-lifecycle.md).

## Command surface

Use `thesis.ps1` (run `.\thesis.ps1 help`), or the underlying
`scripts/render/*.py` directly via `.venv\Scripts\python.exe`. The
README has the full script inventory table.

## Verification after structural changes

```powershell
.\thesis.ps1 audit          # exit 0
.\thesis.ps1 render         # exit 0; warm satellite phase prints
                            # "N rendered, M restored from cache"
.venv\Scripts\python.exe scripts\render\qc\link_check.py   # exit 0
```

Expect in `_site/`: the dashboard kanban renders; each initiative
lists its epics, each epic its items; WU landing pages + `-slides`
decks exist; experiment/WU pages have no `_files/` dir
(embed-resources), hub pages do.
