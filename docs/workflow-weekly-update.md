# Weekly updates (WU decks)

One revealjs deck per active week, presented to the advisor and kept
forever as the project's chronological record. Each WU is a directory:

```
updates/WU-2026-05-21-week-19/
├── index.qmd          # revealjs deck + HTML landing (same source)
└── media/
    ├── gantt.png      # frozen Gantt snapshot for this week
    └── *.png/jpg/mp4  # WU-specific media
```

## Creating one

```powershell
.\thesis.ps1 new wu --title "collision results"   # date defaults to today
```

The scaffolder copies `updates/_template/`, infers the
semester-relative week number from existing dirs (prints the
inference; `--week NN` overrides), and patches title/date/owner.
Usually you don't call it directly — the [/disperse
skill](workflow-inbox-dispersal.md) drafts the WU as part of routing
the week's inbox.

## Deck conventions

- Front matter declares both `html` (landing page) and `revealjs`
  (slides → `index-slides.html`).
- Standard sections: *Where I am · Schedule snapshot · Progress this
  week · Blockers · Next week · Questions for advisor*.
- Cross-reference experiments with repo-relative links
  (`../../initiatives/.../README.qmd`); the render pipeline rewrites
  them to `.html`. WU-specific images live in this WU's `media/`, item
  evidence stays with the item.
- The auto-generated change history renders on the HTML landing only
  (wrapped in `unless-format="revealjs"` so it never becomes a slide).

## The frozen Gantt

`build_gantt.py` (pre-render hook) renders `media/gantt.png` from the
Mermaid Gantt in `index.qmd` with the **WU's date** as the red "today"
marker. While the WU's date is today-or-future the PNG tracks schedule
edits; once the date passes, the file on disk freezes — the WU forever
shows the schedule the advisor saw that week. `--force` overrides
(this *rewrites history*; almost never what you want).

## Videos → Google Drive embeds

GitHub Pages won't serve git-LFS files, so demonstration clips don't
ship with the site. Host them on a personal Google Drive and embed via
`<iframe>` instead — `scripts/tools/google-drive-embed/` (see that
directory's README for the one-time OAuth setup):

1. `upload_item_video.py --file <…media/clip.mp4> --item-id <id>`
   uploads the clip to your Drive (`drive.file` OAuth scope; secrets
   `client_secret.json` / `token.json` are gitignored),
2. makes it anyone-with-link readable,
3. caches `{drive_id, embed_url}` in `_video_manifest.json` (idempotent
   re-runs) and prints an `<iframe>` snippet to paste into the item's
   README,
4. deletes the local copy so it never trips the pre-commit 50 MB video
   guard or the LFS quota.

> Don't need off-LFS hosting? Delete `scripts/tools/google-drive-embed/`
> and the two references noted in its README.
