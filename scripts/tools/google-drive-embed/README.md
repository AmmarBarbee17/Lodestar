# google-drive-embed

Host large item videos on a personal Google Drive and embed them via
`<iframe>`, because **GitHub Pages won't serve git-LFS blobs** and
files over 100 MB break the Pages push. The Drive iframe is the
playback path; the video never has to live in the repo.

| File | Role |
|---|---|
| `drive_common.py` | Shared plumbing: OAuth, folder helpers, public-link toggle, the `_video_manifest.json` path. Set `TOP_FOLDER_NAME` here. |
| `upload_item_video.py` | Entry point: upload one item video, cache its embed URL, delete the local copy. CLAUDE.md guardrail 11 + the pre-commit video guard point here. |
| `prototype_drive.py` | One-time connectivity check (uploads a tiny file, makes it public, prints the embed URL, deletes it). |

## One-time setup (~10 min, no IT involvement)

1. <https://console.cloud.google.com> → create a project (any name).
2. **APIs & Services → Library** → enable **Google Drive API**.
3. **OAuth consent screen** → User type **External** → add your own
   Google address under **Test users**.
4. **Credentials → Create credentials → OAuth client ID** → type
   **Desktop app**. Download the JSON, save it here as
   `client_secret.json` (gitignored).
5. Edit `drive_common.py`: set `TOP_FOLDER_NAME` to your Drive media
   folder name.
6. `python scripts/tools/google-drive-embed/prototype_drive.py` — a
   browser opens once for consent; the login caches to `token.json`
   (gitignored) so later runs need no browser.

## Usage

```powershell
.venv\Scripts\python.exe scripts/tools/google-drive-embed/upload_item_video.py `
    --file initiatives/<I>/epics/<E>/experiments/<item>/media/<item-id>-VID-trial-01.mp4 `
    --item-id <item-id>
```

It prints an `<iframe …>` snippet to paste into the item's README.

> **Don't need off-LFS video hosting?** Delete this whole directory and
> the two references to it in `scripts/git-hooks/pre-commit` (the error
> message) and `CLAUDE.md` guardrail 11.
