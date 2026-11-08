#!/usr/bin/env python3
"""Fixes a hand-curated list of cards confirmed (by a human/LLM triage
pass over check_self_standing.py's raw report) to genuinely rely on
unstated context — a bare "this/that/these" with no antecedent, an
unestablished course-specific metaphor, etc.

Deliberately does NOT read check_self_standing.py's raw report directly
— that report's LLM layer has a meaningful false-positive rate (see the
triage that produced the input list this script actually reads), so
this only touches cards a human confirmed are real. For each card, the
model sees its own text plus its related main card (and the preview card
of that same pack, for a metaphor-dependent case) so it has real
material to substitute the vague reference with instead of guessing.

Same safety net as llm_fix_forward_refs.py: rewrite pre-check
(llm_common.rewrite_problem: word limits, correct option kept, answer-bearing
options never touched), trusted validate_course.py re-check afterward,
per-card revert on failure (every touched card if the validator cannot run).

Input: a text file, one "course|card_id" pair per line ("#" starts a comment
line; any other malformed line is reported and skipped).

Usage:
    python tools/llm_fix_self_standing_confirmed.py <list.txt> [--batch-size 3] [--model NAME]
"""
import argparse
import os

import llm_common
from llm_common import DEFAULT_MODEL, LlmFailures, coerce_str, extract_json_array, rewrite_problem, write_dict_csv

BATCH_SIZE_DEFAULT = 3

SYSTEM_PROMPT = (
    "You fix flashcard prompts that rely on unstated context — a bare "
    "'this'/'that'/'these' with no antecedent in the card's own text, or "
    "an assumed analogy/metaphor/role the learner may not have seen "
    "recently, since a spaced-repetition app can resurface any card "
    "alone. For each card given, you see its own current text, its "
    "related main/pack card for grounding, and (if relevant) the "
    "preview card that may have established a metaphor. Rewrite ONLY "
    "what's necessary in the prompt (and options if needed) to name the "
    "actual referent directly, replacing the vague word. You MUST "
    "preserve the exact same correct answer and meaning. Hard limits: "
    "prompt under 10 words total, each option under 3 words. If you "
    "cannot fix it within these limits, respond with SKIP for that "
    "card instead of forcing a bad rewrite. Respond ONLY with a JSON "
    "array, one object per card in the same order given, no markdown "
    'fences: {"card_id": "...", "action": "REWRITE" or "SKIP", '
    '"prompt": "..." (only for REWRITE, omit if unchanged), "options": '
    '"..." (only for REWRITE, omit if unchanged)}'
)


def read_csv(path):
    return llm_common.read_csv(path)


def call_llm(model, user_content):
    return llm_common.call_llm(model, SYSTEM_PROMPT, user_content, temperature=0.2, max_tokens=2000)


def run_validate(course_dir):
    return llm_common.run_validate(course_dir)


def pack_preview(cards, main_card):
    """The preview card of main_card's own pack (its related_main_id), not just any preview in
    the same unit: a unit holds several packs."""
    return next((c for c in cards if c.get("role") == "preview" and c.get("related_main_id") == main_card["id"]), None)


def format_group(card, main_card, preview_card):
    lines = [
        f'card_id={card["id"]} type={card["type"]}',
        f'prompt: {card.get("prompt","")}',
        f'options: {card.get("options","")}',
    ]
    if main_card is not None:
        lines.append(f'related main card: {main_card.get("prompt","")} -> {main_card.get("options","")}')
    if preview_card is not None:
        lines.append(f'pack preview card: {preview_card.get("prompt","")} -> {preview_card.get("options","")}')
    return "\n".join(lines)


def fix_course(course_dir, card_ids, model, batch_size, failures=None):
    failures = failures or LlmFailures()
    card_fields, cards = read_csv(os.path.join(course_dir, "source", "cards.csv"))
    if not cards:
        return
    cards_by_id = {c["id"]: c for c in cards}

    name = os.path.basename(course_dir.rstrip("/\\"))
    todo = [cid for cid in card_ids if cid in cards_by_id]
    missing = [cid for cid in card_ids if cid not in cards_by_id]
    if missing:
        print(f"  {name}: WARNING card id(s) not found, skipping: {missing}")
    if not todo:
        return
    print(f"  {name}: {len(todo)} confirmed card(s) to fix")

    cards_path = os.path.join(course_dir, "source", "cards.csv")
    original = {}
    touched = set()
    skipped = []

    for i in range(0, len(todo), batch_size):
        batch_ids = todo[i : i + batch_size]
        blocks = []
        for cid in batch_ids:
            card = cards_by_id[cid]
            main_card = cards_by_id.get(card.get("related_main_id", ""))
            preview_card = pack_preview(cards, main_card) if main_card is not None else None
            blocks.append(format_group(card, main_card, preview_card))
        block = "\n---\n".join(blocks)
        try:
            raw = call_llm(model, block)
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
        for cid in batch_ids:
            result = result_by_id.get(cid)
            if not result or result.get("action") != "REWRITE":
                skipped.append(cid)
                continue
            card = cards_by_id[cid]
            new_prompt = coerce_str(result.get("prompt"))
            new_options = coerce_str(result.get("options"), "|")
            if rewrite_problem(card, new_prompt, new_options):
                skipped.append(cid)
                continue
            original.setdefault(cid, dict(card))
            if new_prompt:
                card["prompt"] = new_prompt
            if new_options:
                card["options"] = new_options
            touched.add(cid)

        print(f"    batch {i}-{i+len(batch_ids)} done")

    if not touched:
        print(f"  DONE: {name} — no changes applied, {len(skipped)} skipped")
        return

    write_dict_csv(cards_path, card_fields, cards)

    bad = run_validate(course_dir)
    bad_ids = set(touched) if bad is None else bad & touched
    if bad_ids:
        for cid in bad_ids:
            cards_by_id[cid].clear()
            cards_by_id[cid].update(original[cid])
        write_dict_csv(cards_path, card_fields, cards)
        print(f"  {name}: reverted {len(bad_ids)} card(s) that failed validation: {sorted(bad_ids)}")

    fixed = touched - bad_ids
    print(f"  DONE: {name} — fixed {len(fixed)} card(s), skipped {len(skipped)}, reverted {len(bad_ids)}")


def read_card_list(path):
    """{course: [card_id, ...]} from a "course|card_id" list; blank and "#" lines are ignored and
    any other line that is not exactly two non-empty fields is reported and skipped."""
    by_course = {}
    with open(path, encoding="utf-8-sig") as f:
        for n, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 2 or not all(parts):
                print(f"  WARNING: skipping line {n} (expected course|card_id): {line[:80]!r}")
                continue
            by_course.setdefault(parts[0], []).append(parts[1])
    return by_course


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list_file")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    by_course = read_card_list(args.list_file)

    print(f"Fixing {sum(len(v) for v in by_course.values())} confirmed card(s) across {len(by_course)} course(s) with model={args.model}")
    failures = LlmFailures()
    for course, ids in by_course.items():
        fix_course(course, ids, args.model, args.batch_size, failures)
        if failures.tripped:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
