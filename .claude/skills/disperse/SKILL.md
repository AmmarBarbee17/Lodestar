---
name: disperse
description: >
  Route a week's staged inbox dump into the thesis repo on weekly-update day.
  Use when the user says "/disperse", "disperse the inbox", "process this
  week's dump", or after running scripts/disperse.py. Reads a staged
  _inbox/<YYYY-Www>/ folder (raw photos, videos, CAD, and a rolling
  notes-week-NN.md), then proposes (a) a weekly-update deck draft and (b) a
  per-file routing plan into initiatives/epics/experiments, updates media,
  archive, or data — for the author's approval before moving anything.
---

# Disperse a weekly inbox dump

You are routing one week's raw dump into the repo's organized structure. The
deterministic staging copy is already done by `scripts/render/disperse.py` (it copied
`$THESIS_INBOX` → `_inbox/<YYYY-Www>/` and wrote `_manifest.md`). Your job is the
judgement half: draft the weekly update and propose where each file belongs.

## Repo structure you are routing into

- **Initiative → Epic → Experiment.** Epics live at
  `initiatives/<initiative-slug>/epics/<gantt-id>-<slug>/`. Each epic
  README front matter has a `gantt-id` (`A1`…, `B1`…, Gantt/priority
  order) and `status`.
- **Experiments** live at `…/epics/<slug>/experiments/<gantt-id>-EX-NNN-<slug>/`
  with `README.qmd` + `data/ images/ videos/`. IDs are **epic-prefixed and
  per-epic** (e.g. the 3rd experiment in epic A5 is `A5-EX-003-…`). Media files
  repeat the ID: `A5-EX-003-IMG-trial-01-<desc>.jpg`, `…-VID-…mp4`.
- **Weekly updates** live at `updates/WU-YYYY-MM-DD-week-NN/{index.qmd, media/}`
  (a revealjs deck; topical slug goes in the front-matter `title`, not the dir).
- **archive/** for historical / vendor / reference material; **data/** for
  cross-cutting shared data.

## Process

1. **Find the dump.** Use the most recent `_inbox/<YYYY-Www>/` (or ask which
   week if ambiguous). Read its `_manifest.md` and the rolling `notes-week-NN.md`.
   If there is no staged folder yet, tell the user to run
   `python scripts/render/disperse.py --week <YYYY-Www>` first.

2. **Learn the current targets.** Glob `initiatives/*/epics/*/README.qmd` for
   the live epic slugs + gantt-ids + statuses, and `updates/WU-*/` for existing
   weeks. Never invent an epic; if the notes imply a new one, flag it for the
   author rather than creating it silently.

3. **Draft the weekly update.** Scaffold it with the canonical tool — never
   hand-copy the template (CLAUDE.md guardrail #1):
   `.\thesis.ps1 new wu --title "<topic>"` (or
   `python scripts/render/new_item.py wu --title "<topic>"`). That creates
   `updates/WU-<today>-week-NN/` from the template with the date + semester
   week filled in. Then fill the deck body from the notes file: a one-line
   `description`, and the `## Where I am / Progress this week / Blockers /
   Next week / Questions for advisor` sections. Reference item pages with
   repo-relative links (`../../initiatives/.../README.qmd`) and put deck
   images in this WU's `media/`.

4. **Propose a route for every non-text file** in the dump:
   - tied to a specific item → that item's `images/ | videos/ | data/`,
     renamed to the `<item-id>-IMG|VID-…` convention;
   - a NEW item's evidence → scaffold the item first with
     `.\thesis.ps1 new experiment --epic <gantt-id> --slug <slug> --title "…"`
     (or `feature`/`issue`) — it allocates the next free ID and writes
     audit-clean front matter; never hand-create the directory;
   - illustrates the weekly update itself → `updates/WU-…/media/`;
   - vendor / datasheet / historical reference → `archive/<bucket>/` (or an
     `archive/external-index.qmd` entry if it should stay external);
   - cross-cutting shared data → `data/`.

5. **Propose status-log appends.** For decisions/results captured in the notes,
   draft one-line `## Status log` bullets for the relevant epic README(s).

6. **Present ONE checklist** — a table of `source file → proposed destination
   (+ rename)`, the WU draft path, and the status-log edits. Then STOP and wait
   for explicit approval. Let the author edit or reject rows.

7. **On approval, execute.** **Copy** (don't move) files out of `_inbox/` into
   their destinations — `_inbox/<week>/` stays as the audit trail. Use `git mv`
   only when relocating files already tracked elsewhere in the repo. Create the
   WU dir + draft, apply status-log edits. Then run
   `.venv/Scripts/python.exe scripts/render/build_listings.py` and `quarto render` to
   verify (or hand back to the author to render).

## Guardrails

- Never move/copy anything before the author approves the checklist.
- Preserve `_inbox/<week>/` intact (it is the audit trail); route by copying.
- Follow the naming conventions exactly (epic-prefixed experiment IDs,
  `<id>-IMG/VID` media, `WU-YYYY-MM-DD-week-NN/` dirs). When unsure which epic a
  file belongs to, ask rather than guess.
- Do not touch the Quarto book chapters — the PM content stays in
  `initiatives/`, `updates/`, `archive/`.
