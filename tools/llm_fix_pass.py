#!/usr/bin/env python3
"""Local-LLM-assisted bulk FIX pass — companion to llm_review_pass.py.

llm_review_pass.py only flags issues; this script actually writes fixes
for the "missing_or_generic_explanation" category, which review sampling
confirmed is real signal (every sampled flagged card had a genuinely
blank explanation field, not a false positive). For each flagged card it
asks the local LLM for one short, natural-language sentence explaining
WHY the correct answer is right (not a motivational filler line — the
app already shows a default encouraging sentence when explanation is
blank, so a written explanation should always add real reasoning).

Does NOT touch robotic_phrasing or repetitive_practice — those need
free rewriting of prompt/options text, which is higher-risk to do
unsupervised at this scale and is a separate, slower pass.

Resumable: tracks completed card ids in
<course>/.internal/llm_fix_state.json, safe to stop and restart. A flag whose
card's explanation was edited since the review is skipped as stale.

Usage:
    python tools/llm_fix_pass.py <course-folder> [--batch-size 5] [--model NAME]
    python tools/llm_fix_pass.py --all [--batch-size 5] [--model NAME]
"""
import argparse
import os
import sys

import llm_common
from llm_common import (
    DEFAULT_MODEL, LlmFailures, coerce_str, extract_json_array, find_all_course_dirs, load_json,
    review_entry_current, save_json, write_dict_csv,
)

BATCH_SIZE_DEFAULT = 5

SYSTEM_PROMPT = (
    "You write short, natural, humanized explanations for flashcard app "
    "cards. For each card given, write ONE explanation: why the correct "
    "answer is actually right (and, if it clarifies things, briefly why "
    "the obvious wrong answer is wrong). Write like a knowledgeable "
    "person explaining it to a friend — never robotic, never generic "
    "praise like 'Great job!' or 'Keep practicing!', never restate the "
    "prompt. 1-2 sentences, plain text, no markdown. If the card already "
    "has an existing (but weak) explanation, replace it with a better "
    "one — don't just pad it. Respond ONLY with a JSON array, one object "
    'per card in the same order given, no markdown fences: '
    '{"card_id": "...", "explanation": "..."}'
)

# cloze_passage encodes a SEPARATE correct answer per blank as nested
# pipe/tilde-delimited sub-lists (e.g. options "choice|Excuse me~Hello~No|..."
# correct_index "2|0|1") — a format this script's plain card formatter
# doesn't parse, which produced confidently wrong explanations that
# didn't match the actual per-blank answer (caught by manual review
# before anything shipped). Skip it rather than risk shipping a wrong
# explanation; it would need a dedicated per-blank formatter to be safe.
UNSAFE_TYPES = {"cloze_passage"}


def read_csv(path):
    return llm_common.read_csv(path)


def call_llm(model, user_content):
    return llm_common.call_llm(model, SYSTEM_PROMPT, user_content, temperature=0.3, max_tokens=1600)


def format_card(c):
    return (
        f'id={c["id"]} type={c["type"]}\n'
        f'prompt: {c.get("prompt","")}\n'
        f'options: {c.get("options","")}\n'
        f'correct_index: {c.get("correct_index","")}\n'
        f'current explanation: {c.get("explanation","") or "(blank)"}'
    )


def fix_course(course_dir, model, batch_size, failures=None):
    failures = failures or LlmFailures()
    cards_path = os.path.join(course_dir, "source", "cards.csv")
    fieldnames, cards = read_csv(cards_path)
    if not cards:
        print(f"  skip (no cards.csv): {course_dir}")
        return False

    report_path = os.path.join(course_dir, ".internal", "llm_review_report.json")
    if not os.path.isfile(report_path):
        print(f"  skip (no review report yet): {os.path.basename(course_dir)}")
        return False
    report = load_json(report_path, {})

    by_id = {c["id"]: c for c in cards}
    flagged_ids = [
        cid for cid, r in report.items()
        if r.get("missing_or_generic_explanation")
        and cid in by_id
        and by_id[cid]["type"] not in UNSAFE_TYPES
        and review_entry_current(r, by_id[cid], parts=("explanation",))
    ]

    state_path = os.path.join(course_dir, ".internal", "llm_fix_state.json")
    done = load_json(state_path, {})

    todo = [cid for cid in flagged_ids if cid not in done]
    if not todo:
        print(f"  already fixed ({len(flagged_ids)} cards): {os.path.basename(course_dir)}")
        return False

    print(f"  {os.path.basename(course_dir)}: {len(todo)}/{len(flagged_ids)} explanations to write")

    changed = False
    for i in range(0, len(todo), batch_size):
        batch_ids = todo[i : i + batch_size]
        batch_cards = [by_id[cid] for cid in batch_ids]
        cards_block = "\n---\n".join(format_card(c) for c in batch_cards)
        try:
            raw = call_llm(model, cards_block)
        except Exception as e:  # noqa: BLE001
            print(f"    batch {i}-{i+len(batch_ids)} FAILED: {e}")
            if failures.failed():
                break
            continue
        failures.ok()
        parsed = extract_json_array(raw)
        if not parsed:
            print(f"    batch {i}-{i+len(batch_ids)}: could not parse model output, skipping")
            continue

        result_by_id = {str(item.get("card_id")): item for item in parsed if isinstance(item, dict)}
        batch_done = []
        for cid in batch_ids:
            explanation = coerce_str((result_by_id.get(cid) or {}).get("explanation"))
            if not explanation:
                continue
            by_id[cid]["explanation"] = explanation
            batch_done.append(cid)
            changed = True

        # cards.csv first (atomic), then the state: a crash in between leaves a card
        # re-done, never marked done without its edit.
        if batch_done:
            write_dict_csv(cards_path, fieldnames, cards)
            done.update({cid: True for cid in batch_done})
            save_json(state_path, done)

        print(f"    batch {i}-{i+len(batch_ids)} done ({len(done)}/{len(flagged_ids)} total)")

    print(f"  DONE: {os.path.basename(course_dir)} — wrote {len(done)} explanations")
    return changed


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

    print(f"Fixing {len(course_dirs)} course(s) with model={args.model}, batch_size={args.batch_size}")
    failures = LlmFailures()
    for course_dir in course_dirs:
        fix_course(course_dir, args.model, args.batch_size, failures)
        if failures.tripped:
            sys.exit(1)


if __name__ == "__main__":
    main()
