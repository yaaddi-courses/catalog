#!/usr/bin/env python3
"""Checks that a course's declared content language (source/meta.csv's
`language` column) actually matches the script its cards are written in,
and that no card ends up silently misdirected.

Why this exists: the app decides a card's base reading direction from
`packages.language` (set at import time from meta.csv's `language` column
— NOT from meta.json's top-level "language" field, which only affects
catalog listing/translation selection). A course authored entirely in
Farsi/Arabic/Hebrew/Urdu script but missing (or wrong in) that `language`
column silently renders left-to-right for every card — a real bug this
script caught in `scam-tashkhis-farsi` (meta.csv had no `language` column
at all, so every RTL-script card rendered LTR despite meta.json separately
claiming "language": "fa").

Per-option/per-string direction inside a card is a SEPARATE, already-correct
mechanism (see app/src/lib/textDirection.ts's `autoDirectionOf`): the app
auto-detects each option/chip's own direction from its own first strong
character, independent of the package's overall language — so a Farsi
course can still have a pure-English option (e.g. a technical term) render
LTR correctly, and vice versa. This script mirrors that exact "first
strong character" rule (same Unicode ranges, same skip-digits/punctuation
logic) so its verdicts match what the app will actually render, instead of
inventing a different heuristic.

What this script flags:
  1. meta.csv `language` missing/`en` (or unset) while the bulk of the
     course's own text is RTL-script — the exact bug class described above.
  2. meta.csv `language` set to an RTL code while the bulk of the course's
     text is actually Latin-script — the mirror-image mistake.
  3. Per-card: an individual prompt whose OWN first-strong direction
     disagrees with the course's declared package-level language, when
     that prompt is plain single-direction prose (not a legitimate
     inline quote/code snippet, which the app already lets embed either
     direction inside a paragraph via bidi). This surfaces authoring
     slips (e.g. a stray Latin punctuation mark at the very start of an
     otherwise-Farsi sentence flipping its rendered direction) without
     false-flagging normal bilingual inline usage.

Usage:
    python tools/check_text_direction.py <course-folder>   # one course
    python tools/check_text_direction.py --all             # every course at the repo root
"""
import argparse
import csv
import os
import re
import sys
from pathlib import Path

RTL_LANGUAGES = {"fa", "ar", "he", "ur"}

# Mirrors app/src/lib/textDirection.ts's RTL_SCRIPT_PATTERN exactly:
# U+0590-U+08FF (Hebrew through Arabic Extended-A, covers Farsi/Arabic/
# Hebrew/Urdu).
RTL_SCRIPT_PATTERN = re.compile("[֐-ࣿ]")
LTR_SCRIPT_PATTERN = re.compile("[A-Za-z]")


def read_csv(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def first_strong_direction(text):
    """Mirrors autoDirectionOf: first RTL or Latin character found wins;
    None if the string has no directionally-strong character at all."""
    for ch in text or "":
        if RTL_SCRIPT_PATTERN.match(ch):
            return "rtl"
        if LTR_SCRIPT_PATTERN.match(ch):
            return "ltr"
    return None


def script_ratio(text):
    """Returns (rtl_char_count, ltr_char_count) for a whole string —
    used for the course-wide majority-script estimate, not per-card
    first-strong judging."""
    rtl = len(RTL_SCRIPT_PATTERN.findall(text or ""))
    ltr = len(LTR_SCRIPT_PATTERN.findall(text or ""))
    return rtl, ltr


def check_course(course_dir):
    problems = []
    meta_rows = read_csv(os.path.join(course_dir, "source", "meta.csv"))
    declared_language = (meta_rows[0].get("language") if meta_rows else "") or "en"
    declared_language = declared_language.strip().lower() or "en"
    declared_rtl = declared_language in RTL_LANGUAGES
    # A teaches_language:true course deliberately mixes scripts card-by-card
    # (a base-language-framed course's target-language item IS the prompt on
    # many cards, by design — see flashcard-course-reviewer.md's own
    # language-course section for the dedicated script-mixing rules that
    # already cover this). The per-card first-strong check below would be
    # pure noise there, so it's skipped for such courses — only the
    # course-level majority-script sanity check still applies (a language
    # course's `language` column should still name the real audience
    # language, RTL or not).
    teaches_language = ((meta_rows[0].get("teaches_language") if meta_rows else "") or "").strip().lower() == "true"

    cards = read_csv(os.path.join(course_dir, "source", "cards.csv"))
    if not cards:
        return declared_language, ["no cards.csv found or it's empty"]

    total_rtl_chars = 0
    total_ltr_chars = 0
    per_card_mismatches = []

    for c in cards:
        cid = c.get("id")
        ctype = c.get("type") or ""
        # Skip types whose "prompt" legitimately holds code/commands/passages
        # (see validate_course.py's own newline exemption for these types) —
        # a code snippet's own script isn't a meaningful direction signal.
        prompt = c.get("prompt") or ""
        if "\n" in prompt or ctype in ("code_fill", "command_output", "reading_passage", "cloze_passage"):
            continue

        for field_name in ("prompt", "options", "explanation"):
            text = c.get(field_name) or ""
            if not text.strip():
                continue
            r, l = script_ratio(text)
            total_rtl_chars += r
            total_ltr_chars += l

        # Per-card prompt-level first-strong check, only for plain prose
        # prompts (skip select_blank — its "before___after" shape often
        # legitimately starts with a short fragment whose first character
        # isn't representative of the sentence's real direction).
        if ctype == "select_blank":
            continue
        fs = first_strong_direction(prompt)
        if fs is not None:
            expected = "rtl" if declared_rtl else "ltr"
            if fs != expected:
                per_card_mismatches.append((cid, fs, prompt[:60]))

    if total_rtl_chars + total_ltr_chars > 0:
        actual_majority_rtl = total_rtl_chars > total_ltr_chars
        if actual_majority_rtl and not declared_rtl:
            problems.append(
                f'meta.csv "language" is "{declared_language}" (LTR) but the course\'s own text is '
                f"majority RTL-script ({total_rtl_chars} RTL chars vs {total_ltr_chars} LTR chars) — "
                f'every card will render left-to-right. Set meta.csv\'s "language" column to "fa" '
                f"(or whichever RTL code applies)."
            )
        elif declared_rtl and not actual_majority_rtl:
            problems.append(
                f'meta.csv "language" is "{declared_language}" (RTL) but the course\'s own text is '
                f"majority Latin-script ({total_ltr_chars} LTR chars vs {total_rtl_chars} RTL chars) — "
                f"double check this is really an RTL-content course, not a base-language mismatch."
            )

    # Only report per-card mismatches if the course-level language looks
    # correctly declared — otherwise every card will mismatch for the same
    # root cause already reported above, and 100+ redundant lines just
    # bury the signal. Also skipped entirely for a teaches_language course
    # (see above).
    if not problems and not teaches_language:
        for cid, fs, snippet in per_card_mismatches:
            problems.append(
                f"card {cid}: prompt's own first-strong direction is {fs}, opposite the course's "
                f'declared "{declared_language}" language — starts: "{snippet}..." '
                f"(check for a stray leading Latin/RTL character, e.g. punctuation, flipping detected direction)"
            )

    return declared_language, problems


def find_all_course_dirs(root):
    dirs = []
    for entry in sorted(os.listdir(root)):
        p = os.path.join(root, entry)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "meta.json")):
            dirs.append(p)
    return dirs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course", nargs="?", help="course folder to check")
    ap.add_argument("--all", action="store_true", help="check every course at the repo root")
    args = ap.parse_args()

    if args.all:
        root = os.getcwd()
        course_dirs = find_all_course_dirs(root)
    elif args.course:
        course_dirs = [args.course]
    else:
        ap.error("pass a course folder or --all")
        return

    any_problems = False
    for course_dir in course_dirs:
        name = os.path.basename(os.path.normpath(course_dir))
        declared_language, problems = check_course(course_dir)
        if problems:
            any_problems = True
            print(f"=== {name} (language={declared_language}): {len(problems)} issue(s) ===")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"=== {name} (language={declared_language}): OK ===")

    sys.exit(1 if any_problems else 0)


if __name__ == "__main__":
    main()
