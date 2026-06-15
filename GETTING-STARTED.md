# Getting started with Lodestar

You cloned Lodestar — this checklist turns the template into *your*
thesis repo. Everything else (workflows, conventions, the render
pipeline) is documented in [docs/](docs/README.md).

## 1. One-time machine setup

```powershell
git config core.longpaths true
git config core.hooksPath scripts/git-hooks
git lfs install --skip-repo
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.\thesis.ps1 doctor       # must report all green
```

(Quarto CLI from <https://quarto.org>; a LaTeX distribution only if
you want the PDF build.)

## 2. Personalize (grep for `TODO` to catch them all)

| Where | What |
|---|---|
| `_quarto.yml` | `book.title`, `book.author`, `site-url` (once Pages is set up) |
| `scripts/render/_lib.py` | `DEFAULT_OWNER` — your display name (fills `owner:` everywhere) |
| `index.qmd` | dashboard title + abstract TODO + the Mermaid Gantt (your dates/sections) |
| `chapters/` | rename/extend the example parts; register new files in `_quarto.yml` |
| `.cspell.json` | add your field's jargon as the spell checker flags it |
| `references.bib`, `tools.yml` | your citations and (optional) SOP tool library |
| `scripts/tools/google-drive-embed/` | adapt the hardcoded source paths, or delete the directory if you won't host videos on Drive |
| `$THESIS_INBOX` env var | point at your cloud inbox folder if you'll use the `/disperse` weekly workflow |

After personalizing, propagate your name into the example content:

```powershell
.\thesis.ps1 audit --fix --owner "Your Name"
```

## 3. Build your PM tree

The template ships one worked example of each unit (initiative
`example-research`, epic `A1-example-epic`, experiment `A1-EX-001`,
weekly update week 01) so the first render shows every feature working.
Study them, then replace:

```powershell
# new initiative: copy initiatives/_template/initiative/ to
#   initiatives/<your-slug>/README.qmd and fill the front matter
# (gantt-id A1 is taken by the shipped example epic — use A2+ until you
#  delete it, then renumber freely)
.\thesis.ps1 new epic --initiative <your-slug> --gantt-id A2 --slug <epic-slug> --title "..."
.\thesis.ps1 new experiment --epic A2 --slug <slug> --title "..."
.\thesis.ps1 new wu --title "first weekly update"
```

Add a Gantt bar in `index.qmd` for every epic (the scaffolder reminds
you). Delete the example initiative/epic/WU when you no longer need
the reference — then run `.\thesis.ps1 render` and the cache prunes
them automatically.

## 4. First render

```powershell
.\thesis.ps1 render        # cold: renders everything once
.\thesis.ps1 render       # warm: satellites print "0 rendered, N restored"
.\thesis.ps1 render-one A1-EX-001   # the fast inner loop
```

## 5. Publish (optional)

Create the GitHub repo, push, then `.\thesis.ps1 publish` (gated:
audit → render → link check → gh-pages). Set `site-url` in
`_quarto.yml` and enable Pages on the `gh-pages` branch.

## What to read next

- [docs/workflow-item-lifecycle.md](docs/workflow-item-lifecycle.md) —
  the Initiative → Epic → Item system, ownership, revision tables
- [docs/workflow-weekly-update.md](docs/workflow-weekly-update.md) —
  the advisor-deck cadence
- [docs/render-pipeline.md](docs/render-pipeline.md) — how rendering +
  the satellite cache work (read before touching the pipeline)
