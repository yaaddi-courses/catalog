"""Content and HTML for the user guide, FAQ and What's New pages (English only).

build_site.py renders these through its own render_static_page. Screenshots are
described once, in tools/guide/guide_shots.json (file + alt text), and the version
stamp lives in tools/guide_version.json; the release skill updates both.
"""
from __future__ import annotations

import json
import struct
from html import escape as esc
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMG_DIR = HERE / "site_assets" / "img" / "guide"
SHOT_ALT = {s["file"]: s["alt"] for s in json.loads((HERE / "guide" / "guide_shots.json").read_text(encoding="utf-8"))["shots"]}


def load_version() -> dict:
    return json.loads((HERE / "guide_version.json").read_text(encoding="utf-8"))


def png_size(path: Path) -> tuple[int, int]:
    """Width and height from the PNG header (stdlib only), so <img> can reserve its space."""
    return struct.unpack(">II", path.read_bytes()[16:24])


def shot(file: str) -> str:
    width, height = png_size(IMG_DIR / file)
    return (
        f'<figure class="guide-shot"><img src="../assets/img/guide/{esc(file)}" alt="{esc(SHOT_ALT[file])}" '
        f'width="{width}" height="{height}" loading="lazy"><figcaption>{esc(SHOT_ALT[file])}</figcaption></figure>'
    )


def stamp(version: dict) -> str:
    return f'<p class="guide-stamp">Checked against Yaaddi {esc(version["app_version"])} on {esc(version["verified"])}.</p>'


# (anchor id, heading, body html, screenshot file or None)
GUIDE_SECTIONS = [
    ("first-lesson", "Your first lesson",
     "<p>Yaaddi has three tabs along the bottom: <strong>Learn</strong>, <strong>Stats</strong> and <strong>Settings</strong>. "
     "Learn starts on your list of courses. Tap a course to see its path: the decks run in order, and the "
     "<strong>Start</strong> marker shows where to continue. Tap a deck to begin a lesson.</p>", "learn-map.png"),
    ("courses", "Find and install courses",
     "<p>On the Learn tab, tap the shop icon to open the <strong>Course Library</strong>. Search, pick a course and tap "
     "<strong>Install</strong>. The Library needs internet; installed courses work offline. Use <strong>Check for updates</strong> "
     "to get newer versions of the courses you have. Details are on the <a href=\"../help/index.html\">course install and update page</a>.</p>",
     "library.png"),
    ("courses-list", "Your course list",
     "<p>Every installed course is listed on the Learn tab. Use <strong>Find a course</strong> to search, and the three-dot menu on a "
     "course for more actions.</p>", "courses.png"),
    ("reviews", "How reviews work",
     "<p>Yaaddi uses spaced repetition: a card you know well comes back after a longer gap, and a card you miss comes back sooner. "
     "You do not schedule anything; the app decides what is due. Five scheduling methods are built in "
     "(SM-2, Fibonacci, FSRS, ACT-R and HLR). The default suits most people; change it under "
     "<strong>Settings &rarr; Studying &rarr; Advanced learning options</strong>.</p>"
     "<p><strong>New topics per session</strong> limits how many new topics a review session adds when nothing is due.</p>",
     "settings-studying.png"),
    ("coins", "Coins, levels and streaks",
     "<p>You earn a Coin for every correct answer. Coins only go up: a wrong answer or a missed day never takes any away. "
     "Tap your level picture at the top to see your level and how many Coins the next one needs. The flame is your study streak; "
     "every 7-day streak earns a <strong>streak freeze</strong> that covers one missed day automatically.</p>", "levels.png"),
    ("stats", "Check your progress",
     "<p>The <strong>Stats</strong> tab shows a calendar of the days you studied, plus totals, accuracy and charts over time. "
     "Tap <strong>Share progress</strong> to send a progress card to a friend.</p>", "stats.png"),
    ("exams", "Test yourself",
     "<p>On a course's path, <strong>Test yourself</strong> starts an exam for that course.</p>", None),
    ("settings", "Make it yours",
     "<p>In <strong>Settings</strong> you can choose light, dark or system appearance, turn sound effects and animations on or off, "
     "change the text size, and set a daily study reminder. Reminders stay on your phone.</p>", "settings.png"),
]

# (question, answer html)
FAQ = [
    ("Is Yaaddi free? Do I need an account?",
     "Yaaddi is free and has no accounts. Nothing is stored about you on a server. See the <a href=\"../privacy/index.html\">privacy page</a>."),
    ("Does it work offline?",
     "Yes. Courses you installed are stored on your phone. Only the Course Library, and checking for updates, need internet."),
    ("The Course Library is empty or says no courses were found.",
     "The list is downloaded from GitHub when you open the Library. Check your internet connection, then reopen the Library. "
     "If it stays empty, write to <a href=\"mailto:support@yaaddi.com\">support@yaaddi.com</a> with your phone model and app version."),
    ("Which scheduling method should I pick?",
     "Keep the default unless you have a reason to change it. Fibonacci is the simplest: gaps grow 1, 2, 3, 5, 8 days and so on. "
     "You can change the method any time under Settings, Studying, Advanced learning options."),
    ("Do I lose Coins or my streak when I make mistakes?",
     "No. Coins only go up, and a wrong answer never costs any. A streak freeze, earned every 7 days of streak, covers one missed day."),
    ("Will updating a course erase my progress?",
     "No. Your review progress on cards that did not change is kept. If an update would remove cards you have already studied, the app warns you first."),
    ("How do I delete my data?",
     "Uninstall the app. Everything is stored only on your phone."),
    ("I found a mistake in a course.",
     "Use <strong>Report a problem</strong> in the app, or write to <a href=\"mailto:support@yaaddi.com\">support@yaaddi.com</a>. "
     "You can also <a href=\"../contribute/index.html\">fix it yourself</a>."),
    ("Is there a Farsi version?",
     "The app itself is available in English and Farsi. This guide is in English only."),
]


def render_guide_sections() -> str:
    version = load_version()
    toc = "".join(f'<li><a href="#{i}">{esc(t)}</a></li>' for i, t, _, _ in GUIDE_SECTIONS)
    body = "".join(
        f'<section class="section" id="{i}"><h2>{esc(t)}</h2>{text}{shot(f) if f else ""}</section>'
        for i, t, text, f in GUIDE_SECTIONS
    )
    return f'<nav class="guide-toc" aria-label="Contents"><ol class="help-steps">{toc}</ol></nav>{body}{stamp(version)}'


def render_faq_sections() -> str:
    items = "".join(f'<details class="privacy-details"><summary>{esc(q)}</summary><p>{a}</p></details>' for q, a in FAQ)
    return f'<section class="section">{items}</section>{stamp(load_version())}'


def render_whats_new_sections() -> str:
    version = load_version()
    blocks = "".join(
        f'<section class="section"><h2>Version {esc(r["version"])} <small>({esc(r["date"])})</small></h2>'
        f'<ul class="help-steps">{"".join(f"<li>{esc(i)}</li>" for i in r["items"])}</ul></section>'
        for r in version["releases"]
    )
    return blocks + stamp(version)
