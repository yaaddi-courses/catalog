"""Search-engine and sharing output of the site build: canonical URLs, share tags, schema.org
data, robots.txt, sitemap.xml and the Google Play links."""
import json
import re
import xml.etree.ElementTree as ET

import build_site
from test_build_site_render import CARDS, FIXTURE, UNITS, build, write_course

SITE = "https://courses.yaaddi.com"
PLAY = "https://play.google.com/store/apps/details?id=com.yaaddi.app"


def read(out, *parts):
    return out.joinpath(*parts).read_text(encoding="utf-8")


def json_ld(page):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)]


def test_every_page_has_canonical_url_and_share_tags(tmp_path):
    out = build(tmp_path, FIXTURE)
    pages = {"": "index.html", "courses/sample-course/": "courses/sample-course/index.html"}
    pages.update({p: p + "index.html" for p in build_site.STATIC_PAGES})
    for path, file in pages.items():
        page = read(out, file)
        assert f'<link rel="canonical" href="{SITE}/{path}">' in page, path
        assert f'<meta property="og:url" content="{SITE}/{path}">' in page, path
        for tag in ('property="og:title"', 'property="og:description"', 'property="og:image"', 'name="twitter:card"', 'name="description"'):
            assert page.count(tag) == 1, (path, tag)
        assert page.count("<title>") == 1 and page.count("<h1") == 1, path


def test_static_pages_list_matches_the_pages_built(tmp_path):
    out = build(tmp_path, FIXTURE)
    built = {f"{p.parent.name}/" for p in out.glob("*/index.html")}
    assert built == set(build_site.STATIC_PAGES)


def test_course_page_shares_its_cover_and_describes_the_course(tmp_path):
    page = read(build(tmp_path, FIXTURE), "courses", "sample-course", "index.html")
    assert f'<meta property="og:image" content="{SITE}/images/sample-course/cover.png">' in page
    assert '<meta name="twitter:card" content="summary_large_image">' in page
    assert "Free Flashcard Course | Yaaddi</title>" in page
    course, breadcrumb = json_ld(page)
    assert course["@type"] == "Course" and course["url"] == f"{SITE}/courses/sample-course/"
    assert course["image"] == f"{SITE}/images/sample-course/cover.png" and course["isAccessibleForFree"] is True
    assert course["offers"]["price"] == "0"
    assert [i["item"] for i in breadcrumb["itemListElement"]] == [f"{SITE}/", f"{SITE}/courses/sample-course/"]


def test_page_without_a_published_cover_shares_the_site_icon(tmp_path):
    # "../secret.png" is refused by copy_images, so it must not be advertised either.
    write_course(tmp_path / "courses", "c", {"title": "T", "image": "../secret.png"}, CARDS, UNITS)
    out = build(tmp_path, tmp_path / "courses")
    for file in ("index.html", "courses/c/index.html"):
        page = read(out, file)
        assert f'<meta property="og:image" content="{SITE}/assets/img/icon-512.png">' in page
        assert '<meta name="twitter:card" content="summary">' in page
    course_page = read(out, "courses/c/index.html")
    assert "image" not in json_ld(course_page)[0] and "secret.png" not in course_page  # no broken <img> either
    assert (out / "assets" / "img" / "icon-512.png").is_file() and (out / "assets" / "img" / "favicon.png").is_file()


def test_index_structured_data_lists_the_site_and_every_course(tmp_path):
    site, items = json_ld(read(build(tmp_path, FIXTURE), "index.html"))
    assert site["@type"] == "WebSite" and site["url"] == f"{SITE}/"
    assert site["publisher"]["sameAs"] == [PLAY]
    assert [i["url"] for i in items["itemListElement"]] == [f"{SITE}/courses/sample-course/"]


def test_course_text_cannot_break_out_of_head_or_structured_data(tmp_path):
    evil = '"></script><script>alert(1)</script>'
    write_course(tmp_path / "courses", "c", {"title": evil, "description": evil}, CARDS, UNITS)
    out = build(tmp_path, tmp_path / "courses")
    for file in ("index.html", "courses/c/index.html"):
        assert "<script>alert(1)" not in read(out, file)
    assert json_ld(read(out, "courses/c/index.html"))[0]["name"] == evil


def test_sitemap_and_robots_cover_every_page(tmp_path):
    out = build(tmp_path, FIXTURE)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in ET.parse(out / "sitemap.xml").getroot().findall("s:url/s:loc", ns)]
    assert locs == [f"{SITE}/", f"{SITE}/courses/sample-course/", *(f"{SITE}/{p}" for p in build_site.STATIC_PAGES)]
    assert len(locs) == len(set(locs))
    robots = read(out, "robots.txt")
    assert "User-agent: *" in robots and "Disallow" not in robots
    assert f"Sitemap: {SITE}/sitemap.xml" in robots


def test_google_play_link_is_on_every_page(tmp_path):
    out = build(tmp_path, FIXTURE)
    for file in out.rglob("index.html"):
        assert f'href="{PLAY}"' in file.read_text(encoding="utf-8"), file
    for file in ("index.html", "courses/sample-course/index.html"):
        assert f'class="play-button" href="{PLAY}"' in read(out, file)
