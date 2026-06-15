# Contributor docs

One page per workflow. These are the single source of truth for *how
work flows through the repo* — the root [README](../README.md) covers
setup, [CLAUDE.md](../CLAUDE.md) covers agent guardrails, and both
point here instead of duplicating.

| Doc | Covers |
|---|---|
| [render-pipeline.md](render-pipeline.md) | Book vs satellite rendering, the hook order, the satellite cache and its invalidation rules, `render-one`, troubleshooting |
| [workflow-item-lifecycle.md](workflow-item-lifecycle.md) | Initiative → epic → item structure, front-matter contracts, naming/ID conventions, scaffolding, ownership + revision tables, the kanban board |
| [workflow-inbox-dispersal.md](workflow-inbox-dispersal.md) | The weekly inbox: `$THESIS_INBOX` → `disperse.py` staging → `/disperse` skill routing |
| [workflow-weekly-update.md](workflow-weekly-update.md) | Creating WU decks, deck conventions, frozen Gantt snapshots, the Drive video-embed pipeline |
| [workflow-publish-qc.md](workflow-publish-qc.md) | The publish gate sequence (audit → render → link check → prose check → gh-pages) and the three publishing options |
| [decisions.md](decisions.md) | The numbered architectural-decision log |

These render on GitHub (including the Mermaid diagrams) and are *not*
part of the Quarto site — they document the machine, they aren't
content the machine renders.

> Examples in these docs mirror the worked example shipped in the repo
> (the `example-research` initiative, `A1-example-epic`, `A1-EX-001`),
> so you can cross-reference them against real files. The *patterns*
> are what matter; your own slugs and IDs will differ.
