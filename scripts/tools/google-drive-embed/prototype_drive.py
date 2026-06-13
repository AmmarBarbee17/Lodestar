# /// script
# requires-python = ">=3.10"
# dependencies = ["google-api-python-client>=2.100", "google-auth-oauthlib>=1.2"]
# ///
"""Prototype: personal Google Drive upload + public link + /preview embed.

A *personal* Google account has no enterprise admin gates (unlike many
university SharePoint/Box tenants), so this should just work — proving
the embed pipeline (upload -> anyone-with-link -> /preview iframe) is
viable with zero IT involvement and zero manual iframe work.

ONE-TIME SETUP (no IT; ~10 min), all on your personal/student Google account:
  1. https://console.cloud.google.com  ->  create a project (any name).
  2. "APIs & Services" -> "Library" -> enable **Google Drive API**.
  3. "APIs & Services" -> "OAuth consent screen" -> User type **External** ->
     fill the minimum -> under **Test users** add your own Google address.
  4. "Credentials" -> "Create credentials" -> "OAuth client ID" ->
     application type **Desktop app**. Download the JSON and save it next to
     this script as  client_secret.json .
  5. Run:  python scripts/tools/google-drive-embed/prototype_drive.py
     A browser opens once -> pick your student Google account -> Allow.

Uploads a tiny test file, makes it "anyone with the link" readable, prints the
embeddable /preview URL, then deletes it. Writes _proto_result.md. The login is
cached to token.json so later runs need no browser. (client_secret.json and
token.json are gitignored — they're secrets.)
"""
from __future__ import annotations

import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

HERE = Path(__file__).resolve().parent
# drive.file = access only to files THIS app creates. It's a non-sensitive
# scope, so the consent screen needs no Google verification/audit.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_creds() -> Credentials:
    token = HERE / "token.json"
    if token.exists():
        c = Credentials.from_authorized_user_file(str(token), SCOPES)
        if c and c.valid:
            return c
    secret = HERE / "client_secret.json"
    if not secret.exists():
        raise SystemExit(
            "Missing client_secret.json — do the one-time setup at the top of "
            "this file (create a Desktop OAuth client and save its JSON here).")
    creds = InstalledAppFlow.from_client_secrets_file(
        str(secret), SCOPES).run_local_server(port=0)
    token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def main() -> int:
    drive = build("drive", "v3", credentials=get_creds())
    f = drive.files().create(
        body={"name": "_thesis-embed-test.txt"},
        media_body=MediaInMemoryUpload(b"thesis embed prototype",
                                       mimetype="text/plain"),
        fields="id,name").execute()
    fid = f["id"]
    print("Upload OK — file id", fid)

    perm = drive.permissions().create(
        fileId=fid, body={"type": "anyone", "role": "reader"}).execute()
    embed = f"https://drive.google.com/file/d/{fid}/preview"
    print("Public 'anyone with link' permission:", perm.get("id"))
    print("EMBED URL:", embed)

    out = {
        "upload": "OK",
        "public_permission_id": perm.get("id"),
        "embed_url_form": "https://drive.google.com/file/d/<ID>/preview",
        "verdict": "Personal Google Drive upload + anyone-with-link + /preview "
                   "embed all OK — full auto-embed pipeline is viable, no IT.",
    }
    drive.files().delete(fileId=fid).execute()  # clean up test file
    print("\nVERDICT:", out["verdict"])
    (HERE / "_proto_result.md").write_text(
        "# Google Drive embed prototype — result\n\n```json\n"
        + json.dumps(out, indent=2) + "\n```\n", encoding="utf-8")
    print("Wrote", HERE / "_proto_result.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
