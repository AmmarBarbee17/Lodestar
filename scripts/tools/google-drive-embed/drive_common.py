# /// script
# requires-python = ">=3.10"
# dependencies = ["google-api-python-client>=2.100", "google-auth-oauthlib>=1.2", "google-auth>=2.0"]
# ///
"""Shared Google Drive plumbing for the off-LFS video-hosting pattern.

GitHub Pages won't serve git-LFS blobs, so large item videos are hosted
on a personal Google Drive and embedded via `<iframe>`. This module
holds the reusable pieces (OAuth, folder helpers, public-link toggle,
the embed-URL manifest); `upload_item_video.py` is the user-facing
entry point built on top of it.

## One-time setup (see README.md in this directory)

1. Create an OAuth client (Desktop app) in a Google Cloud project with
   the Drive API enabled; download it as `client_secret.json` here
   (gitignored).
2. Run `prototype_drive.py` once to do the browser consent flow and
   cache `token.json` (gitignored).
3. Set `TOP_FOLDER_NAME` below to your Drive media folder name.
"""
from __future__ import annotations

from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
MANIFEST = HERE / "_video_manifest.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# TODO: your Drive root media folder name (created on first upload).
TOP_FOLDER_NAME = "TODO Thesis Media"


# ───────── auth ─────────
def get_creds() -> Credentials:
    token = HERE / "token.json"
    if token.exists():
        c = Credentials.from_authorized_user_file(str(token), SCOPES)
        if c and c.valid:
            return c
        if c and c.expired and c.refresh_token:
            from google.auth.transport.requests import Request
            c.refresh(Request())
            token.write_text(c.to_json(), encoding="utf-8")
            return c
    c = InstalledAppFlow.from_client_secrets_file(
        str(HERE / "client_secret.json"), SCOPES).run_local_server(port=0)
    token.write_text(c.to_json(), encoding="utf-8")
    return c


# ───────── Drive folder helpers ─────────
def _find_folder(drive, name: str, parent_id: str | None) -> str | None:
    q = (f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
         "and trashed=false")
    if parent_id:
        q += f" and '{parent_id}' in parents"
    hits = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    return hits[0]["id"] if hits else None


def _create_folder(drive, name: str, parent_id: str | None) -> str:
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    return drive.files().create(body=body, fields="id").execute()["id"]


def _get_or_create(drive, name: str, parent_id: str | None) -> str:
    return _find_folder(drive, name, parent_id) or _create_folder(drive, name, parent_id)


def top_folder(drive) -> str:
    """Find (or create) the root media folder named TOP_FOLDER_NAME."""
    return _get_or_create(drive, TOP_FOLDER_NAME, None)


# ───────── file ops ─────────
def _make_public(drive, vid: str) -> None:
    try:
        drive.permissions().create(
            fileId=vid, body={"type": "anyone", "role": "reader"}).execute()
    except Exception as e:  # already exists, etc.
        print(f"      (permission note: {e})", flush=True)
