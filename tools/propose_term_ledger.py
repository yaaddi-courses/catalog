#!/usr/bin/env python3
"""Proposes `introduced_by_card_id` values for every glossary.csv term that's
missing one, as a candidate ledger for human approval — never writes the
CSV itself.

For each term, finds the FIRST card (walking units in `units.csv` order,
then cards within a unit by id) whose role is `main` or `preview` and whose
prompt/options/explanation contains the term as a whole word (same
matching convention as tools/check_key_term_usage.py: case-insensitive,
longest-term-first so a multi-word term isn't shadowed by a shorter
substring). A `main`/`preview` card is preferred over an `exercise` card as
the "teaches it" card, matching how this repo's own pack structure works
(preview/main introduce; exercise cards only ever exercise what's already
been taught) — see flashcard-course-creator's SKILL.md.

This is a proposal tool, not an authority: it finds the first MENTION, not
necessarily the first card that actually explains the term (a term can be
name-dropped in passing before the pack that truly defines it) — a human
(or the flashcard-course-reviewer agent) must still confirm each proposal
against the real card text before it's written into glossary.csv. Flags
any term found nowhere in the course at all (dead glossary entry) and any
term whose only appearances are in `exercise`-role cards (never actually
taught, only drilled — a real content gap, not just a ledger gap).

Usage:
    python tools/propose_term_ledger.py <course-folder>
"""
import argparse
import csv
import os
import re
import sys


def read_csv(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_word_pattern(term):
    return re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE | re.UNICODE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course")
    args = ap.parse_args()

    course_dir = args.course
    units = read_csv(os.path.join(course_dir, "source", "units.csv"))
    cards = read_csv(os.path.join(course_dir, "source", "cards.csv"))
    glossary = read_csv(os.path.join(course_dir, "source", "glossary.csv"))

    if not glossary:
        print("no glossary.csv found (or it's empty)")
        return

    unit_order = {u["id"]: i for i, u in enumerate(units)}

    def sort_key(c):
        return (unit_order.get(c["unit_id"], 10**9), int(c["id"]))

    ordered_cards = sorted(cards, key=sort_key)

    missing = [g for g in glossary if not (g.get("introduced_by_card_id") or "").strip()]
    if not missing:
        print(f"all {len(glossary)} glossary terms already have introduced_by_card_id set")
        return

    # Longest-term-first so "Governor General" isn't shadowed by "Governor"
    # when both exist — same reasoning as check_key_term_usage.py.
    missing_sorted = sorted(missing, key=lambda g: -len(g["term"]))

    proposals = []
    dead_terms = []
    exercise_only_terms = []

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
            proposals.append((term, first_teach))
        elif first_any is not None:
            exercise_only_terms.append((term, first_any))
        else:
            dead_terms.append(term)

    # Report in the ORDER those cards actually appear in the course, not
    # alphabetically — the user asked to review "starting from the first
    # one" (i.e. teaching order), not a glossary-alphabetical dump.
    proposals.sort(key=lambda p: sort_key(p[1]))

    print(f"=== {os.path.basename(course_dir)}: term ledger proposal ===")
    print(f"{len(proposals)} term(s) with a clear main/preview card to propose:\n")
    for term, card in proposals:
        unit_title = next((u["title"] for u in units if u["id"] == card["unit_id"]), "?")
        print(f'  "{term}" -> card {card["id"]} ({card["role"]}, unit "{unit_title}")')
        print(f'      prompt: {card["prompt"][:80]}')

    if exercise_only_terms:
        print(f"\n{len(exercise_only_terms)} term(s) used ONLY in exercise cards (never actually taught — a real content gap, not just a ledger gap):")
        for term, card in exercise_only_terms:
            print(f'  "{term}" -> first seen in card {card["id"]} ({card["role"]}): {card["prompt"][:70]}')

    if dead_terms:
        print(f"\n{len(dead_terms)} term(s) not found anywhere in cards.csv (dead glossary entry — check for a typo or a since-removed card):")
        for term in dead_terms:
            print(f'  "{term}"')


if __name__ == "__main__":
    main()
