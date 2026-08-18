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
import shutil
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_TITLE = "Yaaddi Courses"
SITE_TAGLINE = "Free, open-source spaced-repetition courses — browse what's inside before you install."
GITHUB_REPO = "mohammad-reza-mahdiani/yaaddi"
# Matches the app's own Help screen (src/screens/HelpScreen.tsx's
# AUTHOR_NAME/AUTHOR_LINKS) — kept in sync manually since this is a
# separate repo/build with no shared import between them.
AUTHOR_NAME = "Mohammad Reza Mahdiani"
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/mohammad-reza-mahdiani/"
AUTHOR_YOUTUBE = "https://www.youtube.com/channel/UCYWh8QADJmCVE3gdjcIGbPA"

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
        "id": meta.get("id", slug),
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


def render_card_preview(card: dict) -> str:
    opts_html = ""
    if card["options"]:
        items = "".join(f"<li>{esc(o)}</li>" for o in card["options"][:4])
        opts_html = f'<ul class="preview-options">{items}</ul>'
    return f'''<div class="card-preview">
      <span class="card-type-badge">{esc(card["type"].replace("_", " "))}</span>
      <p class="card-prompt">{esc(card["prompt"])}</p>
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
"""

PAGE_TAIL = f"""
<footer class="site-footer">
  <p>Open-source course content for <strong>Yaaddi</strong> — a free spaced-repetition
  learning app. <a href="https://github.com/{{repo}}">View on GitHub</a></p>
  <p class="footer-credit">Made by {AUTHOR_NAME} —
  <a href="{AUTHOR_LINKEDIN}">LinkedIn</a> &middot;
  <a href="{AUTHOR_YOUTUBE}">YouTube</a></p>
</footer>
</body>
</html>
"""

NAV = """<header class="site-header">
  <a class="brand" href="{root_prefix}index.html">Yaaddi Courses</a>
  <nav class="header-nav">
    <a class="header-link" href="{root_prefix}help/index.html">Help</a>
    <a class="header-link" href="{root_prefix}contribute/index.html">Contribute</a>
    <a class="header-link" href="https://github.com/{repo}">GitHub</a>
  </nav>
</header>
"""


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
            <h3>{esc(c["title"])}</h3>
            <p class="course-desc">{esc(c["description"])}</p>
            <div class="tag-row">{render_tag_chips(c["tags"])}</div>
            <div class="course-stats">
              <span>{c["deck_count"]} decks</span>
              <span>&middot;</span>
              <span title="{c["main_count"]} main + {c["practice_count"]} practice — one-time intro preview cards not counted">{c["card_count"]} cards</span>
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
        f'<button class="tag-filter" data-tag="{esc(t)}">{esc(t)}</button>' for t in all_tags
    )

    data_json = json.dumps(
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
<main class="index-main">
  <section class="hero">
    <h1>{esc(SITE_TITLE)}</h1>
    <p class="tagline">{esc(SITE_TAGLINE)}</p>
    <div class="search-row">
      <input id="search" type="search" placeholder="Search courses..." aria-label="Search courses">
    </div>
    <div class="tag-filter-row" id="tag-filters">
      <button class="tag-filter active" data-tag="">All</button>
      {tag_buttons}
    </div>
  </section>
  <section class="course-grid" id="course-grid">
    {"".join(cards_html)}
  </section>
  <div id="load-sentinel" aria-hidden="true"></div>
  <p class="no-results" id="no-results" hidden>No courses match your search.</p>
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

    toc_items = "".join(f"<li>{esc(t)}</li>" for t in course["toc"])
    if not toc_items and course["units"]:
        toc_items = "".join(f"<li>{esc(u['title'])}</li>" for u in course["units"])

    examples_html = "".join(render_card_preview(c) for c in course["example_cards"])

    latest_note = ""
    if course["changelog"]:
        latest_note = esc(course["changelog"][-1].get("notes", ""))

    body = f'''{NAV.format(root_prefix="../../", repo=GITHUB_REPO)}
<main class="course-main">
  <a class="back-link" href="../../index.html">&larr; All courses</a>
  <div class="course-hero">
    {cover_html}
    <div class="course-hero-body">
      <h1>{esc(course["title"])}</h1>
      <p class="course-desc-large">{esc(course["description"])}</p>
      <div class="tag-row">{render_tag_chips(course["tags"])}</div>
      <div class="course-stats-row">
        <div class="stat"><strong>{course["deck_count"]}</strong><span>decks</span></div>
        <div class="stat"><strong>{course["main_count"]}</strong><span>main cards</span></div>
        <div class="stat"><strong>{course["practice_count"]}</strong><span>practice cards</span></div>
        <div class="stat"><strong>{course["image_coverage_pct"]}%</strong><span>with images</span></div>
        <div class="stat"><strong>v{esc(course["version"])}</strong><span>version</span></div>
      </div>
    </div>
  </div>

  <section class="section">
    <h2>Card type mix</h2>
    <div class="type-bar">{render_type_bar(course["type_counts"])}</div>
    <ul class="type-legend">
      {"".join(f'<li>{esc(t.replace("_"," "))}: {n}</li>' for t, n in course["type_counts"].items())}
    </ul>
  </section>

  <section class="section">
    <h2>What's covered</h2>
    <ol class="toc-list">{toc_items}</ol>
  </section>

  {"<section class='section'><h2>Example cards</h2><div class='examples'>" + examples_html + "</div></section>" if examples_html else ""}

  {f"<section class='section'><p class='changelog-note'>Latest: {latest_note}</p></section>" if latest_note else ""}
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
<main class="content-main">
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
      card/deck download straight from this repo.</li>
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
    <p>Course content lives in this same open-source repo — see
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


def render_contribute_page(out_dir: Path) -> None:
    sections = f'''
  <section class="section">
    <h2>Ways to help</h2>
    <ul class="help-steps">
      <li><strong>Report a problem</strong> — wrong information, a typo, a
      confusing card — <a href="https://github.com/{esc(GITHUB_REPO)}/issues">open an issue</a>.</li>
      <li><strong>Fix or improve a course</strong> — edit its
      <code>source/*.csv</code> files and open a pull request.</li>
      <li><strong>Write a new course</strong> — see the walkthrough below.</li>
    </ul>
  </section>

  <section class="section">
    <h2>Writing a new course</h2>
    <ol class="help-steps">
      <li>Create <code>&lt;name&gt;/source/</code> with <code>meta.csv</code>,
      <code>units.csv</code>, <code>cards.csv</code>, and any images/audio
      they reference.</li>
      <li>Read <a href="https://github.com/{esc(GITHUB_REPO)}/blob/main/AUTHORING.md">AUTHORING.md</a>
      for this project's content guidelines — deck structure, card-type
      variety, how many practice cards per concept, and more.</li>
      <li>Add a cover image and a <code>meta.json</code> — see
      <a href="https://github.com/{esc(GITHUB_REPO)}/blob/main/README.md#metajson">README.md</a>
      for every field.</li>
      <li>Run the validator: <code>python validate_course.py &lt;name&gt; --source</code>
      — it catches dangling references, missing media, unknown card types,
      and more before you open a PR.</li>
      <li>Build the zip: <code>python build_course_zip.py &lt;name&gt;</code>,
      then open a pull request.</li>
    </ol>
    <p>The <code>validate-courses</code> GitHub Action runs the same checks
    automatically on every PR.</p>
  </section>

  <section class="section">
    <h2>License</h2>
    <p>Course content in this repo is licensed under
    <a href="https://github.com/{esc(GITHUB_REPO)}/blob/main/LICENSE">PolyForm Noncommercial 1.0.0</a>.
    If you're contributing a course built from a source with its own
    license, say so in that course's own folder rather than assuming.</p>
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


def copy_images(course_dir: Path, course: dict, out_dir: Path) -> None:
    dst = out_dir / "images" / course["slug"]
    dst.mkdir(parents=True, exist_ok=True)
    if course["image"]:
        src = course_dir / course["image"]
        if src.exists():
            shutil.copy2(src, dst / Path(course["image"]).name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "_site"), help="Output directory")
    args = parser.parse_args()
    out_dir = Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    course_dirs = discover_courses(REPO_ROOT)
    courses = []
    for course_dir in course_dirs:
        data = build_course_data(course_dir)
        courses.append(data)
        copy_images(course_dir, data, out_dir)

    courses.sort(key=lambda c: c["title"].lower())

    copy_assets(REPO_ROOT, out_dir)
    render_index(courses, out_dir)
    for course in courses:
        render_course_page(course, out_dir)
    render_help_page(out_dir)
    render_contribute_page(out_dir)

    print(f"Built {len(courses)} course page(s) into {out_dir}")


if __name__ == "__main__":
    main()
