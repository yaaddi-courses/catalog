#!/usr/bin/env python3
"""Fixes a hand-curated list of cards confirmed (by a human/Claude triage
pass over check_self_standing.py's raw report) to genuinely rely on
unstated context — a bare "this/that/these" with no antecedent, an
unestablished course-specific metaphor, etc.

Deliberately does NOT read check_self_standing.py's raw report directly
— that report's LLM layer has a meaningful false-positive rate (see the
triage that produced the input list this script actually reads), so
this only touches cards a human confirmed are real. For each card, the
model sees its own text plus its related main card (and, for a
metaphor-dependent case, the pack's preview/main text) so it has real
material to substitute the vague reference with instead of guessing.

Same safety net as llm_fix_forward_refs.py: word-limit pre-check,
validate_course.py re-check afterward, per-card revert on failure.

Input: a text file, one "course|card_id" pair per line.

Usage:
    python tools/llm_fix_self_standing_confirmed.py <list.txt> [--batch-size 3] [--model NAME]
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_MODEL = "google/gemma-4-e4b"
BATCH_SIZE_DEFAULT = 3
MAX_PROMPT_WORDS = 10
MAX_OPTION_WORDS = 3

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
    if not os.path.isfile(path):
        return [], []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, restkey="_extra")
        fieldnames = reader.fieldnames
        rows = list(reader)
    bad = [r.get("id") for r in rows if r.get("_extra")]
    if bad:
        raise ValueError(f"{path}: malformed row(s) with extra columns (id={bad})")
    return fieldnames, rows


def call_llm(model, user_content, max_tokens=2000, retries=3):
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        LM_STUDIO_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LM Studio call failed after {retries} attempts: {last_err}")


def extract_json_array(text):
    text = text.strip()
    # Strip a markdown code fence if the model added one despite being
    # told not to (```json ... ``` or bare ``` ... ```).
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    # A single-item batch sometimes comes back as a bare object instead
    # of a 1-element array, despite the instruction — wrap it.
    if text.startswith("{"):
        try:
            return [json.loads(text)]
        except json.JSONDecodeError:
            pass
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return [json.loads(match.group(0))]
        except json.JSONDecodeError:
            return None
    return None


def coerce_str(v, sep=" "):
    if isinstance(v, list):
        return sep.join(str(x) for x in v)
    return v


def valid_rewrite(new_prompt, new_options, orig_options):
    if new_prompt is not None and len(new_prompt.split()) > MAX_PROMPT_WORDS:
        return False
    if new_options is not None:
        orig_n = len(orig_options.split("|")) if orig_options else 0
        new_opts = new_options.split("|")
        if orig_n and len(new_opts) != orig_n:
            return False
        for o in new_opts:
            if len(o.split(":", 1)[-1].split()) > MAX_OPTION_WORDS:
                return False
    return True


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


def run_validate(course_dir):
    abs_course_dir = os.path.abspath(course_dir)
    script = os.path.join(abs_course_dir, "validate_course.py")
    if not os.path.isfile(script):
        print(f"    WARNING: validate_course.py not found at {script}")
        return set()
    result = subprocess.run(
        [sys.executable, script, ".", "--source"],
        cwd=abs_course_dir, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    bad_ids = set()
    for line in result.stdout.splitlines():
        m = re.search(r"card (\d+)", line)
        if "[ERROR]" in line and m:
            bad_ids.add(m.group(1))
    return bad_ids


def fix_course(course_dir, card_ids, model, batch_size):
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
            preview_card = None
            if main_card is not None:
                # find a preview card in the same unit as the main card
                for c in cards:
                    if c.get("role") == "preview" and c["unit_id"] == main_card["unit_id"]:
                        preview_card = c
                        break
            blocks.append(format_group(card, main_card, preview_card))
        block = "\n---\n".join(blocks)
        try:
            raw = call_llm(model, block)
            parsed = extract_json_array(raw)
        except Exception as e:  # noqa: BLE001
            print(f"    batch {i}-{i+len(batch_ids)} FAILED: {e}")
            continue
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
            new_options = coerce_str(result.get("options"))
            if not valid_rewrite(new_prompt, new_options, card.get("options", "")):
                skipped.append(cid)
                continue
            original[cid] = dict(card)
            if new_prompt:
                card["prompt"] = new_prompt
            if new_options:
                card["options"] = new_options
            touched.add(cid)

        print(f"    batch {i}-{i+len(batch_ids)} done")

    if not touched:
        print(f"  DONE: {name} — no changes applied, {len(skipped)} skipped")
        return

    tmp = cards_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=card_fields)
        w.writeheader()
        w.writerows(cards)
    os.replace(tmp, cards_path)

    bad_ids = run_validate(course_dir) & touched
    if bad_ids:
        for cid in bad_ids:
            cards_by_id[cid].clear()
            cards_by_id[cid].update(original[cid])
        tmp = cards_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=card_fields)
            w.writeheader()
            w.writerows(cards)
        os.replace(tmp, cards_path)
        print(f"  {name}: reverted {len(bad_ids)} card(s) that failed validation: {sorted(bad_ids)}")

    fixed = touched - bad_ids
    print(f"  DONE: {name} — fixed {len(fixed)} card(s), skipped {len(skipped)}, reverted {len(bad_ids)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list_file")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    by_course = {}
    with open(args.list_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            course, cid = line.split("|")
            by_course.setdefault(course, []).append(cid)

    print(f"Fixing {sum(len(v) for v in by_course.values())} confirmed card(s) across {len(by_course)} course(s) with model={args.model}")
    for course, ids in by_course.items():
        fix_course(course, ids, args.model, args.batch_size)


if __name__ == "__main__":
    main()
