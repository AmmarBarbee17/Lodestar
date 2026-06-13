# /// script
# requires-python = ">=3.10"
# ///
"""Internal-link checker — walk _site/, flag local <a>/<img>/<iframe>/<link>
targets that 404 in the rendered tree. Skips external (http://, https://,
mailto:, data:, tel:, javascript:) — external link-checking needs network +
rate-limit handling and belongs in a CI pass.

Run:  python scripts/render/qc/link_check.py [_site]
Exits 1 on any broken internal target."""
from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[3]
SITE = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "_site")
ATTR_RX = re.compile(r"""(?:href|src)\s*=\s*[\"\']([^\"\'#?]+)""", re.I)
SCRIPT_RX = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.S)
STYLE_RX = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "data:", "tel:",
                     "javascript:", "//", "#")
# Patterns we don't try to resolve on the filesystem:
#  - `${...}` — JS template-literal interpolation captured from revealjs
#    runtime code (we strip <script> blocks, but `_files/` static JS may
#    inline equivalent fragments without the tag).
TEMPLATE_LITERAL_RX = re.compile(r"\$\{")


def is_external(t: str) -> bool:
    return t.startswith(EXTERNAL_PREFIXES) or t == ""


def check_html(html: Path, broken: list) -> None:
    text = html.read_text(encoding="utf-8", errors="ignore")
    # Strip <script>/<style> bodies so href/src-shaped strings inside
    # JS template literals (revealjs runtime) don't get treated as
    # navigable links.
    text = SCRIPT_RX.sub("", text)
    text = STYLE_RX.sub("", text)
    for raw in ATTR_RX.findall(text):
        if is_external(raw):
            continue
        if TEMPLATE_LITERAL_RX.search(raw):
            continue
        url = unquote(urlparse(raw).path)
        if not url:
            continue
        if url.startswith("/"):
            target = SITE / url.lstrip("/")
        else:
            target = (html.parent / url).resolve()
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            try:
                rel = html.relative_to(SITE)
            except ValueError:
                rel = html
            broken.append((str(rel), raw))


def main() -> int:
    if not SITE.exists():
        print(f"link_check: {SITE} does not exist; run `quarto render` first.")
        return 2
    broken: list = []
    n = 0
    for h in SITE.rglob("*.html"):
        n += 1
        check_html(h, broken)
    if broken:
        print(f"link_check: {len(broken)} broken local link(s) across {n} HTML files:")
        for src, t in broken[:50]:
            print(f"  {src}  ->  {t}")
        if len(broken) > 50:
            print(f"  ... and {len(broken) - 50} more")
        return 1
    print(f"link_check: OK ({n} HTML files scanned, no broken local links).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
