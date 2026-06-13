# /// script
# requires-python = ">=3.10"
# dependencies = ["google-api-python-client>=2.100", "google-auth-oauthlib>=1.2", "google-auth>=2.0"]
# ///
"""Upload one local video to Google Drive, cache the embed URL, and delete the local copy.

When a video lands in
`initiatives/<I>/epics/<E>/{experiments,issues,features}/<X>/media/`
(e.g. via the disperse skill), run this once on the file to:

1. Upload to the Drive layout
   `<TOP_FOLDER_NAME> / item-media / <item-id> / <descriptive>.mp4`
   (anyone-with-link readable). `TOP_FOLDER_NAME` is set in
   `drive_common.py`.
2. Add a `{id, embed}` entry to `_video_manifest.json` keyed by
   `<item-id>-<basename>` so future invocations / consumers can look
   the embed URL up.
3. **Delete the local file from the repo** (and the containing
   `media/` directory if it becomes empty). Use `--keep-local` to
   override.

The pattern: large media should not live both in git-lfs *and* on
GitHub Pages. The Drive iframe is the playback path; the file in the
repo only consumes LFS quota and trips GitHub's 100 MB Pages limit.
This tool collapses that to "in Drive, with an iframe-ready URL".

One-time setup (OAuth client + token) is described in this directory's
README.md.

Run (PEP-723 inline deps, run via uv or the repo .venv):
    python scripts/tools/google-drive-embed/upload_item_video.py \\
        --file initiatives/.../A1-EX-002-.../media/A1-EX-002-VID-trial-01.mp4 \\
        --item-id A1-EX-002

Idempotent: a file already in the manifest under the computed key is
treated as "done" and (by default) deleted locally without a re-upload.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

from drive_common import (  # noqa: E402
    MANIFEST, get_creds, top_folder, _get_or_create, _make_public,
)
from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.http import MediaFileUpload  # noqa: E402

ITEM_MEDIA_FOLDER = "item-media"


def manifest_key(item_id: str, local_path: Path) -> str:
    return f"{item_id}-{local_path.stem}"


def drive_parent(drive, top_id: str, item_id: str) -> str:
    """`<top>/item-media/<item-id>/` — created on demand."""
    return _get_or_create(
        drive, item_id,
        _get_or_create(drive, ITEM_MEDIA_FOLDER, top_id),
    )


def upload(drive, parent_id: str, local: Path, target_name: str) -> str:
    """Upload (or reuse by name in target parent) and return Drive file id."""
    q = (f"name='{target_name}' and '{parent_id}' in parents "
         "and trashed=false")
    hits = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if hits:
        print(f"reusing existing Drive file ({target_name})")
        return hits[0]["id"]
    size_mb = local.stat().st_size / 1e6
    print(f"uploading {target_name} ({size_mb:.0f} MB)...")
    media = MediaFileUpload(
        str(local), mimetype="video/mp4",
        resumable=True, chunksize=8 * 1024 * 1024)
    req = drive.files().create(
        body={"name": target_name, "parents": [parent_id]},
        media_body=media, fields="id")
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  {int(status.progress() * 100)}%")
    return resp["id"]


def delete_local(local: Path) -> None:
    """Remove the local file and the parent `media/` dir if it empties."""
    local.unlink()
    print(f"  removed local: {local.relative_to(ROOT)}")
    parent = local.parent
    try:
        if parent.name == "media" and not any(parent.iterdir()):
            parent.rmdir()
            print(f"  removed empty media/ dir: {parent.relative_to(ROOT)}")
    except OSError:
        pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Upload one item video to Drive, cache the embed, "
                    "and (by default) delete the local copy.")
    ap.add_argument("--file", required=True,
                    help="Path to the local video (e.g. an item's media/...mp4).")
    ap.add_argument("--item-id", required=True,
                    help="Item id (e.g. A1-EX-002, A1-IS-001).")
    ap.add_argument("--name",
                    help="Drive filename (default: derived from local stem).")
    ap.add_argument("--keep-local", action="store_true",
                    help="Don't delete the local file after a successful upload.")
    args = ap.parse_args(argv)

    local = Path(args.file).resolve()
    if not local.exists():
        print(f"ERROR: not found: {local}", file=sys.stderr)
        return 2
    if local.suffix.lower() != ".mp4":
        print(f"WARN: {local.suffix} is not an .mp4 — proceeding anyway")

    target_name = args.name or f"{local.stem}{local.suffix.lower()}"
    key = manifest_key(args.item_id, local)

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}

    if key in manifest:
        rec = manifest[key]
        print(f"already cached: {rec['embed']}")
        if not args.keep_local:
            delete_local(local)
        return 0

    creds = get_creds()
    drive = build("drive", "v3", credentials=creds)
    top_id = top_folder(drive)
    parent_id = drive_parent(drive, top_id, args.item_id)

    file_id = upload(drive, parent_id, local, target_name)
    _make_public(drive, file_id)

    rec = {
        "id": file_id,
        "embed": f"https://drive.google.com/file/d/{file_id}/preview",
    }
    manifest[key] = rec
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest entry: {key} -> {rec['embed']}")

    if not args.keep_local:
        delete_local(local)

    print("Done. Paste the iframe into the item's README:")
    print(f'  <iframe src="{rec["embed"]}" width="100%" height="460" '
          'allow="autoplay" '
          'style="border:1px solid #ccc;border-radius:4px"></iframe>')
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
