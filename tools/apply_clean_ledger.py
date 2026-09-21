#!/usr/bin/env python3
"""Deterministically applies propose_term_ledger.py's "clean" proposals
(terms with an unambiguous first main/preview card) directly into
glossary.csv's introduced_by_card_id, and removes dead glossary entries
(terms that appear nowhere in cards.csv — almost always a stale/typo'd
row from a since-edited course). Pure text matching, no LLM, no risk.

Terms used only in exercise cards are deliberately left with a BLANK
introduced_by_card_id — those need real judgment (does an existing card
already explain it well enough, or does something need a sentence
added?) and are handled by llm_fix_exercise_only_terms.py instead.

Usage:
    python tools/apply_clean_ledger.py <course-folder>
    python tools/apply_clean_ledger.py --all
"""
import argparse
import csv
import os
import re
import sys


def read_csv(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_word_pattern(term):
    return re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE | re.UNICODE)


def apply_course(course_dir):
    glossary_path = os.path.join(course_dir, "source", "glossary.csv")
    units = read_csv(os.path.join(course_dir, "source", "units.csv"))
    cards = read_csv(os.path.join(course_dir, "source", "cards.csv"))
    glossary = read_csv(glossary_path)

    if not glossary:
        print(f"  {os.path.basename(course_dir)}: no glossary.csv, skipping")
        return False

    unit_order = {u["id"]: i for i, u in enumerate(units)}

    def sort_key(c):
        return (unit_order.get(c["unit_id"], 10**9), int(c["id"]))

    ordered_cards = sorted(cards, key=sort_key)

    fieldnames = list(glossary[0].keys())
    if "introduced_by_card_id" not in fieldnames:
        fieldnames.append("introduced_by_card_id")

    missing = [g for g in glossary if not (g.get("introduced_by_card_id") or "").strip()]
    missing_sorted = sorted(missing, key=lambda g: -len(g["term"]))

    clean = 0
    dead = 0
    exercise_only = 0
    dead_terms = set()

    for g in missing_sorted:
        term = g["term"]
        pattern = build_word_pattern(term)
        first_teach = None
        first_any = None
        for c in ordered_cards:
            haystack = " ".join([c.get("prompt", ""), c.get("options", ""), c.get("explanation", "")])
            if pattern.search(haystack):
                if first_any is None:
                    first_any = c
                if c.get("role") in ("main", "preview") and first_teach is None:
                    first_teach = c
                    break
        if first_teach is not None:
            g["introduced_by_card_id"] = first_teach["id"]
            clean += 1
        elif first_any is not None:
            exercise_only += 1  # left blank on purpose
        else:
            dead_terms.add(term)
            dead += 1

    remaining = [g for g in glossary if g["term"] not in dead_terms]

    with open(glossary_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(remaining)

    print(f"  {os.path.basename(course_dir)}: {clean} mapped, {dead} dead removed, {exercise_only} exercise-only left for LLM pass")
    return True


def find_all_course_dirs(root):
    dirs = []
    for entry in sorted(os.listdir(root)):
        p = os.path.join(root, entry)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "meta.json")):
            dirs.append(p)
    return dirs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        course_dirs = find_all_course_dirs(os.getcwd())
    elif args.course:
        course_dirs = [args.course]
    else:
        ap.error("pass a course folder or --all")
        return

    for course_dir in course_dirs:
        apply_course(course_dir)


if __name__ == "__main__":
    main()
