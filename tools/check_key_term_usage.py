#!/usr/bin/env python3
"""Checks that no card uses a glossary term before the card that actually
teaches it, for ANY course (not just a teaches_language one — see
check_word_coverage.py for that narrower, vocabulary-specific ledger).

Unlike language-course vocabulary, `glossary.csv` has no built-in link to a
specific card — it's just a term/definition lookup table the app's
LinkedText/glossaryMatch.ts uses at render time, independent of teaching
order (see docs/GLOSSARY.md in the app repo). So this script relies on an
explicit `introduced_by_card_id` column in glossary.csv (added per-term by
whoever reviews the course — validate_course.py warns on any term missing
it, and hard-errors if it points at a card id that doesn't exist). A term
with no introduced_by_card_id yet is skipped here, not flagged — that's
validate_course.py's job, not this script's.

Matching mirrors the app's own app/src/domain/glossaryMatch.ts: whole-word,
case-insensitive, longest-term-first (so "Governor General" matches whole
rather than "Governor" swallowing half the phrase). Python's `\b` is
Unicode-aware by default for `str` patterns, unlike JS's ASCII-only `\b`
(which glossaryMatch.ts has to work around) — no equivalent workaround
needed here.

Deliberately unit-granularity, not raw card-id order — the same tradeoff
check_word_coverage.py's find_undefined_references already documents and
chose for the identical reason (a course edited incrementally over time
ends up with card ids that don't track true teaching order within a unit
anymore; checking "used in an EARLIER unit" is robust to that at the cost of
not catching a same-unit forward-reference).

Usage:
    python tools/check_key_term_usage.py <course-folder>   # one course
    python tools/check_key_term_usage.py --all             # every course at the repo root
"""
import argparse
import csv
import os
import re
import sys
from pathlib import Path


def load_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_unit_order(course_dir):
    """unit id -> its row position in units.csv (0-based) — see
    check_word_coverage.py's load_unit_order, same convention."""
    rows = load_rows(os.path.join(course_dir, "source", "units.csv"))
    return {u["id"]: i for i, u in enumerate(rows)}


def card_text(card):
    return " ".join(
        (card.get(field) or "") for field in ("prompt", "options", "explanation")
    )


def build_matcher(terms):
    """One compiled regex for every term, longest first — mirrors
    glossaryMatch.ts's buildGlossaryMatcher exactly (see its own doc
    comment in app/src/domain/glossaryMatch.ts for why longest-first and
    why whole-word matching, restated in this file's own module doc
    comment above)."""
    ordered = sorted(set(terms), key=len, reverse=True)
    pattern = "|".join(re.escape(t) for t in ordered)
    return re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE) if ordered else None


def check_course(course_dir):
    """Returns a list of finding strings — empty means clean."""
    source_dir = os.path.join(course_dir, "source")
    glossary_path = os.path.join(source_dir, "glossary.csv")
    if not os.path.isfile(glossary_path):
        return []

    glossary_rows = load_rows(glossary_path)
    cards = load_rows(os.path.join(source_dir, "cards.csv"))
    cards_by_id = {c["id"]: c for c in cards}
    unit_order = load_unit_order(course_dir)

    findings = []
    for row in glossary_rows:
        term = (row.get("term") or "").strip()
        intro_id = (row.get("introduced_by_card_id") or "").strip()
        if not term or not intro_id:
            continue  # validate_course.py's job to flag a missing link
        intro_card = cards_by_id.get(intro_id)
        if not intro_card:
            continue  # validate_course.py already hard-errors this
        intro_rank = unit_order.get(intro_card["unit_id"], 10**9)

        matcher = build_matcher([term])
        for c in cards:
            if c["id"] == intro_id:
                continue
            card_rank = unit_order.get(c["unit_id"], 10**9)
            if card_rank >= intro_rank:
                continue  # same unit or later — not "before", see module doc comment
            if matcher.search(card_text(c)):
                findings.append(
                    f'card {c["id"]} (unit={c["unit_id"]}): uses "{term}" before its '
                    f'introducing card {intro_id} (unit={intro_card["unit_id"]})'
                )
    return findings


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("course", nargs="?", help="path to a single course folder")
    parser.add_argument(
        "--all", action="store_true", help="check every course folder at the repo root"
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    course_dirs = []
    if args.all:
        for entry in sorted(os.listdir(repo_root)):
            full = repo_root / entry
            if full.is_dir() and (full / "meta.json").is_file():
                course_dirs.append(full)
    elif args.course:
        course_dirs.append(Path(args.course))
    else:
        parser.print_help()
        sys.exit(1)

    total_findings = 0
    for course_dir in course_dirs:
        findings = check_course(course_dir)
        print(f"=== {course_dir.name} ===")
        if not findings:
            print("(clean)")
        for line in findings:
            print(f"- {line}")
        print()
        total_findings += len(findings)

    sys.exit(1 if total_findings else 0)


if __name__ == "__main__":
    main()
