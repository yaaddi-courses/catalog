"""The user guide, FAQ and What's New pages: every screenshot must exist and have alt text,
the manifest and the files on disk must agree, and the version stamp must be present."""
import json
import re
import tempfile
from pathlib import Path

import build_site
import guide_pages

TOOLS = Path(__file__).resolve().parent
PAGES = ("guide", "faq", "whats-new")


def build() -> Path:
    out = Path(tempfile.mkdtemp())
    build_site.render_guide_pages(out)
    return out


def test_pages_render_with_version_stamp():
    out = build()
    version = json.loads((TOOLS / "guide_version.json").read_text(encoding="utf-8"))
    for slug in PAGES:
        html = (out / slug / "index.html").read_text(encoding="utf-8")
        assert f"Checked against Yaaddi {version['app_version']} on {version['verified']}" in html, slug


def test_every_image_exists_has_alt_and_size():
    out = build()
    for slug in PAGES:
        html = (out / slug / "index.html").read_text(encoding="utf-8")
        for tag in re.findall(r"<img [^>]*>", html):
            src = re.search(r'src="\.\./([^"]+)"', tag).group(1)
            assert (TOOLS / "site_assets" / src.removeprefix("assets/")).is_file(), src
            assert re.search(r'alt="[^"]{10,}"', tag), tag
            assert re.search(r'width="\d+" height="\d+"', tag), tag


def test_manifest_matches_files_on_disk():
    manifest = json.loads((TOOLS / "guide" / "guide_shots.json").read_text(encoding="utf-8"))
    listed = {s["file"] for s in manifest["shots"]}
    on_disk = {p.name for p in guide_pages.IMG_DIR.glob("*.png")}
    assert listed == on_disk  # no stale image left over, no shot missing


def test_every_guide_screenshot_is_used():
    used = {f for _, _, _, f in guide_pages.GUIDE_SECTIONS if f}
    assert used == set(guide_pages.SHOT_ALT)


def test_no_external_resources_and_nav_links():
    out = build()
    for slug in PAGES:
        html = (out / slug / "index.html").read_text(encoding="utf-8")
        assert not re.search(r'(src|href)="https?://(?!github\.com|docs\.github\.com)', html), slug
        assert "../guide/index.html" in html and "../faq/index.html" in html


def test_faq_covers_support_basics():
    html = (build() / "faq" / "index.html").read_text(encoding="utf-8")
    assert "support@yaaddi.com" in html and "Do I need an account" in html
