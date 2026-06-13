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

> Examples in these docs use IDs from the reference implementation
> this template was extracted from (an Automated Fiber Placement
> thesis — epics like `A5-simulated-collision-avoidance`, items like
> `A5-EX-002`). The *patterns* are what matter; your slugs and IDs
> will differ.
