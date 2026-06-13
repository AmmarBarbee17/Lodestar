---
name: grammar-review
description: >
  Run a grammar / clarity / style pass over the thesis prose (`.qmd` files
  under chapters/ and the initiative/epic READMEs) before publishing. Use
  when the user says "/grammar-review", "grammar pass", or runs
  `scripts/render/publish.py` and wants an LLM review. Returns line-numbered
  issues per file; does NOT mutate files without approval.
---

# Grammar-review pass

Pre-publish polish: read the changed-since-last-publish `.qmd` files (chapters
+ initiative/epic READMEs + weekly updates) and return grammar, comma-splice,
subject-verb, and clarity issues with line numbers. Style guidance follows the
existing prose (technical, sentence-case, short sentences, no marketing
voice). Skip code blocks, YAML front matter, math, and SharePoint iframe
URLs.

## Scope

- `chapters/**/*.qmd` (thesis prose).
- `initiatives/**/README.qmd` (initiative + epic + experiment READMEs).
- `updates/WU-*/index.qmd` (weekly-update decks).
- Skip: anything under `_site/`, `archive/`, `_inbox/`, `.venv/`.

## Process

1. Use `git diff --name-only` against the last `gh-pages` push (or
   `--cached`/`HEAD~1` if the author asks) to scope to changed files. If the
   author asks for "everything," walk all the in-scope paths above.
2. For each file:
   - Read it, skip YAML front matter (between `---` fences) and fenced code
     blocks (```), and Quarto shortcodes (`{{< ... >}}`).
   - Identify grammar/clarity issues; output them as
     `<path>:<line>: <issue>` with a one-line suggested rewrite.
3. Present a per-file checklist. STOP — do NOT modify files. Wait for the
   author to accept/edit/reject each item.
4. On approval, apply edits with the Edit tool; preserve front matter,
   shortcodes, and code blocks exactly.

## Guardrails

- Never change technical claims, numbers, units, citation keys, or proper
  nouns (equipment models, vendor names, material designations).
- Never collapse sentence-case headings to title case.
- Never inline-rewrite shortcodes or `<iframe>` URLs.
- Comma splices, subject-verb agreement, dangling modifiers, and run-ons
  are the primary targets — not voice changes.
