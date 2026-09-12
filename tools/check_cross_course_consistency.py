#!/usr/bin/env python3
"""Flags candidates for cross-course duplication/overlap that only show up
once you can see every course at once — nothing in a single-course review
(validate_course.py, the flashcard-course-reviewer agent) ever compares
against the other 16. Every finding here is a CANDIDATE for a human/agent
to read and judge, never an automatic verdict — overlap between courses
isn't itself a failure (see flashcard-course-reviewer.md's own "Overlap
with another course isn't itself a failure" note); only undifferentiated
duplication with no acknowledgment is.

Reports three things:
  1. Glossary term collisions — the same term defined in glossary.csv in
     2+ courses. Flags both an identical definition (candidate: one course
     should link to the other's course instead of redefining it) and a
     materially different one (candidate: genuine terminology drift worth
     reading both to resolve).
  2. Near-duplicate card prompts across courses — the exact same
     normalization validate_course.py's own in-course duplicate check
     already uses (prompt.lower() + "||" + options.lower()), run pairwise
     across every course instead of within one.
  3. Tag/topic overlap — courses sharing most of their meta.json "tags"
     list, a cheap signal worth a closer read, not a verdict on its own.

Usage:
    python tools/check_cross_course_consistency.py --courses-dir <path>

Reuses discover_courses()'s exact directory-walking convention from
build_site.py so both tools see the same course set from the same
--courses-dir input.
"""
import argparse
import csv
import json
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_site import discover_courses  # noqa: E402 (needs sys.path set first)


def normalize_term(term):
    return term.strip().lower()


def load_glossary(course_dir):
    path = course_dir / "source" / "glossary.csv"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_cards(course_dir):
    path = course_dir / "source" / "cards.csv"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_tags(course_dir):
    meta_path = course_dir / "meta.json"
    if not meta_path.is_file():
        return set()
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {t.strip().lower() for t in meta.get("tags", []) if t.strip()}


def check_glossary_collisions(course_dirs):
    by_term = {}
    for course_dir in course_dirs:
        for row in load_glossary(course_dir):
            term = (row.get("term") or "").strip()
            if not term:
                continue
            by_term.setdefault(normalize_term(term), []).append(
                (course_dir.name, term, (row.get("definition") or "").strip())
            )

    findings = []
    for _norm, entries in by_term.items():
        if len(entries) < 2:
            continue
        definitions = {d for _c, _t, d in entries}
        courses = ", ".join(f'{c} ("{t}")' for c, t, _d in entries)
        if len(definitions) == 1:
            findings.append(f'"{entries[0][1]}" defined identically in: {courses}')
        else:
            lines = "; ".join(f'{c}: "{d[:80]}"' for c, _t, d in entries)
            findings.append(f'"{entries[0][1]}" defined differently across courses — {lines}')
    return findings


def check_duplicate_prompts(course_dirs):
    by_key = {}
    for course_dir in course_dirs:
        for c in load_cards(course_dir):
            prompt = (c.get("prompt") or "").strip()
            if not prompt:
                continue
            ctype = c.get("type") or "multiple_choice"
            # Same exemptions validate_course.py's own in-course check
            # applies — speech_recognition/listening_card legitimately
            # repeat a production/listening prompt on purpose.
            if ctype in ("speech_recognition", "listening_card"):
                continue
            key = prompt.lower() + "||" + (c.get("options") or "").strip().lower()
            by_key.setdefault(key, []).append((course_dir.name, c.get("id"), prompt))

    findings = []
    for _key, entries in by_key.items():
        courses_involved = {c for c, _id, _p in entries}
        if len(courses_involved) < 2:
            continue  # within-course duplicates are validate_course.py's job
        locs = ", ".join(f"{c} (card {cid})" for c, cid, _p in entries)
        findings.append(f'"{entries[0][2]}" appears near-identically in: {locs}')
    return findings


def check_tag_overlap(course_dirs, min_shared=2, min_share_ratio=0.6):
    tags_by_course = {c.name: load_tags(c) for c in course_dirs}
    findings = []
    for (name_a, tags_a), (name_b, tags_b) in combinations(tags_by_course.items(), 2):
        if not tags_a or not tags_b:
            continue
        shared = tags_a & tags_b
        smaller = min(len(tags_a), len(tags_b))
        if len(shared) >= min_shared and len(shared) / smaller >= min_share_ratio:
            findings.append(f"{name_a} and {name_b} share tags: {', '.join(sorted(shared))}")
    return findings


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--courses-dir", required=True, help="directory containing every course folder")
    args = parser.parse_args()

    course_dirs = discover_courses(Path(args.courses_dir))
    if not course_dirs:
        print(f"No course folders found under {args.courses_dir}")
        sys.exit(1)

    sections = [
        ("Glossary term collisions", check_glossary_collisions(course_dirs)),
        ("Near-duplicate card prompts across courses", check_duplicate_prompts(course_dirs)),
        ("Tag/topic overlap", check_tag_overlap(course_dirs)),
    ]

    print(f"=== Cross-course consistency across {len(course_dirs)} course(s) ===\n")
    total = 0
    for title, findings in sections:
        print(f"--- {title} ---")
        if not findings:
            print("(none)")
        for line in findings:
            print(f"- {line}")
        print()
        total += len(findings)

    print(f"{total} candidate(s) found — read each before treating it as a real defect.")


if __name__ == "__main__":
    main()
