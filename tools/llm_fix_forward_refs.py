#!/usr/bin/env python3
"""Local-LLM-assisted fixer for forward-references found by
check_key_term_usage.py — cards that use a glossary term before the card
that's supposed to teach it. Generalizes the manual process used for
concurrency-in-python's 60 forward-references (see that course's commit
history) to run across every course automatically.

For each offending card, the model picks one of:
  REWORD — rewrite the card's prompt/options/explanation to avoid the
    term(s), preserving the correct answer and meaning exactly.
  REMAP — the offending card is actually a legitimate (often earlier and
    better) place to introduce the term; move introduced_by_card_id to
    it instead of rewriting anything. Only accepted for a term flagged on
    that card, and only when the card is a main or preview card (an
    exercise never "teaches" a term); if several cards remap one term the
    earliest wins.

Safety: every REWORD goes through llm_common.rewrite_problem (word limits,
the correct option keeps its text and position, the options of
answer-bearing types are never touched), and the original text of every
touched card is kept in memory so it can be reverted individually (not
the whole course) if the trusted validate_course.py still rejects it
afterward, or if the reword brought in another glossary term too early
(find_forward_refs is re-run). If the validator cannot run at all, every
edit of this pass is reverted. cards.csv and glossary.csv are written after
every batch, so an interrupted run keeps the finished batches. Anything still
flagged is left alone and reported, never looped forever.

Usage:
    python tools/llm_fix_forward_refs.py <course-folder> [--batch-size 3] [--model NAME]
    python tools/llm_fix_forward_refs.py --all [--batch-size 3] [--model NAME]
"""
import argparse
import os
import sys

import llm_common
from llm_common import (
    DEFAULT_MODEL, LlmFailures, coerce_str, extract_json_array, find_all_course_dirs, rewrite_problem,
    write_dict_csv,
)
from term_match import build_matcher, build_word_pattern  # noqa: F401  (build_word_pattern: shared API)

BATCH_SIZE_DEFAULT = 3

SYSTEM_PROMPT = (
    "You fix a flashcard course's forward-reference bugs: a card uses a "
    "technical term before the course has actually taught it. For each "
    "card given, you see which term(s) it uses too early, each term's "
    "definition, and which later card is supposed to introduce it. "
    "Decide ONE fix per card:\n"
    "REWORD — rewrite ONLY what's necessary in prompt/options/explanation "
    "to remove the premature term(s), replacing with a plain-English "
    "description instead. You MUST preserve the exact same correct "
    "answer, the same number of options, and the same meaning. Hard "
    "limits: prompt under 10 words total, each option under 3 words.\n"
    "REMAP — use this ONLY if this card itself is actually a good, clear "
    "place to teach the term (better than the card currently credited) — "
    "then no text change is needed, just move the credit here.\n"
    "Respond ONLY with a JSON array, one object per card in the same "
    "order given, no markdown fences: {\"card_id\": \"...\", "
    '"decision": "REWORD" or "REMAP", "remap_term": "..." (only for '
    'REMAP — which term moves here), "prompt": "..." (only for REWORD, '
    'omit if unchanged), "options": "..." (only for REWORD, omit if '
    'unchanged), "explanation": "..." (only for REWORD, omit if '
    "unchanged)}"
)


def read_csv(path):
    return llm_common.read_csv(path)


def call_llm(model, user_content):
    return llm_common.call_llm(model, SYSTEM_PROMPT, user_content, temperature=0.1, max_tokens=2000)


def run_validate(course_dir):
    return llm_common.run_validate(course_dir)


def card_text(card):
    return " ".join((card.get(f) or "") for f in ("prompt", "options", "explanation"))


def find_forward_refs(course_dir):
    """Same logic as check_key_term_usage.py's check_course, but returns
    structured (card_id, [(term, definition, intro_id), ...]) groups."""
    source_dir = os.path.join(course_dir, "source")
    _, glossary = read_csv(os.path.join(source_dir, "glossary.csv"))
    _, units = read_csv(os.path.join(source_dir, "units.csv"))
    card_fields, cards = read_csv(os.path.join(source_dir, "cards.csv"))
    if not glossary or not cards:
        return {}, card_fields, cards
    cards_by_id = {c["id"]: c for c in cards}
    unit_order = {u["id"]: i for i, u in enumerate(units)}
    # Computed once per card, not once per term x card.
    ranked = [(unit_order.get(c["unit_id"], 10**9), c["id"], card_text(c)) for c in cards]

    groups = {}
    for row in glossary:
        term = (row.get("term") or "").strip()
        definition = row.get("definition") or ""
        intro_id = (row.get("introduced_by_card_id") or "").strip()
        if not term or not intro_id:
            continue
        intro_card = cards_by_id.get(intro_id)
        if not intro_card:
            continue
        intro_rank = unit_order.get(intro_card["unit_id"], 10**9)
        matcher = build_matcher([term])
        for card_rank, cid, text in ranked:
            if cid != intro_id and card_rank < intro_rank and matcher.search(text):
                groups.setdefault(cid, []).append((term, definition, intro_id))
    return groups, card_fields, cards


def format_group(card, terms):
    term_block = "\n".join(
        f'  - "{t}" (def: {d[:100]}) — should be taught first at card {intro}'
        for t, d, intro in terms
    )
    return (
        f'card_id={card["id"]} type={card["type"]}\n'
        f'prompt: {card.get("prompt","")}\n'
        f'options: {card.get("options","")}\n'
        f'explanation: {card.get("explanation","") or "(blank)"}\n'
        f'terms used too early:\n{term_block}'
    )


def fix_course(course_dir, model, batch_size, failures=None):
    failures = failures or LlmFailures()
    groups, card_fields, cards = find_forward_refs(course_dir)
    if not groups:
        return False

    name = os.path.basename(course_dir)
    print(f"  {name}: {len(groups)} card(s) with forward-referenced term(s)")

    cards_by_id = {c["id"]: c for c in cards}
    cards_path = os.path.join(course_dir, "source", "cards.csv")
    glossary_path = os.path.join(course_dir, "source", "glossary.csv")
    glossary_fields, glossary = read_csv(glossary_path)
    glossary_by_term = {g["term"].strip(): g for g in glossary}
    _, units = read_csv(os.path.join(course_dir, "source", "units.csv"))
    unit_order = {u["id"]: i for i, u in enumerate(units)}

    def rank(cid):
        c = cards_by_id.get(cid)
        return (unit_order.get(c["unit_id"], 10**9), int(cid)) if c else (10**9, 10**9)

    original = {}  # card_id -> original field dict, for per-card revert
    original_intro = {}  # term -> introduced_by_card_id before this pass
    touched_card_ids = set()

    group_items = list(groups.items())
    for i in range(0, len(group_items), batch_size):
        batch = group_items[i : i + batch_size]
        block = "\n---\n".join(format_group(cards_by_id[cid], terms) for cid, terms in batch)
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

        result_by_id = {str(item.get("card_id")): item for item in parsed if isinstance(item, dict)}
        batch_cards = batch_terms = False
        for cid, terms in batch:
            result = result_by_id.get(cid)
            if not result:
                continue
            card = cards_by_id[cid]
            decision = coerce_str(result.get("decision"))
            if decision == "REMAP":
                flagged = {t.lower(): t for t, _, _ in terms}
                term = flagged.get((coerce_str(result.get("remap_term")) or "").lower())
                if term is None or term not in glossary_by_term or card.get("role") not in ("main", "preview"):
                    continue  # only a term flagged on this card, and only onto a teaching card
                entry = glossary_by_term[term]
                if rank(cid) < rank(entry["introduced_by_card_id"].strip()):
                    original_intro.setdefault(term, entry["introduced_by_card_id"])
                    entry["introduced_by_card_id"] = cid
                    batch_terms = True
                continue
            if decision != "REWORD":
                continue
            new_prompt = coerce_str(result.get("prompt"))
            new_options = coerce_str(result.get("options"), "|")
            new_explanation = coerce_str(result.get("explanation"))
            if rewrite_problem(card, new_prompt, new_options):
                continue  # leave untouched, will still show up in the final residual report
            original.setdefault(cid, dict(card))
            if new_prompt:
                card["prompt"] = new_prompt
            if new_options:
                card["options"] = new_options
            if new_explanation:
                card["explanation"] = new_explanation
            touched_card_ids.add(cid)
            batch_cards = True

        # Written after every batch so an interrupted run keeps its finished work.
        if batch_cards:
            write_dict_csv(cards_path, card_fields, cards)
        if batch_terms:
            write_dict_csv(glossary_path, glossary_fields, glossary)
        print(f"    batch {i}-{i+len(batch)} done")

    if not touched_card_ids and not original_intro:
        print(f"  DONE: {name} — no changes applied")
        return False

    # Validate; revert any specific card that still fails a structural check, or whose reword
    # brought in another glossary term before it is taught. No validator result: revert it all.
    bad_ids = run_validate(course_dir)
    if bad_ids is None:
        reverted = set(touched_card_ids)
        for term, intro in original_intro.items():
            glossary_by_term[term]["introduced_by_card_id"] = intro
        reverted_terms = set(original_intro)
    else:
        new_groups, _, _ = find_forward_refs(course_dir)
        new_terms = {
            cid for cid in touched_card_ids
            if {t for t, _, _ in new_groups.get(cid, [])} - {t for t, _, _ in groups.get(cid, [])}
        }
        reverted = (bad_ids & touched_card_ids) | new_terms
        reverted_terms = set()
    for cid in reverted:
        cards_by_id[cid].clear()
        cards_by_id[cid].update(original[cid])
    if reverted:
        write_dict_csv(cards_path, card_fields, cards)
        print(f"  {name}: reverted {len(reverted)} card(s) that failed validation or the forward-ref re-check: {sorted(reverted)}")
    if reverted_terms:
        write_dict_csv(glossary_path, glossary_fields, glossary)
        print(f"  {name}: reverted {len(reverted_terms)} remap(s): {sorted(reverted_terms)}")

    residual, _, _ = find_forward_refs(course_dir)
    remapped = len(original_intro) - len(reverted_terms)
    print(f"  DONE: {name} — reworded {len(touched_card_ids - reverted)} card(s), remapped {remapped} term(s), "
          f"{len(residual)} card(s) still flagged")
    return True


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

    print(f"Fixing forward-references for {len(course_dirs)} course(s) with model={args.model}")
    failures = LlmFailures()
    for course_dir in course_dirs:
        fix_course(course_dir, args.model, args.batch_size, failures)
        if failures.tripped:
            sys.exit(1)


if __name__ == "__main__":
    main()
