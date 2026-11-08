#!/usr/bin/env python3
"""Local-LLM-assisted resolver for glossary terms that apply_clean_ledger.py
left with a BLANK introduced_by_card_id — terms that appear only in
exercise-role cards, never in a main/preview card's own text (per
propose_term_ledger.py's "exercise-only" bucket).

For each such term, the most likely fix (confirmed by hand across many
real cases in concurrency-in-python) is that the term's OWN pack's main
card already teaches the concept, just not using that exact string — so
the fix is either:
  (a) MAPPED — link introduced_by_card_id straight to that main card, no
      text change, because reading it a human would agree the concept is
      already covered; or
  (b) NEEDS_EXPLANATION — the main card doesn't really cover it, so
      append one short clarifying sentence to that card's explanation
      that names the term, then link to it.

Only ever writes to the SAME main/preview card the exercise already
points at via related_main_id (or, if that's missing, the first
main/preview card in the same unit) — never invents a new card or
touches prompt/options, so there is no word-limit or correctness risk
the way there is with card rewrites.

Usage:
    python tools/llm_fix_exercise_only_terms.py <course-folder> [--batch-size 6]
    python tools/llm_fix_exercise_only_terms.py --all [--batch-size 6]
"""
import argparse
import os
import sys

import llm_common
from llm_common import (
    DEFAULT_MODEL, LlmFailures, coerce_str, extract_json_array, find_all_course_dirs, read_dict_csv, write_dict_csv,
)
from term_match import build_word_pattern

BATCH_SIZE_DEFAULT = 6

SYSTEM_PROMPT = (
    "You are back-filling a flashcard course's glossary. For each term "
    "given, you see its definition, an exercise card that uses it, and "
    "that exercise's own main/preview card (the card that's supposed to "
    "teach the concept the exercise drills). Decide: does the main card "
    "ALREADY adequately explain this term's concept, just without using "
    "the exact word? If yes, answer MAPPED. If the main card's own "
    "content doesn't really cover it, answer NEEDS_EXPLANATION and give "
    "ONE short sentence (naming the term) to append to that main card's "
    "explanation. Never invent a new card, never contradict the main "
    "card's existing content. Respond ONLY with a JSON array, one object "
    "per term in the same order given, no markdown fences: "
    '{"term": "...", "decision": "MAPPED" or "NEEDS_EXPLANATION", '
    '"add_sentence": "..." (only if NEEDS_EXPLANATION, else "")}'
)


def read_csv(path):
    return read_dict_csv(path, strict=False)[1]


def call_llm(model, user_content):
    return llm_common.call_llm(model, SYSTEM_PROMPT, user_content, temperature=0.1, max_tokens=1600)


def find_exercise_only_terms(course_dir):
    """Reruns the same classification propose_term_ledger.py uses, but only
    returns terms still missing introduced_by_card_id whose only textual
    hits are in exercise-role cards — i.e. exactly what apply_clean_ledger
    left blank on purpose."""
    units = read_csv(os.path.join(course_dir, "source", "units.csv"))
    cards = read_csv(os.path.join(course_dir, "source", "cards.csv"))
    glossary = read_csv(os.path.join(course_dir, "source", "glossary.csv"))
    if not glossary:
        return [], [], {}

    unit_order = {u["id"]: i for i, u in enumerate(units)}

    def sort_key(c):
        return (unit_order.get(c["unit_id"], 10**9), int(c["id"]))

    ordered_cards = sorted(cards, key=sort_key)
    by_id = {c["id"]: c for c in cards}
    # Card text joined once, not once per term x card.
    exercise_texts = [
        (c, " ".join([c.get("prompt", ""), c.get("options", ""), c.get("explanation", "")]))
        for c in ordered_cards if c.get("role") == "exercise"
    ]

    missing = [g for g in glossary if not (g.get("introduced_by_card_id") or "").strip()]
    results = []
    for g in sorted(missing, key=lambda g: -len(g["term"])):
        term = g["term"]
        pattern = build_word_pattern(term)
        first_exercise = next((c for c, text in exercise_texts if pattern.search(text)), None)
        if first_exercise is None:
            continue  # dead term or something apply_clean_ledger should have caught
        main_id = first_exercise.get("related_main_id") or ""
        main_card = by_id.get(main_id)
        if main_card is None:
            # fall back to first main/preview card in the same unit
            for c in ordered_cards:
                if c["unit_id"] == first_exercise["unit_id"] and c.get("role") in ("main", "preview"):
                    main_card = c
                    break
        if main_card is None:
            continue  # nothing sensible to link to — leave for manual review
        results.append((g, first_exercise, main_card))
    return results, glossary, cards


def format_term(term_row, exercise_card, main_card):
    return (
        f'term: {term_row["term"]}\n'
        f'definition: {term_row.get("definition","")}\n'
        f'exercise card (id={exercise_card["id"]}): prompt={exercise_card.get("prompt","")} '
        f'options={exercise_card.get("options","")}\n'
        f'main card (id={main_card["id"]}): prompt={main_card.get("prompt","")} '
        f'options={main_card.get("options","")} explanation={main_card.get("explanation","") or "(blank)"}'
    )


def fix_course(course_dir, model, batch_size, failures=None):
    failures = failures or LlmFailures()
    todo, glossary, cards = find_exercise_only_terms(course_dir)
    if not todo:
        return False

    glossary_path = os.path.join(course_dir, "source", "glossary.csv")
    cards_path = os.path.join(course_dir, "source", "cards.csv")
    print(f"  {os.path.basename(course_dir)}: {len(todo)} exercise-only term(s)")

    glossary_by_term = {g["term"]: g for g in glossary}
    cards_by_id = {c["id"]: c for c in cards}
    card_fieldnames = list(cards[0].keys()) if cards else []
    glossary_fieldnames = list(glossary[0].keys()) if glossary else []

    changed_glossary = False
    changed_cards = False

    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        block = "\n---\n".join(format_term(*t) for t in batch)
        try:
            raw = call_llm(model, block)
        except Exception as e:  # noqa: BLE001
            print(f"    batch {i}-{i+len(batch)} FAILED: {e}")
            if failures.failed():
                break
            continue
        failures.ok()
        parsed = extract_json_array(raw)
        if not parsed:
            print(f"    batch {i}-{i+len(batch)}: could not parse model output, skipping")
            continue

        result_by_term = {item.get("term"): item for item in parsed if isinstance(item, dict)}
        for term_row, exercise_card, main_card in batch:
            result = result_by_term.get(term_row["term"])
            if not result:
                continue
            decision = result.get("decision")
            if decision not in ("MAPPED", "NEEDS_EXPLANATION"):
                continue
            glossary_by_term[term_row["term"]]["introduced_by_card_id"] = main_card["id"]
            changed_glossary = True
            if decision == "NEEDS_EXPLANATION":
                sentence = coerce_str(result.get("add_sentence")) or ""
                if sentence:
                    existing = cards_by_id[main_card["id"]].get("explanation", "") or ""
                    cards_by_id[main_card["id"]]["explanation"] = (
                        (existing + " " + sentence).strip() if existing else sentence
                    )
                    changed_cards = True

        print(f"    batch {i}-{i+len(batch)} done")

    if changed_glossary:
        write_dict_csv(glossary_path, glossary_fieldnames, glossary)
    if changed_cards:
        write_dict_csv(cards_path, card_fieldnames, cards)

    print(f"  DONE: {os.path.basename(course_dir)} — glossary_changed={changed_glossary} cards_changed={changed_cards}")
    return changed_glossary or changed_cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    if args.all:
        course_dirs = find_all_course_dirs()
        if not course_dirs:
            ap.error(f"no course folders (with a meta.json) found under {llm_common.REPO_ROOT}")
    elif args.course:
        course_dirs = [args.course]
    else:
        ap.error("pass a course folder or --all")
        return

    print(f"Resolving exercise-only terms for {len(course_dirs)} course(s) with model={args.model}")
    failures = LlmFailures()
    for course_dir in course_dirs:
        fix_course(course_dir, args.model, args.batch_size, failures)
        if failures.tripped:
            sys.exit(1)


if __name__ == "__main__":
    main()
