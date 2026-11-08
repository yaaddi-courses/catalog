#!/usr/bin/env python3
"""Local-LLM-assisted bulk FIX pass for "robotic_phrasing"-flagged cards.

Companion to llm_fix_pass.py (which handles missing_or_generic_explanation).
This one rewords a card's prompt/options into natural, humanized language
while preserving EXACT meaning and the correct answer — it must never
change what's being asked or which option is correct.

Hard constraints enforced by the app/validator that the model is told
about explicitly: prompt <= 10 words, each option <= 3 words. Any card
whose rewrite violates this, breaks the option count, changes the correct
option's text or position, or touches options that ARE the answer (type_answer,
order, match_pairs, listening_card, ...; see llm_common.rewrite_problem) is
left unchanged and printed as a manual-review line, rather than silently
written — safer than risking a validate_course.py failure or, worse, a
passing-but-wrong card.

Resumable: tracks completed card ids in
<course>/.internal/llm_fix_phrasing_state.json (only cards whose result was
written; a rejected rewrite is tried again on the next run).

Usage:
    python tools/llm_fix_phrasing.py <course-folder> [--batch-size 4] [--model NAME]
    python tools/llm_fix_phrasing.py --all [--batch-size 4] [--model NAME]
"""
import argparse
import os
import sys

import llm_common
from llm_common import (
    DEFAULT_MODEL, PROMPT_REWRITE_TYPES, LlmFailures, coerce_str, extract_json_array, find_all_course_dirs,
    load_json, review_entry_current, rewrite_problem, save_json, write_dict_csv,
)

BATCH_SIZE_DEFAULT = 4

SYSTEM_PROMPT = (
    "You reword stiff, robotic, textbook-sounding flashcard text into "
    "natural language a real person would actually write — without "
    "changing the meaning, the facts, or which option is correct. Hard "
    "rules: the prompt must stay under 10 words total; each option "
    "(pipe-separated) must stay under 3 words; do not add or remove "
    "options; do not change which option index is correct, and keep the "
    "correct option's text exactly as it is; do not "
    "introduce any technical term that wasn't already in the original "
    "text. If a card's phrasing is already fine, keep it unchanged "
    "rather than forcing a pointless edit. Respond ONLY with a JSON "
    "array, one object per card in the same order given, no markdown "
    'fences: {"card_id": "...", "prompt": "...", "options": "..."} '
    "(options as the same pipe-separated format given)."
)


def read_csv(path):
    return llm_common.read_csv(path)


def call_llm(model, user_content):
    return llm_common.call_llm(model, SYSTEM_PROMPT, user_content, temperature=0.2, max_tokens=1600)


def format_card(c):
    return (
        f'id={c["id"]} type={c["type"]}\n'
        f'prompt: {c.get("prompt","")}\n'
        f'options: {c.get("options","")}'
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
        if r.get("robotic_phrasing") and cid in by_id
        and by_id[cid].get("type") in PROMPT_REWRITE_TYPES
        and review_entry_current(r, by_id[cid], parts=("question",))
    ]
    if not flagged_ids:
        print(f"  no robotic_phrasing flags: {os.path.basename(course_dir)}")
        return False

    state_path = os.path.join(course_dir, ".internal", "llm_fix_phrasing_state.json")
    done = load_json(state_path, {})

    todo = [cid for cid in flagged_ids if cid not in done]
    if not todo:
        print(f"  already fixed ({len(flagged_ids)} cards): {os.path.basename(course_dir)}")
        return False

    print(f"  {os.path.basename(course_dir)}: {len(todo)}/{len(flagged_ids)} phrasing rewrites")

    changed = False
    rewritten = 0
    manual_review = []
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
            result = result_by_id.get(cid)
            if not result:
                continue  # no answer for this card: tried again next run
            original = by_id[cid]
            new_prompt = coerce_str(result.get("prompt")) or original["prompt"]
            new_options = coerce_str(result.get("options"), "|") or original["options"]
            problem = rewrite_problem(original, new_prompt, new_options)
            if problem:
                manual_review.append((cid, problem))
                continue
            if new_prompt != original["prompt"] or new_options != original["options"]:
                original["prompt"] = new_prompt
                original["options"] = new_options
                changed = True
                rewritten += 1
            batch_done.append(cid)

        # cards.csv first (atomic), then the state.
        if batch_done:
            if changed:
                write_dict_csv(cards_path, fieldnames, cards)
            done.update({cid: True for cid in batch_done})
            save_json(state_path, done)

        print(f"    batch {i}-{i+len(batch_ids)} done ({len(done)}/{len(flagged_ids)} total)")

    if manual_review:
        print(f"  {os.path.basename(course_dir)}: {len(manual_review)} card(s) skipped, rewrite rejected: {manual_review}")
    print(f"  DONE: {os.path.basename(course_dir)} — rewrote phrasing on {rewritten} card(s)")
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

    print(f"Rewording {len(course_dirs)} course(s) with model={args.model}, batch_size={args.batch_size}")
    failures = LlmFailures()
    for course_dir in course_dirs:
        fix_course(course_dir, args.model, args.batch_size, failures)
        if failures.tripped:
            sys.exit(1)


if __name__ == "__main__":
    main()
