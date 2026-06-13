"""Render satellite pages as standalone HTML into the book's _site/.

The thesis is a Quarto book project, so only files registered under
`book.chapters` / `book.appendices` are rendered to HTML during the
main `quarto render` pass. That leaves the appendix listing children
(weekly-update decks, initiative + epic + experiment READMEs) without
HTML output — their listing cards would point at raw .qmd files, which
404 in a browser.

This script closes that gap. It runs as a Quarto post-render hook
(see `_quarto.yml`) and:

1. Finds every satellite .qmd: `updates/WU-*/index.qmd` and
   `initiatives/**/README.qmd` (initiative, epic, experiment).
2. Sets up ONE temp directory that mirrors the repo's top-level layout
   (the `initiatives/` tree minus .qmd sources), shared by every
   satellite rendered this run. Rendering in the tempdir keeps the
   book's `_quarto.yml` out of scope so each file emits a standalone
   HTML, and cross-tree relative URLs (a WU deck linking into the
   experiment tree) resolve the same way they do in the real tree.
3. Runs `quarto render <file>.qmd --to all` inside the temp dir,
   producing `<stem>.html` (+ `<stem>-slides.html` for WU decks)
   plus `<stem>*_files/` asset directories (reveal.js, videojs, etc.).
4. Injects a fixed "← Back" link and rewrites `.qmd` hrefs to `.html`,
   then copies the post-processed outputs into `_site/<original-dir>/`
   AND into the satellite cache store.
5. Rewrites the dashboard + appendix listing index HTML files to
   replace `.qmd` hrefs with `.html` so cards land on rendered pages.

## The satellite cache

Each satellite's inputs are fingerprinted into a cache key:

- sha256 of the source .qmd,
- sha256 of every sibling `_*.md` generated partial (`_listing.md`,
  `_files.md`, `_revisions.md` — presence/absence included),
- size+mtime of sibling asset dirs (data/images/videos/media) and
  loose non-underscore files,
- the computed back-link (href + parent page title),
- for decks that reference `../../initiatives/...` files: size+mtime
  of those cross-tree files.

If the key matches the manifest and the store has the outputs, the
page is restored from `.quarto/satellite-cache/store/` instead of
re-rendered — a warm full render skips all ~50 quarto subprocesses.

Global inputs (this script itself, the Quarto version, CACHE_SCHEMA)
invalidate everything when they change. RULE: anything new that gets
copied into the shared mirror for ALL satellites (e.g. a future shared
`_metadata.yml`) must be added to `global_key()`.

Generated inputs stay cache-stable because every generator writes
only-if-changed (see scripts/render/_lib.py). Binary assets are
fingerprinted by size+mtime, not content — worst case after a fresh
clone is one spurious re-render, never a stale page.

CLI:
    --force          ignore the manifest; render everything selected
    --only <substr>  restrict to satellites whose repo-relative path
                     contains <substr> (the single-page fast path;
                     `thesis.ps1 render-one` uses `--only X --force`)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _lib import ROOT, stat_manifest, write_text_if_changed

SITE = ROOT / "_site"
CACHE_SCHEMA = 1
CACHE_DIR = ROOT / ".quarto" / "satellite-cache"
MANIFEST = CACHE_DIR / "manifest.json"
STORE = CACHE_DIR / "store"
SATELLITE_ASSET_DIRS = {"data", "videos", "images", "media"}
# GitHub Pages rejects any single blob > 100 MB on push to gh-pages. The
# mp4 source of truth is the local LFS blob in the repo + the Drive embed
# iframe in the rendered HTML; the copy into _site/ is purely redundant
# and is what blocks `quarto publish gh-pages`. Skip anything that would
# breach the limit (with a small safety margin).
MAX_SITE_FILE_BYTES = 95 * 1024 * 1024
BACK_LINK_LABELS = {
    "updates": "Weekly updates",
    "initiatives": "Initiatives",
}
BACK_LINK_STYLE = (
    "position:fixed;top:12px;left:12px;z-index:10000;"
    "background:rgba(255,255,255,0.92);padding:6px 12px;border-radius:4px;"
    "text-decoration:none;color:#333;"
    "font-family:system-ui,-apple-system,sans-serif;font-size:14px;"
    "box-shadow:0 1px 4px rgba(0,0,0,0.15);"
)


def iter_satellites():
    yield from sorted((ROOT / "updates").glob("WU-*/index.qmd"))
    for p in sorted((ROOT / "initiatives").glob("**/README.qmd")):
        # Skip the item-template tree (mirrors _quarto.yml's book-render
        # exclude, which doesn't reach this post-render satellite pass).
        if "_template" in p.parts:
            continue
        yield p


def rel_posix(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _ignore_qmd(_dir: str, names: list[str]) -> list[str]:
    return [n for n in names if n.endswith(".qmd")]


def _ignore_oversized(directory: str, names: list[str]) -> list[str]:
    """copytree ignore: skip files larger than MAX_SITE_FILE_BYTES.

    Drive-embedded videos are the intended target — playback runs via
    the `<iframe>` in the rendered HTML regardless of whether the local
    mp4 ships with the site. The local LFS blob in the repo remains
    intact for fresh clones / offline reference.
    """
    base = Path(directory)
    skipped: list[str] = []
    for n in names:
        p = base / n
        try:
            if p.is_file() and p.stat().st_size > MAX_SITE_FILE_BYTES:
                skipped.append(n)
        except OSError:
            continue
    return skipped


# ---------------------------------------------------------------------------
# Cache keys


def sibling_partials(src: Path) -> list[Path]:
    """Generated `_*.md` partials beside the satellite (sorted)."""
    return sorted(p for p in src.parent.glob("_*.md") if p.is_file())


def asset_paths(src_parent: Path) -> tuple[list[Path], list[Path]]:
    """(asset dirs, loose files) the satellite ships alongside its HTML."""
    dirs = [src_parent / d for d in sorted(SATELLITE_ASSET_DIRS)
            if (src_parent / d).is_dir()]
    loose = sorted(
        p for p in src_parent.iterdir()
        if p.is_file() and p.suffix != ".qmd" and not p.name.startswith("_")
    )
    return dirs, loose


# Cross-tree references a WU deck makes into the initiatives tree
# (images / videos pulled straight from an experiment's media/). Only
# the referenced files join the deck's cache key — a new photo dropped
# into some item must not invalidate decks that never mention it.
XREF_RX = re.compile(r"\.\./\.\./(initiatives/[^)\s\"'>]+)")


def cross_ref_files(src: Path) -> list[Path]:
    try:
        text = src.read_text(encoding="utf-8")
    except OSError:
        return []
    out: set[Path] = set()
    for m in XREF_RX.finditer(text):
        p = ROOT / m.group(1)
        # Only embeddable assets (images/video/data) join the key.
        # Linked .qmd/.md pages are hyperlinks, never inlined into the
        # deck's HTML — tracking them would re-render decks whenever a
        # linked page is merely edited.
        if p.suffix.lower() in {".qmd", ".md"}:
            continue
        if p.is_file():
            out.add(p)
    return sorted(out)


def compute_key(src: Path) -> str:
    parent_rel = src.parent.relative_to(ROOT)
    parts: dict = {
        "qmd": hashlib.sha256(src.read_bytes()).hexdigest(),
        "partials": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sibling_partials(src)},
        # Back link href + label: the label is the PARENT page's title,
        # so renaming an epic re-renders its children's back links.
        "back_link": back_link_target(parent_rel.parts),
    }
    dirs, loose = asset_paths(src.parent)
    parts["assets"] = stat_manifest(src.parent, dirs + loose)
    xrefs = cross_ref_files(src)
    if xrefs:
        parts["xrefs"] = stat_manifest(ROOT, xrefs)
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def quarto_version() -> str:
    try:
        proc = subprocess.run(["quarto", "--version"],
                              capture_output=True, text=True)
        return proc.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def global_key() -> dict:
    """Inputs shared by every satellite render. Mismatch ⇒ full rebuild."""
    return {
        "schema": CACHE_SCHEMA,
        "script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "quarto": quarto_version(),
    }


def store_dir_for(rel: str) -> Path:
    return STORE / hashlib.sha1(rel.encode("utf-8")).hexdigest()[:16]


def load_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# Output store + asset sync


def store_outputs(satellite_dir: Path, stem: str, store: Path) -> None:
    """Snapshot post-processed render outputs into the cache store."""
    if store.exists():
        shutil.rmtree(store)
    store.mkdir(parents=True)
    for html in satellite_dir.glob(f"{stem}*.html"):
        shutil.copy2(html, store / html.name)
    for files_dir in satellite_dir.glob(f"{stem}*_files"):
        if files_dir.is_dir():
            shutil.copytree(files_dir, store / files_dir.name)


def restore_outputs(store: Path, dest_dir: Path) -> None:
    """Copy store contents into _site/, skipping byte-identical files."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for entry in store.iterdir():
        target = dest_dir / entry.name
        if entry.is_dir():
            want = stat_manifest(entry, [entry])
            have = stat_manifest(target, [target]) if target.exists() else []
            if want != have:
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(entry, target)
        else:
            try:
                ts, es = target.stat(), entry.stat()
                if (ts.st_size == es.st_size
                        and ts.st_mtime_ns == es.st_mtime_ns):
                    continue
            except OSError:
                pass
            shutil.copy2(entry, target)


def sync_assets(src_parent: Path, dest_dir: Path) -> None:
    """Mirror asset dirs + loose files into _site/, skipping unchanged.

    copy2 preserves mtimes, so the size+mtime comparison is exact on
    subsequent runs. Oversize files never ship (GitHub Pages limit).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dirs, loose = asset_paths(src_parent)
    for d in dirs:
        target = dest_dir / d.name
        want = [e for e in stat_manifest(d, [d])
                if e[1] <= MAX_SITE_FILE_BYTES]
        have = stat_manifest(target, [target]) if target.exists() else []
        if want != have:
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(d, target, ignore=_ignore_oversized)
    for f in loose:
        if f.stat().st_size > MAX_SITE_FILE_BYTES:
            continue
        # Loose root files (lab notes, one-off data dumps) are part
        # of the item's file inventory (_files.md links them), so
        # they must be downloadable from _site/ too.
        target = dest_dir / f.name
        try:
            ts, fs = target.stat(), f.stat()
            if ts.st_size == fs.st_size and ts.st_mtime_ns == fs.st_mtime_ns:
                continue
        except OSError:
            pass
        shutil.copy2(f, target)


# ---------------------------------------------------------------------------
# Rendering


def render_standalone(src: Path, mirror: Path) -> None:
    """Render one satellite inside the shared mirror and post-process
    its outputs in place (back link + .qmd→.html hrefs)."""
    src_parent_rel = src.parent.relative_to(ROOT)
    satellite_dir = mirror / src_parent_rel
    satellite_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, satellite_dir / src.name)

    if src_parent_rel.parts[0] != "initiatives":
        # The shared mirror only pre-copies the initiatives/ tree.
        # Non-initiatives satellites (WU decks) bring their own
        # partials + asset dirs + loose files.
        for partial in sibling_partials(src):
            shutil.copy2(partial, satellite_dir / partial.name)
        dirs, loose = asset_paths(src.parent)
        for d in dirs:
            shutil.copytree(d, satellite_dir / d.name, dirs_exist_ok=True)
        for f in loose:
            shutil.copy2(f, satellite_dir / f.name)

    # embed-resources => self-contained HTML with no `<stem>_files/` dir.
    # Critical on Windows for the DEEP experiment pages + revealjs update
    # decks, whose generated `_files/libs/.../<hash>` paths blow past
    # MAX_PATH. BUT initiative + epic hub READMEs are shallow enough to keep
    # a normal `_files/` dir under the limit, and they embed PDFs via
    # <iframe> — which browsers refuse to render from a `data:` URI. So skip
    # embed-resources for those hub pages (relative iframe/asset srcs then
    # resolve against the copied media/).
    rel_parts = src_parent_rel.parts
    is_hub = (rel_parts[:1] == ("initiatives",)
              and src.name == "README.qmd"
              and "experiments" not in rel_parts)
    # Per-file opt-out: a deep satellite can declare `embed-resources: false`
    # in its front matter if it relies on external <iframe> srcs (e.g. Drive
    # video embeds) that embed-resources would otherwise rewrite into broken
    # data: URLs.
    opt_out = _frontmatter_has(src, "embed-resources", "false")
    cmd = ["quarto", "render", src.name, "--to", "all"]
    if not is_hub and not opt_out:
        cmd += ["-M", "embed-resources:true"]
    subprocess.run(cmd, cwd=satellite_dir, check=True)

    for html in satellite_dir.glob(f"{src.stem}*.html"):
        inject_back_link(html, rel_parts)
        # Cross-references between satellites use `.qmd` hrefs in
        # the source; rewrite to `.html` so they resolve in _site/.
        rewrite_qmd_hrefs(html)


def _read_title(qmd: Path) -> str | None:
    if not qmd.exists():
        return None
    m = re.search(r'^title:\s*"?(.*?)"?\s*$',
                  qmd.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1).strip() if m else None


def _frontmatter_has(qmd: Path, key: str, value: str) -> bool:
    """True iff the file's front matter has `<key>: <value>` (scalar)."""
    if not qmd.exists():
        return False
    text = qmd.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return False
    return bool(re.search(rf"^{re.escape(key)}:\s*{re.escape(value)}\s*$",
                          m.group(1), re.MULTILINE))


def back_link_target(parts: tuple[str, ...]) -> tuple[str, str] | None:
    """Return (href, label) for an 'up one level' back link, or None.

    For the initiatives tree the back link climbs the hierarchy — an
    experiment goes back to its epic, an epic back to its initiative, an
    initiative back to the Initiatives index — rather than always jumping to
    the top index. Other groups (updates) keep the simple 'back to the
    group index' behaviour.
    """
    if not parts:
        return None
    group = parts[0]
    if group == "initiatives":
        # initiatives/<I>/epics/<E>/experiments/<X>/  -> back to epic <E>
        if len(parts) == 6 and parts[2] == "epics" and parts[4] == "experiments":
            epic = ROOT / "initiatives" / parts[1] / "epics" / parts[3] / "README.qmd"
            return ("../../README.html", _read_title(epic) or parts[3])
        # initiatives/<I>/epics/<E>/  -> back to initiative <I>
        if len(parts) == 4 and parts[2] == "epics":
            init = ROOT / "initiatives" / parts[1] / "README.qmd"
            return ("../../README.html", _read_title(init) or parts[1])
        # initiatives/<I>/  -> back to the Initiatives index
        if len(parts) == 2:
            return ("../index.html", "Initiatives")
        return None
    label = BACK_LINK_LABELS.get(group)
    if label is None:
        return None
    depth = len(parts) - 1
    return (("../" * depth) + "index.html", label)


def inject_back_link(html_file: Path, parts: tuple[str, ...]) -> None:
    target = back_link_target(parts)
    if target is None:
        return
    href, label = target
    snippet = (
        f'<a href="{href}" class="site-back-link" '
        f'style="{BACK_LINK_STYLE}">← {label}</a>'
    )
    text = html_file.read_text(encoding="utf-8")
    if 'class="site-back-link"' in text:
        return
    patched, count = re.subn(r"(<body[^>]*>)", r"\1" + snippet, text, count=1)
    if count:
        html_file.write_text(patched, encoding="utf-8")


QMD_HREF_RX = re.compile(r'(href="[^"#]+)\.qmd((?:#[^"]*)?")')


def rewrite_qmd_hrefs(html_file: Path) -> None:
    """Rewrite href="...foo.qmd[#fragment]" → href="...foo.html[#fragment]".

    Cross-references in `.qmd` source files point at sibling `.qmd`s
    (the editor-time view); the rendered site needs them to point at
    the corresponding `.html` outputs. Handles an optional `#fragment`
    suffix (anchor link into a section heading).
    """
    if not html_file.exists():
        return
    original = html_file.read_text(encoding="utf-8")
    patched = QMD_HREF_RX.sub(r'\1.html\2', original)
    if patched != original:
        html_file.write_text(patched, encoding="utf-8")


# Kept for backwards compatibility with the post-render orchestration
# call site — both names rewrite the same way.
rewrite_listing_hrefs = rewrite_qmd_hrefs


# ---------------------------------------------------------------------------
# Orchestration


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Render satellite pages into _site/ (cached).")
    ap.add_argument("--force", action="store_true",
                    help="ignore the cache manifest; render everything "
                         "selected")
    ap.add_argument("--only", metavar="SUBSTR", default=None,
                    help="restrict to satellites whose repo-relative path "
                         "contains SUBSTR (e.g. 'A5-EX-002' or "
                         "'updates/WU-2026-05-29')")
    args = ap.parse_args(argv)

    if not SITE.exists():
        print(f"_site/ not found at {SITE} — skipping satellite render",
              file=sys.stderr)
        return 0

    all_sats = list(iter_satellites())
    selected = all_sats
    if args.only:
        needle = args.only.replace("\\", "/").lower()
        selected = [s for s in all_sats if needle in rel_posix(s).lower()]
        if not selected:
            print(f"--only {args.only!r} matched no satellites",
                  file=sys.stderr)
            return 1

    manifest = load_manifest()
    gkey = global_key()
    global_changed = manifest.get("global") != gkey
    # A global-key change invalidates the WHOLE store. Only a full run is
    # allowed to act on that (wipe + reset). Under --only we must NOT wipe
    # the other satellites' cache or bless the new global key — otherwise
    # `render-one` after editing this script (which changes the global key)
    # would silently discard all other entries, forcing a cold full rebuild.
    # Leaving the old global key in place means the next FULL render still
    # detects the mismatch and rebuilds correctly.
    if global_changed and not args.only:
        if manifest:
            print("satellites: global inputs changed (script/quarto/schema) "
                  "— cache invalidated")
        manifest = {"global": gkey, "satellites": {}}
        if STORE.exists():
            shutil.rmtree(STORE)
    elif global_changed and args.only:
        print("satellites: global inputs changed, but --only is active — "
              "keeping the full cache (next full render rebuilds it)")
    sats_manifest: dict = manifest.setdefault("satellites", {})

    rendered = restored = 0
    to_render: list[tuple[Path, str, str, Path]] = []
    for src in selected:
        rel = rel_posix(src)
        key = compute_key(src)
        store = store_dir_for(rel)
        entry = sats_manifest.get(rel)
        if (not args.force and entry and entry.get("key") == key
                and store.exists()):
            dest_dir = SITE / Path(rel).parent
            restore_outputs(store, dest_dir)
            sync_assets(src.parent, dest_dir)
            restored += 1
        else:
            to_render.append((src, rel, key, store))

    if to_render:
        # ONE shared mirror per run (short prefix: deep experiment paths
        # under %TEMP% must stay below Windows MAX_PATH).
        with tempfile.TemporaryDirectory(prefix="sat-") as tmp:
            mirror = Path(tmp)
            cross_src = ROOT / "initiatives"
            if cross_src.exists():
                # Cross-reference tree (assets only, no .qmd — we don't
                # want Quarto re-rendering siblings). WU decks link to
                # `../../initiatives/<I>/.../media/*` directly; the
                # initiatives satellites also find their own partials +
                # asset dirs here.
                shutil.copytree(cross_src, mirror / "initiatives",
                                ignore=_ignore_qmd)
            for src, rel, key, store in to_render:
                render_standalone(src, mirror)
                satellite_dir = mirror / Path(rel).parent
                dest_dir = SITE / Path(rel).parent
                store_outputs(satellite_dir, src.stem, store)
                restore_outputs(store, dest_dir)
                sync_assets(src.parent, dest_dir)
                sats_manifest[rel] = {"key": key}
                rendered += 1

    # Prune cache entries whose source satellite no longer exists
    # (always judged against the FULL satellite set, not --only).
    live = {rel_posix(s) for s in all_sats}
    pruned = 0
    for rel in list(sats_manifest):
        if rel not in live:
            sats_manifest.pop(rel)
            stale_store = store_dir_for(rel)
            if stale_store.exists():
                shutil.rmtree(stale_store)
            pruned += 1

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    write_text_if_changed(
        MANIFEST, json.dumps(manifest, indent=1, sort_keys=True))

    # The dashboard + appendix listing pages are book-rendered from
    # sources whose links point at editor-time .qmd paths; rewrite to
    # the rendered .html outputs.
    for page in (SITE / "index.html",
                 SITE / "updates" / "index.html",
                 SITE / "initiatives" / "index.html"):
        rewrite_listing_hrefs(page)

    print(f"satellites: {rendered} rendered, {restored} restored from "
          f"cache, {pruned} pruned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
