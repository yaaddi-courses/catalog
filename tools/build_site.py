#!/usr/bin/env python3
"""Builds the static GitHub Pages site for this course repo.

Reads every course's meta.json + source/cards.csv (never the built .zip —
source/ is always the freshest, human-edited copy) and renders:

  _site/index.html               — course catalog: grid, cover images,
                                    tag filter + free-text search (all
                                    client-side, over a small prebuilt
                                    JSON blob — no runtime API calls, no
                                    per-visit re-parsing of CSVs)
  _site/courses/<slug>/index.html — one page per course: full description,
                                    deck/unit table of contents, a couple
                                    of real example cards, card-type and
                                    image-coverage stats
  _site/help/index.html          — how to install/update/study a course
  _site/contribute/index.html    — how to report issues, fix a course, or
                                    write a new one (points back at
                                    README.md/AUTHORING.md for full detail
                                    rather than duplicating them)
  _site/assets/style.css         — shared styles (system fonts only, no
                                    external font/CDN requests — keeps the
                                    site fast and dependency-free)
  _site/assets/site.js           — index page's filter/search behavior
  _site/images/<slug>/...        — cover + unit images, copied verbatim

Pure Python stdlib — no dependencies, matches validate_course.py's own
"stdlib-only" convention so this needs nothing beyond `python3` in CI.

Usage:
    python tools/build_site.py                 # writes to ./_site
    python tools/build_site.py --out /tmp/site  # custom output dir
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import guide_pages

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_TITLE = "Yaaddi Courses"
SITE_TAGLINE = "Free, open-source spaced-repetition courses — browse what's inside before you install."
GITHUB_REPO = "mohammad-reza-mahdiani/yaaddi"
# The org every individual course's own dedicated repo lives under (see
# README.md's "one repo per course" architecture) — used to link each
# course's detail page back to ITS OWN repo (to star/watch/open an issue
# on that specific course), distinct from GITHUB_REPO above (the app repo,
# used for the site nav's generic "report an issue with the app" links).
COURSES_ORG = "yaaddi-courses"

# Folders at repo root that are never course folders.
SKIP_DIRS = {
    ".git", ".github", ".internal", "__pycache__", "tools", "_site",
    "node_modules",
}


def discover_courses(root: Path) -> list[Path]:
    courses = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in SKIP_DIRS or child.name.startswith("."):
            continue
        if (child / "meta.json").exists():
            courses.append(child)
    return courses


def read_cards(course_dir: Path) -> list[dict]:
    cards_path = course_dir / "source" / "cards.csv"
    if not cards_path.exists():
        return []
    with cards_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_units(course_dir: Path) -> list[dict]:
    units_path = course_dir / "source" / "units.csv"
    if not units_path.exists():
        return []
    with units_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_course_data(course_dir: Path) -> dict:
    slug = course_dir.name
    meta = json.loads((course_dir / "meta.json").read_text(encoding="utf-8"))
    cards = read_cards(course_dir)
    units = read_units(course_dir)

    role_counts = Counter(c["role"] for c in cards)
    type_counts = Counter(c["type"] for c in cards if c["role"] != "preview")
    total_non_preview = sum(v for k, v in role_counts.items() if k != "preview")
    with_image = sum(1 for c in cards if c.get("image", "").strip())
    image_coverage_pct = round(100 * with_image / len(cards)) if cards else 0

    # A couple of real "main" cards for the course detail page's preview —
    # first 2 in file order, atomic single-concept cards by construction
    # (see AUTHORING.md), so any 2 are a fair, representative sample.
    example_cards = []
    for c in cards:
        if c["role"] == "main" and len(example_cards) < 2:
            example_cards.append({
                "type": c["type"],
                "prompt": c["prompt"],
                "options": [o for o in c.get("options", "").split("|") if o],
            })

    return {
        "slug": slug,
        # This course's own dedicated repo — one repo per course, named
        # after its folder/slug (see README.md's "one repo per course"
        # architecture; `ensure_course_ids.py`/the catalog build never
        # rename a course's folder after publishing, so this is stable).
        "repo_url": f"https://github.com/{COURSES_ORG}/{slug}",
        "id": meta.get("id", slug),
        "language": meta.get("language", ""),
        "title": meta["title"],
        "description": meta.get("description", ""),
        "image": meta.get("image", ""),
        "version": meta.get("version", ""),
        "tags": meta.get("tags", []),
        "toc": meta.get("toc", []),
        "units": [
            {"title": u["title"], "description": u["description"], "section": u.get("section", "")}
            for u in units
        ],
        "deck_count": len(units) or len(meta.get("toc", [])),
        # Main + practice cards — deliberately excludes preview cards (one
        # ungraded intro per main card, never independently studied/graded),
        # same convention the app's own Stats screen uses for its "total
        # cards" figure. Computed identically for every course via this one
        # function, so the number means the same thing everywhere — but
        # "cards" alone reads as ambiguous (could look like "main cards
        # only" to a reader who doesn't know the convention), so the
        # main/practice split is exposed separately too for the course
        # detail page to spell out explicitly instead of just one bare
        # number.
        "card_count": total_non_preview,
        "main_count": role_counts.get("main", 0),
        "practice_count": role_counts.get("exercise", 0),
        "type_counts": dict(sorted(type_counts.items(), key=lambda kv: -kv[1])),
        "image_coverage_pct": image_coverage_pct,
        "example_cards": example_cards,
        "changelog": meta.get("changelog", []),
    }


# ---------------------------------------------------------------------------
# Rendering — plain f-string templates, no template engine dependency.
# ---------------------------------------------------------------------------

def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


# Arabic-script letters (Farsi, Arabic, Urdu) and Hebrew.
RTL_SCRIPT_RE = re.compile("[֐-ࣿיִ-﷿ﹰ-ﻼ]")


def text_attrs(text: str, language: str = "") -> str:
    """Attributes for an element holding course text: dir="auto" so a Farsi title or card
    reads right-to-left, plus lang when the text is in the course's RTL script. meta.json's
    `language` is the learner's language, so an English title in a Farsi-speakers' course
    gets no lang (the page itself is lang="en")."""
    attrs = ' dir="auto"'
    if language and RTL_SCRIPT_RE.search(str(text)):
        attrs += f' lang="{esc(language)}"'
    return attrs


def script_json(data) -> str:
    """JSON safe to embed inside <script>: "<", ">" and "&" are escaped so course text from
    an external repo can never close the tag ("</script>") or open a comment ("<!--").
    json.dumps already escapes U+2028/U+2029 (ensure_ascii)."""
    return (
        json.dumps(data)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def render_tag_chips(tags: list[str]) -> str:
    return "".join(f'<span class="chip">{esc(t)}</span>' for t in tags)


def render_type_bar(type_counts: dict[str, int]) -> str:
    total = sum(type_counts.values()) or 1
    segments = []
    for t, n in type_counts.items():
        pct = 100 * n / total
        segments.append(
            f'<span class="type-seg" style="width:{pct:.2f}%" title="{esc(t)}: {n} cards"></span>'
        )
    return "".join(segments)


def render_card_preview(card: dict, language: str = "") -> str:
    opts_html = ""
    if card["options"]:
        items = "".join(f"<li{text_attrs(o, language)}>{esc(o)}</li>" for o in card["options"][:4])
        opts_html = f'<ul class="preview-options">{items}</ul>'
    return f'''<div class="card-preview">
      <span class="card-type-badge">{esc(card["type"].replace("_", " "))}</span>
      <p class="card-prompt"{text_attrs(card["prompt"], language)}>{esc(card["prompt"])}</p>
      {opts_html}
    </div>'''


PAGE_HEAD = """<!doctype html>
<html lang="en" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="icon" href="data:,">
<link rel="stylesheet" href="{asset_prefix}assets/style.css">
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
"""

PAGE_TAIL = """
<footer class="site-footer">
  <p>Open-source course content for <strong>Yaaddi</strong> — a free spaced-repetition
  learning app. <a href="https://github.com/{repo}">View on GitHub</a></p>
</footer>
</body>
</html>
"""

NAV = """<header class="site-header">
  <a class="brand" href="{root_prefix}index.html">Yaaddi Courses</a>
  <nav class="header-nav">
    <a class="header-link" href="{root_prefix}guide/index.html">Guide</a>
    <a class="header-link" href="{root_prefix}faq/index.html">FAQ</a>
    <a class="header-link" href="{root_prefix}help/index.html">Help</a>
    <a class="header-link" href="{root_prefix}contribute/index.html">Contribute</a>
    <a class="header-link" href="{root_prefix}privacy/index.html">Privacy</a>
    <a class="header-link" href="{root_prefix}terms/index.html">Terms</a>
    <a class="header-link" href="https://github.com/{repo}">GitHub</a>
  </nav>
</header>
"""


def plural(n: int, word: str) -> str:
    """"deck" for 1, "decks" otherwise (site.js has the same rule for client-rendered cards)."""
    return word if n == 1 else word + "s"


def render_course_card_html(c: dict) -> str:
    cover = f'images/{c["slug"]}/{Path(c["image"]).name}' if c["image"] else ""
    cover_html = (
        f'<img class="cover" src="{esc(cover)}" alt="" loading="lazy">' if cover else '<div class="cover cover-empty"></div>'
    )
    return f'''
        <a class="course-card" href="courses/{esc(c["slug"])}/index.html"
           data-tags="{esc(' '.join(c["tags"]))}" data-title="{esc(c["title"].lower())}"
           data-desc="{esc(c["description"].lower())}">
          {cover_html}
          <div class="course-card-body">
            <h3{text_attrs(c["title"], c["language"])}>{esc(c["title"])}</h3>
            <p class="course-desc"{text_attrs(c["description"], c["language"])}>{esc(c["description"])}</p>
            <div class="tag-row">{render_tag_chips(c["tags"])}</div>
            <div class="course-stats">
              <span>{c["deck_count"]} {plural(c["deck_count"], "deck")}</span>
              <span>&middot;</span>
              <span title="{c["main_count"]} main + {c["practice_count"]} practice — one-time intro preview cards not counted">{c["card_count"]} {plural(c["card_count"], "card")}</span>
            </div>
          </div>
        </a>'''


# How many course cards are rendered directly into index.html's initial
# HTML — fast first paint (and a fully working page with JS disabled, since
# these are real <a> links, not client-rendered-only) without the whole
# catalog's markup ever hitting the wire at once. site.js progressively
# renders the rest (scroll-triggered, or immediately on a search/filter)
# from `window.__COURSES__` below, which is why that blob carries every
# field a card actually needs to render, not just slug/title/tags — a
# catalog of thousands of courses would otherwise mean an index.html many
# megabytes in size, almost all of it never seen because the visible
# viewport only ever shows a couple dozen cards at once.
INITIAL_RENDERED_COURSES = 60


def render_index(courses: list[dict], out_dir: Path) -> None:
    cards_html = [render_course_card_html(c) for c in courses[:INITIAL_RENDERED_COURSES]]

    all_tags = sorted({t for c in courses for t in c["tags"]})
    tag_buttons = "".join(
        f'<button class="tag-filter" data-tag="{esc(t)}" aria-pressed="false">{esc(t)}</button>' for t in all_tags
    )

    data_json = script_json(
        [
            {
                "slug": c["slug"],
                "title": c["title"],
                "description": c["description"],
                "tags": c["tags"],
                "image": f'images/{c["slug"]}/{Path(c["image"]).name}' if c["image"] else "",
                "deckCount": c["deck_count"],
                "cardCount": c["card_count"],
            }
            for c in courses
        ]
    )

    body = f'''{NAV.format(root_prefix="", repo=GITHUB_REPO)}
<main class="index-main" id="main">
  <section class="hero">
    <h1>{esc(SITE_TITLE)}</h1>
    <p class="tagline">{esc(SITE_TAGLINE)}</p>
    <div class="search-row">
      <input id="search" type="search" placeholder="Search courses..." aria-label="Search courses">
    </div>
    <div class="tag-filter-row" id="tag-filters">
      <button class="tag-filter active" data-tag="" aria-pressed="true">All</button>
      {tag_buttons}
    </div>
  </section>
  <h2 class="sr-only">Courses</h2>
  <section class="course-grid" id="course-grid">
    {"".join(cards_html)}
  </section>
  <div id="load-sentinel" aria-hidden="true"></div>
  <p class="no-results" id="no-results" hidden>No courses match your search.</p>
  <p class="sr-only" id="results-status" role="status"></p>
</main>
<script>window.__COURSES__ = {data_json};</script>
<script src="assets/site.js"></script>
{PAGE_TAIL.format(repo=GITHUB_REPO)}'''

    out_dir.joinpath("index.html").write_text(
        PAGE_HEAD.format(
            title=esc(SITE_TITLE),
            description=esc(SITE_TAGLINE),
            asset_prefix="",
        ) + body,
        encoding="utf-8",
    )


def render_course_page(course: dict, out_dir: Path) -> None:
    page_dir = out_dir / "courses" / course["slug"]
    page_dir.mkdir(parents=True, exist_ok=True)

    cover = f'../../images/{course["slug"]}/{Path(course["image"]).name}' if course["image"] else ""
    cover_html = f'<img class="cover-large" src="{esc(cover)}" alt="">' if cover else ""

    lang = course["language"]
    toc_items = "".join(f"<li{text_attrs(t, lang)}>{esc(t)}</li>" for t in course["toc"])
    if not toc_items and course["units"]:
        toc_items = "".join(f"<li{text_attrs(u['title'], lang)}>{esc(u['title'])}</li>" for u in course["units"])

    examples_html = "".join(render_card_preview(c, lang) for c in course["example_cards"])

    latest_note = ""
    if course["changelog"]:
        latest_note = esc(course["changelog"][-1].get("notes", ""))

    body = f'''{NAV.format(root_prefix="../../", repo=GITHUB_REPO)}
<main class="course-main" id="main">
  <a class="back-link" href="../../index.html">&larr; All courses</a>
  <div class="course-hero">
    {cover_html}
    <div class="course-hero-body">
      <h1{text_attrs(course["title"], lang)}>{esc(course["title"])}</h1>
      <p class="course-desc-large"{text_attrs(course["description"], lang)}>{esc(course["description"])}</p>
      <div class="tag-row">{render_tag_chips(course["tags"])}</div>
      <p class="course-repo-link"><a href="{esc(course["repo_url"])}" target="_blank" rel="noopener">
        View this course's repo on GitHub &rarr;</a> — star it, open an issue, or suggest a fix.</p>
      <div class="course-stats-row">
        <div class="stat"><strong>{course["deck_count"]}</strong><span>{plural(course["deck_count"], "deck")}</span></div>
        <div class="stat"><strong>{course["main_count"]}</strong><span>main {plural(course["main_count"], "card")}</span></div>
        <div class="stat"><strong>{course["practice_count"]}</strong><span>practice {plural(course["practice_count"], "card")}</span></div>
        <div class="stat"><strong>{course["image_coverage_pct"]}%</strong><span>with images</span></div>
        <div class="stat"><strong>v{esc(course["version"])}</strong><span>version</span></div>
      </div>
    </div>
  </div>

  <section class="section">
    <h2>Card type mix</h2>
    <div class="type-bar" aria-hidden="true">{render_type_bar(course["type_counts"])}</div>
    <ul class="type-legend">
      {"".join(f'<li>{esc(t.replace("_"," "))}: {n}</li>' for t, n in course["type_counts"].items())}
    </ul>
  </section>

  <section class="section">
    <h2>What's covered</h2>
    <ol class="toc-list">{toc_items}</ol>
  </section>

  {"<section class='section'><h2>Example cards</h2><div class='examples'>" + examples_html + "</div></section>" if examples_html else ""}

  {f"<section class='section'><p class='changelog-note' dir='auto'>Latest: {latest_note}</p></section>" if latest_note else ""}
</main>
{PAGE_TAIL.format(repo=GITHUB_REPO)}'''

    page_dir.joinpath("index.html").write_text(
        PAGE_HEAD.format(
            title=esc(f'{course["title"]} — Yaaddi Courses'),
            description=esc(course["description"]),
            asset_prefix="../../",
        ) + body,
        encoding="utf-8",
    )


def render_static_page(*, slug: str, nav_title: str, page_title: str, intro: str, sections_html: str, out_dir: Path) -> None:
    """Renders a one-off content page (Help, Contribute) one level below the
    site root — same NAV/PAGE_HEAD/PAGE_TAIL scaffolding as a course page,
    just without any course data."""
    page_dir = out_dir / slug
    page_dir.mkdir(parents=True, exist_ok=True)

    body = f'''{NAV.format(root_prefix="../", repo=GITHUB_REPO)}
<main class="content-main" id="main">
  <a class="back-link" href="../index.html">&larr; All courses</a>
  <h1>{esc(nav_title)}</h1>
  <p class="content-intro">{intro}</p>
  {sections_html}
</main>
{PAGE_TAIL.format(repo=GITHUB_REPO)}'''

    page_dir.joinpath("index.html").write_text(
        PAGE_HEAD.format(title=esc(page_title), description=esc(intro), asset_prefix="../") + body,
        encoding="utf-8",
    )


PRIVACY_UPDATED = "October 30, 2026"
TERMS_UPDATED = "October 8, 2026"  # the terms text did not change with the privacy rewrite

# Layout "B — at a glance" (owner-approved 2026-10-01): hero, four summary
# cards, a table of what the app can use and when, then collapsible details.
# Keep this in step with the app repo's docs/PRIVACY_POLICY.md and
# docs/STORE_COMPLIANCE.md (the Play/App Store forms must match this text).
PRIVACY_CARDS = [
    ("&#128274;", "On-device only", "Courses, progress and settings never leave your phone."),
    ("&#128208;", "Only what's needed", "The app uses only what the features you turn on require."),
    ("&#128218;", "Public courses", "The Course Library downloads public course files from GitHub."),
    ("&#128465;&#65039;", "You&rsquo;re in control", "Uninstall the app and everything is gone."),
]

PRIVACY_FEATURES = [
    ("Course Library", "needs internet", "You open it, or open an installed course (at most once a day per course)",
     "Downloads public course files from GitHub and checks whether an installed course has a newer version. GitHub sees your IP address, under <a href=\"https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement\">its own privacy statement</a>."),
    ("App updates", "Android, needs internet", "The app starts",
     "Asks Google Play whether a newer version of Yaaddi exists. This only works for an app installed from Google Play, and Google Play handles the request under Google&rsquo;s own privacy policy."),
    ("Photos", "optional", "You pick a cover image",
     "Only the picture you choose is read; a copy stays on your device."),
    ("Files", "optional", "You import a course, audio file or backup",
     "Only the file you choose is read. Backups and exports are saved or shared only where you decide."),
    ("Notifications", "optional", "You turn on study reminders",
     "Reminders are scheduled on your phone; nothing is sent to a server."),
    ("Sharing and support", "optional", "You share progress or report a problem",
     "The app opens your phone&rsquo;s share sheet or email app with a prepared message. Nothing is sent until you send it yourself."),
]

PRIVACY_DETAILS = [
    ("Where is my data stored?",
     "In a private database on your device: courses, cards, review history, streaks, Coins, settings and any cover images or audio you add. It is never sent to us. We have no accounts, no advertising and no analytics or crash-reporting tools, and the app does not read advertising IDs or other device identifiers. A backup file is created only if you choose <em>Backup &amp; restore</em>, and you decide where it goes; it contains your courses and progress, so keep it as private as you would any personal file. Android&rsquo;s automatic cloud backup is turned off for this app."),
    ("What information do you collect?",
     "None. Your learning data stays on your phone and the app does not send anything about you to us. The only network requests the app makes are the ones listed under &ldquo;Who else receives data?&rdquo; and, if a course you imported points to a picture on a web address, a request for that picture to that site. The app&rsquo;s own requests to GitHub and Google Play use HTTPS."),
    ("Who else receives data?",
     "GitHub (the Course Library and course update checks): it sees your IP address and which public course files you request, like any website. Google Play (Android app update check): it handles the request under Google&rsquo;s privacy policy. The apps you choose when you share or send an email (for example your email or messaging app): they receive only what you send and handle it under their own policies. Your phone&rsquo;s text-to-speech engine reads cards aloud on your device; the app sends it only the card text, and the engine is governed by your phone maker or Google. We do not sell or share your data for advertising."),
    ("What do &ldquo;Report a problem&rdquo; and sharing send?",
     "&ldquo;Report a problem&rdquo; opens your email app with a message to <a href=\"mailto:support@yaaddi.com\">support@yaaddi.com</a>. It includes your note, the reason, the course name and version, the card&rsquo;s ID, type and a short excerpt of its text, and the app version and platform. You see the whole message and decide whether to send it. If you send it, we receive that text and your email address, and we use them only to fix the card and reply. Sharing your progress hands a picture of your progress and a link to the app to the app you choose."),
    ("How do I delete everything?",
     "Uninstall the app, or clear its storage in your phone&rsquo;s settings. Everything is stored only on your phone and we hold no copy, so there is nothing else to delete. Backup files and shared pictures you saved elsewhere are copies you control and must delete yourself. If you emailed us a report and want it deleted, write to <a href=\"mailto:support@yaaddi.com\">support@yaaddi.com</a>. Because we hold no personal data about you, there is nothing for us to export or correct."),
    ("Is it safe for children?",
     "Yaaddi is not directed at children under 13 and does not knowingly collect personal information from anyone, of any age."),
    ("Who owns the course content?",
     "Courses in the Course Library are community-authored and openly licensed &mdash; see this catalog&rsquo;s GitHub repository for the content and its license. This policy covers how the app handles your data, not course licensing."),
    ("Will this policy change?",
     "If it does, the date at the top of this page changes. Yaaddi is made by Mohammad Reza Mahdiani. Questions: <a href=\"mailto:support@yaaddi.com\">support@yaaddi.com</a>."),
]


def render_legal_hero(title: str, lead: str, cards: list[tuple[str, str, str]], updated: str) -> str:
    """Hero plus summary cards shared by the Privacy and Terms pages (one design for both)."""
    card_html = "\n".join(
        f'    <div class="privacy-card"><div class="privacy-card-icon" aria-hidden="true">{icon}</div>'
        f"<strong>{card_title}</strong><span>{text}</span></div>"
        for icon, card_title, text in cards
    )
    return f"""<div class="privacy-hero">
  <h1>{title}</h1>
  <p>{lead}</p>
  <p class="privacy-updated">Last updated: {updated}</p>
</div>
<div class="privacy-cards">
{card_html}
</div>"""


def render_legal_details(items: list[tuple[str, str]], *, numbered: bool = False) -> str:
    return "\n".join(
        f'    <details class="privacy-details"><summary>{f"{i}. " if numbered else ""}{q}</summary><p>{a}</p></details>'
        for i, (q, a) in enumerate(items, 1)
    )


def render_privacy_page(out_dir: Path) -> None:
    rows = "\n".join(
        f'      <tr><td><strong>{feature}</strong> <span class="privacy-pill">{pill}</span></td>'
        f"<td>{when}</td><td>{what}</td></tr>"
        for feature, pill, when, what in PRIVACY_FEATURES
    )
    hero = render_legal_hero(
        "Your data stays on your phone",
        "Here is exactly what the app does with your information.",
        PRIVACY_CARDS,
        PRIVACY_UPDATED,
    )
    details = render_legal_details(PRIVACY_DETAILS)
    body = f'''{NAV.format(root_prefix="../", repo=GITHUB_REPO)}
{hero}
<main class="privacy-main" id="main">
  <h2>What the app can use</h2>
  <div class="privacy-table-wrap">
    <table class="privacy-table">
      <thead><tr><th>Feature</th><th>When</th><th>What happens</th></tr></thead>
      <tbody>
{rows}
      </tbody>
    </table>
  </div>
  <h2>The details</h2>
{details}
</main>
{PAGE_TAIL.format(repo=GITHUB_REPO)}'''
    page_dir = out_dir / "privacy"
    page_dir.mkdir(parents=True, exist_ok=True)
    intro = "Your learning data stays on your device. Here is exactly what the app does with your information."
    page_dir.joinpath("index.html").write_text(
        PAGE_HEAD.format(title="Privacy Policy — Yaaddi", description=esc(intro), asset_prefix="../") + body,
        encoding="utf-8",
    )


# Same "at a glance" layout as the privacy page. Keep in step with the app's
# terms.json (en); test_build_site_privacy.py guards the two against drifting apart.
TERMS_CARDS = [
    ("&#128218;", "A study aid", "Courses help you learn; they are not professional advice."),
    ("&#9989;", "Check official sources", "Confirm anything important before a decision or an exam."),
    ("&#129517;", "Your decisions", "You choose how to use the content and are responsible for it."),
    ("&#9993;&#65039;", "Found a mistake?", "Tell us and we will fix it in a later version."),
]

TERMS_SECTIONS = [
    ("Educational use only", "Yaaddi and its courses are study aids. They are provided for general education and are not legal, immigration, medical, financial, tax, investment, driving-test or other professional advice, and they are not an official source for any test or licence."),
    ("Accuracy and changes", "Course content is written with care from public sources and reviewed, but it may contain mistakes or become out of date (for example laws, tax figures, test formats and the names of office holders change). Always check the official source (the government agency, test provider or a qualified professional) before you rely on anything for a decision or an exam."),
    ("Your responsibility", "You decide how to use the content. To the extent the law allows, you are responsible for checking it and for your decisions, and Yaaddi and its developer are not liable for loss or damage that results from relying on course content, including failing a test or exam. Nothing in these terms excludes liability that cannot be excluded by law (for example for fraud, or rights you have as a consumer)."),
    ("Courses and third-party content", "Courses are provided &ldquo;as is&rdquo; and &ldquo;as available&rdquo; without any warranty of accuracy or fitness for a particular purpose. Links and images come from third parties under their own licences; see the ATTRIBUTIONS.md of any course that has one. Yaaddi is not affiliated with any government body or test provider named in a course."),
    ("Reporting errors", 'If you find a mistake, use &ldquo;Report a problem&rdquo; in the app or write to <a href="mailto:support@yaaddi.com">support@yaaddi.com</a>. We will correct confirmed errors in a later course version.'),
    ("Changes and contact", 'We may update these terms; the &ldquo;last updated&rdquo; date above changes when we do. Contact: <a href="mailto:support@yaaddi.com">support@yaaddi.com</a>.'),
]


def render_terms_page(out_dir: Path) -> None:
    hero = render_legal_hero(
        "Terms of use and content disclaimer",
        "Yaaddi is a study aid. Here is what that means for you.",
        TERMS_CARDS,
        TERMS_UPDATED,
    )
    body = f'''{NAV.format(root_prefix="../", repo=GITHUB_REPO)}
{hero}
<main class="privacy-main" id="main">
  <h2>The details</h2>
{render_legal_details(TERMS_SECTIONS, numbered=True)}
</main>
{PAGE_TAIL.format(repo=GITHUB_REPO)}'''
    page_dir = out_dir / "terms"
    page_dir.mkdir(parents=True, exist_ok=True)
    page_dir.joinpath("index.html").write_text(
        PAGE_HEAD.format(title="Terms of Use — Yaaddi", description=esc("Yaaddi courses are study aids, not professional advice."), asset_prefix="../") + body,
        encoding="utf-8",
    )


def render_help_page(out_dir: Path) -> None:
    sections = f'''
  <section class="section">
    <h2>What is Yaaddi?</h2>
    <p>Yaaddi is a free spaced-repetition learning app. You install courses
    from this catalog inside the app's own <strong>Course Library</strong>
    screen — this website is just a preview, so you can see what's inside a
    course before you commit to it. Installing itself always happens
    in-app, never from this site.</p>
  </section>

  <section class="section">
    <h2>Installing a course</h2>
    <ol class="help-steps">
      <li>Open Yaaddi and go to <strong>Course Library</strong> from the Learn tab.</li>
      <li>Browse or search for a course — the same list shown on this site.</li>
      <li>Tap <strong>Install</strong>. The course, its cover image, and every
      card/deck download straight from the course's own GitHub repo.</li>
      <li>Study it like any other deck — spaced repetition schedules your
      reviews automatically.</li>
    </ol>
  </section>

  <section class="section">
    <h2>Updating an installed course</h2>
    <p>From Course Library, tap <strong>Check for updates</strong>. If a
    course you've installed has a newer version, you can apply it in one
    tap — new or changed cards come in, and your review progress on
    anything unchanged is kept. If an update would remove cards you've
    already studied, the app warns you before applying it.</p>
  </section>

  <section class="section">
    <h2>Found a mistake in a course?</h2>
    <p>Every course lives in its own open-source repo under the
    <a href="https://github.com/{COURSES_ORG}">{COURSES_ORG}</a> GitHub
    organization — each course's page here links to it. See
    <a href="../contribute/index.html">how to participate</a> for how to
    report or fix it.</p>
  </section>
'''
    render_static_page(
        slug="help",
        nav_title="Help",
        page_title="Help — Yaaddi Courses",
        intro="How to install, study, and update courses from this catalog.",
        sections_html=sections,
        out_dir=out_dir,
    )


def render_guide_pages(out_dir: Path) -> None:
    """User guide, FAQ and What's New (content in guide_pages.py, screenshots in site_assets/img/guide)."""
    for slug, nav_title, intro, sections in (
        ("guide", "User guide", "How to study with Yaaddi, step by step.", guide_pages.render_guide_sections()),
        ("faq", "Frequently asked questions", "Quick answers about using Yaaddi.", guide_pages.render_faq_sections()),
        ("whats-new", "What's new", "Changes in each version of the app.", guide_pages.render_whats_new_sections()),
    ):
        render_static_page(
            slug=slug, nav_title=nav_title, page_title=f"{nav_title} — Yaaddi",
            intro=intro, sections_html=sections, out_dir=out_dir,
        )


def render_contribute_page(out_dir: Path) -> None:
    sections = f'''
  <section class="section">
    <h2>Ways to help</h2>
    <ul class="help-steps">
      <li><strong>Report a problem in a course</strong> — wrong information,
      a typo, a confusing card — open an issue on that course's own repo
      (linked from its page on this site). For a problem with the app itself,
      <a href="https://github.com/{esc(GITHUB_REPO)}/issues">open an issue here</a>.</li>
      <li><strong>Fix or improve a course</strong> — edit the
      <code>source/*.csv</code> files in that course's repo and open a pull
      request against it.</li>
      <li><strong>Write a new course</strong> — see the walkthrough below.</li>
    </ul>
  </section>

  <section class="section">
    <h2>Writing a new course</h2>
    <p>Every course is its own repo under the
    <a href="https://github.com/{COURSES_ORG}">{COURSES_ORG}</a> organization.</p>
    <ol class="help-steps">
      <li>Click <strong>Use this template</strong> on
      <a href="https://github.com/{COURSES_ORG}/course-template">{COURSES_ORG}/course-template</a>
      to create the new course repo.</li>
      <li>Follow that repo's README and
      <a href="https://github.com/{COURSES_ORG}/course-template/blob/main/AUTHORING.md">AUTHORING.md</a>
      — deck structure, card-type variety, how many practice cards per
      concept, <code>meta.json</code> fields, and more.</li>
      <li>In the repo, run the validator:
      <code>python validate_course.py . --source</code> — it catches dangling
      references, missing media, unknown card types, and more. Then build the
      zip: <code>python build_course_zip.py .</code></li>
      <li>The repo's own workflow runs the same validator on every pull
      request and push.</li>
      <li>Once it is merged to <code>main</code>, add the
      <code>yaaddi-course</code> topic to the repo. The catalog picks it up on
      its next scheduled rebuild (every 6 hours) — no pull request against the
      catalog is needed.</li>
    </ol>
  </section>

  <section class="section">
    <h2>License</h2>
    <p>Course content is licensed under
    <a href="https://github.com/{COURSES_ORG}/course-template/blob/main/LICENSE">PolyForm Noncommercial 1.0.0</a>
    — each course repo carries its own <code>LICENSE</code>. If you're
    contributing a course built from a source with its own license, say so
    in that course's own repo rather than assuming.</p>
  </section>
'''
    render_static_page(
        slug="contribute",
        nav_title="How to Participate",
        page_title="Contribute — Yaaddi Courses",
        intro="Report problems, improve existing courses, or write a new one.",
        sections_html=sections,
        out_dir=out_dir,
    )


def copy_assets(root: Path, out_dir: Path) -> None:
    assets_src = root / "tools" / "site_assets"
    assets_dst = out_dir / "assets"
    shutil.copytree(assets_src, assets_dst, dirs_exist_ok=True)


# SVG is left out on purpose: opened directly from the site, it could run script.
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def copy_images(course_dir: Path, course: dict, out_dir: Path) -> None:
    dst = out_dir / "images" / course["slug"]
    dst.mkdir(parents=True, exist_ok=True)
    if course["image"]:
        src = course_dir / course["image"]
        # meta.json comes from an external repo: publish only a real image file that lives
        # inside the course folder (no "../", no symlink pointing elsewhere).
        if (
            src.suffix.lower() not in IMAGE_SUFFIXES
            or src.is_symlink()
            or not src.resolve().is_relative_to(course_dir.resolve())
            or not src.is_file()
        ):
            if src.exists() or src.is_symlink():
                print(f"warning: {course['slug']}: cover {course['image']!r} not published (not an image inside the course)", file=sys.stderr)
            return
        shutil.copy2(src, dst / Path(course["image"]).name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "_site"), help="Output directory")
    parser.add_argument(
        "--courses-dir",
        default=str(REPO_ROOT),
        help=(
            "Directory to scan for course subfolders (default: this repo's own "
            "root, for local/legacy use). In the one-repo-per-course world, the "
            "workflow that runs this shallow-clones every yaaddi-course-tagged "
            "repo into a scratch directory first and points this flag at that "
            "directory instead — site_assets/tools still come from this repo's "
            "own root regardless (see copy_assets(REPO_ROOT, ...) below), only "
            "course discovery is redirected."
        ),
    )
    args = parser.parse_args()
    out_dir = Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    course_dirs = discover_courses(Path(args.courses_dir))
    courses = []
    for course_dir in course_dirs:
        # One malformed course repo (bad meta.json, a CSV missing a column) must not take the
        # whole site down: warn (shown as an annotation in GitHub Actions) and build the rest.
        try:
            data = build_course_data(course_dir)
            copy_images(course_dir, data, out_dir)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
            print(f"::warning::{course_dir.name}: skipped, cannot be built ({type(err).__name__}: {err})", file=sys.stderr)
            continue
        courses.append(data)
    if not courses:
        raise SystemExit(f"no course could be built from {args.courses_dir}; refusing to publish an empty site")

    courses.sort(key=lambda c: c["title"].lower())

    copy_assets(REPO_ROOT, out_dir)
    render_index(courses, out_dir)
    for course in courses:
        render_course_page(course, out_dir)
    render_help_page(out_dir)
    render_guide_pages(out_dir)
    render_contribute_page(out_dir)
    render_privacy_page(out_dir)
    render_terms_page(out_dir)

    print(f"Built {len(courses)} course page(s) into {out_dir}")


if __name__ == "__main__":
    main()
