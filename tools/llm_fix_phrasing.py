#!/usr/bin/env python3
"""Local-LLM-assisted bulk FIX pass for "robotic_phrasing"-flagged cards.

Companion to llm_fix_pass.py (which handles missing_or_generic_explanation).
This one rewords a card's prompt/options into natural, humanized language
while preserving EXACT meaning and the correct answer — it must never
change what's being asked or which option is correct.

Hard constraints enforced by the app/validator that the model is told
about explicitly: prompt <= 10 words, each option <= 3 words. Any card
whose rewrite violates this (or breaks the option count) is left
unchanged and printed as a manual-review line, rather than silently
written — safer than risking a validate_course.py failure or, worse, a
passing-but-wrong card.

Resumable: tracks completed card ids in
<course>/.internal/llm_fix_phrasing_state.json.

Usage:
    python tools/llm_fix_phrasing.py <course-folder> [--batch-size 4] [--model NAME]
    python tools/llm_fix_phrasing.py --all [--batch-size 4] [--model NAME]
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_MODEL = "google/gemma-4-e4b"
BATCH_SIZE_DEFAULT = 4
MAX_PROMPT_WORDS = 10
MAX_OPTION_WORDS = 3

SYSTEM_PROMPT = (
    "You reword stiff, robotic, textbook-sounding flashcard text into "
    "natural language a real person would actually write — without "
    "changing the meaning, the facts, or which option is correct. Hard "
    "rules: the prompt must stay under 10 words total; each option "
    "(pipe-separated) must stay under 3 words; do not add or remove "
    "options; do not change which option index is correct; do not "
    "introduce any technical term that wasn't already in the original "
    "text. If a card's phrasing is already fine, keep it unchanged "
    "rather than forcing a pointless edit. Respond ONLY with a JSON "
    "array, one object per card in the same order given, no markdown "
    'fences: {"card_id": "...", "prompt": "...", "options": "..."} '
    "(options as the same pipe-separated format given)."
)


def read_csv(path):
    """Returns (fieldnames, rows). Raises if any row has more columns than
    the header — a malformed row (usually an unescaped comma in some
    field) must never be silently written back out, since DictWriter has
    no fieldname for the overflow and would crash mid-write, truncating
    the file. Fail fast, before anything is touched, instead."""
    if not os.path.isfile(path):
        return [], []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, restkey="_extra")
        fieldnames = reader.fieldnames
        rows = list(reader)
    bad = [r.get("id") for r in rows if r.get("_extra")]
    if bad:
        raise ValueError(
            f"{path}: malformed row(s) with extra columns (id={bad}) — "
            "likely an unescaped comma in a field. Fix the CSV by hand "
            "before running this script."
        )
    return fieldnames, rows


def call_llm(model, user_content, max_tokens=1600, retries=3):
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
            with urllib.request.urlopen(req, timeout=180) as resp:  # nosec B310  # URL is a fixed constant / operator config, not user input
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LM Studio call failed after {retries} attempts: {last_err}")


def extract_json_array(text):
    text = text.strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def format_card(c):
    return (
        f'id={c["id"]} type={c["type"]}\n'
        f'prompt: {c.get("prompt","")}\n'
        f'options: {c.get("options","")}'
    )


def valid_rewrite(original, new_prompt, new_options):
    if not new_prompt or not new_options:
        return False
    if len(new_prompt.split()) > MAX_PROMPT_WORDS:
        return False
    orig_opts = original.get("options", "").split("|")
    new_opts = new_options.split("|")
    if len(orig_opts) != len(new_opts):
        return False
    for o in new_opts:
        if len(o.split(":", 1)[-1].split()) > MAX_OPTION_WORDS:
            return False
    return True


def fix_course(course_dir, model, batch_size):
    cards_path = os.path.join(course_dir, "source", "cards.csv")
    fieldnames, cards = read_csv(cards_path)
    if not cards:
        print(f"  skip (no cards.csv): {course_dir}")
        return False

    report_path = os.path.join(course_dir, ".internal", "llm_review_report.json")
    if not os.path.isfile(report_path):
        print(f"  skip (no review report yet): {os.path.basename(course_dir)}")
        return False
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    by_id = {c["id"]: c for c in cards}
    flagged_ids = [
        cid for cid, r in report.items()
        if r.get("robotic_phrasing") and cid in by_id
    ]
    if not flagged_ids:
        print(f"  no robotic_phrasing flags: {os.path.basename(course_dir)}")
        return False

    state_path = os.path.join(course_dir, ".internal", "llm_fix_phrasing_state.json")
    done = {}
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as f:
            done = json.load(f)

    todo = [cid for cid in flagged_ids if cid not in done]
    if not todo:
        print(f"  already fixed ({len(flagged_ids)} cards): {os.path.basename(course_dir)}")
        return False

    print(f"  {os.path.basename(course_dir)}: {len(todo)}/{len(flagged_ids)} phrasing rewrites")

    changed = False
    manual_review = []
    for i in range(0, len(todo), batch_size):
        batch_ids = todo[i : i + batch_size]
        batch_cards = [by_id[cid] for cid in batch_ids]
        cards_block = "\n---\n".join(format_card(c) for c in batch_cards)
        try:
            raw = call_llm(model, cards_block)
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
            done[cid] = True
            if not result:
                continue
            original = by_id[cid]
            new_prompt = (result.get("prompt") or "").strip()
            new_options = (result.get("options") or "").strip()
            if not valid_rewrite(original, new_prompt, new_options):
                manual_review.append(cid)
                continue
            if new_prompt != original["prompt"] or new_options != original["options"]:
                original["prompt"] = new_prompt
                original["options"] = new_options
                changed = True

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(done, f, ensure_ascii=False, indent=2)
        # Atomic write (temp file + replace) so a crash mid-write never
        # leaves cards.csv truncated.
        if changed:
            tmp_path = cards_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(cards)
            os.replace(tmp_path, cards_path)

        print(f"    batch {i}-{i+len(batch_ids)} done ({len(done)}/{len(flagged_ids)} total)")

    if manual_review:
        print(f"  {os.path.basename(course_dir)}: {len(manual_review)} card(s) skipped, rewrite violated limits: {manual_review}")
    print(f"  DONE: {os.path.basename(course_dir)} — rewrote phrasing on {len(done) - len(manual_review)} card(s)")
    return changed


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
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    if args.all:
        course_dirs = find_all_course_dirs(os.getcwd())
    elif args.course:
        course_dirs = [args.course]
    else:
        ap.error("pass a course folder or --all")
        return

    print(f"Rewording {len(course_dirs)} course(s) with model={args.model}, batch_size={args.batch_size}")
    for course_dir in course_dirs:
        fix_course(course_dir, args.model, args.batch_size)


if __name__ == "__main__":
    main()
