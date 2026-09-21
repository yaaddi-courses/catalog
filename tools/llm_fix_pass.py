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
<course>/.internal/llm_fix_state.json, safe to stop and restart.

Usage:
    python tools/llm_fix_pass.py <course-folder> [--batch-size 5] [--model NAME]
    python tools/llm_fix_pass.py --all [--batch-size 5] [--model NAME]
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
        "temperature": 0.3,
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
        f'options: {c.get("options","")}\n'
        f'correct_index: {c.get("correct_index","")}\n'
        f'current explanation: {c.get("explanation","") or "(blank)"}'
    )


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

    # cloze_passage encodes a SEPARATE correct answer per blank as nested
    # pipe/tilde-delimited sub-lists (e.g. options "choice|Excuse me~Hello~No|..."
    # correct_index "2|0|1") — a format this script's plain card formatter
    # doesn't parse, which produced confidently wrong explanations that
    # didn't match the actual per-blank answer (caught by manual review
    # before anything shipped). Skip it rather than risk shipping a wrong
    # explanation; it would need a dedicated per-blank formatter to be safe.
    UNSAFE_TYPES = {"cloze_passage"}

    by_id = {c["id"]: c for c in cards}
    flagged_ids = [
        cid for cid, r in report.items()
        if r.get("missing_or_generic_explanation")
        and cid in by_id
        and by_id[cid]["type"] not in UNSAFE_TYPES
    ]

    state_path = os.path.join(course_dir, ".internal", "llm_fix_state.json")
    done = {}
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as f:
            done = json.load(f)

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
            if not result or not result.get("explanation"):
                continue
            by_id[cid]["explanation"] = result["explanation"].strip()
            done[cid] = True
            changed = True

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(done, f, ensure_ascii=False, indent=2)
        # Persist cards.csv after every batch too — safe to interrupt.
        # Write to a temp file and atomically replace so a crash mid-write
        # (or a stray malformed row DictWriter can't place) never leaves
        # cards.csv truncated — os.replace is atomic on the same volume.
        if changed:
            tmp_path = cards_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(cards)
            os.replace(tmp_path, cards_path)

        print(f"    batch {i}-{i+len(batch_ids)} done ({len(done)}/{len(flagged_ids)} total)")

    print(f"  DONE: {os.path.basename(course_dir)} — wrote {len(done)} explanations")
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

    print(f"Fixing {len(course_dirs)} course(s) with model={args.model}, batch_size={args.batch_size}")
    for course_dir in course_dirs:
        fix_course(course_dir, args.model, args.batch_size)


if __name__ == "__main__":
    main()
