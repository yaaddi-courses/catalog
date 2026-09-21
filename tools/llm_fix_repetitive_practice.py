#!/usr/bin/env python3
"""Local-LLM-assisted fixer for "repetitive_practice"-flagged cards — an
exercise that just restates its main card's rule instead of applying it
to a fresh, concrete scenario.

Highest-risk of the LLM fix passes in this repo, for two reasons:
  1. A "fresh example" can accidentally use a term/concept not yet
     taught at that point in the course (the exact bug class
     llm_fix_forward_refs.py exists to fix) — every course now has a
     complete glossary ledger, so this script re-runs
     check_key_term_usage.py after every write and reverts any card
     that introduced a NEW forward-reference (not just word-limit
     violations, unlike the other fix passes).
  2. A true/false card's fresh framing can flip the statement's truth
     value without the correct_index being updated to match (confirmed
     by hand-drafting 3 real examples before building this — see the
     conversation this was designed in). The model is told explicitly
     to keep the same correct answer; word-limit + forward-ref checks
     both apply, but a *silent* polarity flip that still validates is
     the one class of error neither check can catch — treat any single
     polarity-sensitive true/false rewrite with extra scrutiny if
     spot-checking output.

Grounds every rewrite in the SAME deterministic "taught so far" ledger
llm_review_pass.py already builds (each card's own prompt text, in
unit-then-id order) so the model has real material to build an example
from instead of guessing.

Usage:
    python tools/llm_fix_repetitive_practice.py <course-folder> [--batch-size 3]
    python tools/llm_fix_repetitive_practice.py --all [--batch-size 3]
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
    "You improve flashcard practice cards that just restate their main "
    "card's rule instead of applying it to a fresh, concrete scenario. "
    "For each card given (with its main card's rule and a list of "
    "concepts already taught earlier in the course, for grounding), "
    "rewrite ONLY the prompt (and options if it's multiple-choice/"
    "select_blank/multi_select) into a small concrete example or "
    "scenario that tests the SAME underlying rule. Hard requirements: "
    "the correct answer must stay exactly the same true fact — for a "
    "true/false card, if your new phrasing would flip whether the "
    "statement is true or false, rephrase it again until the polarity "
    "matches the original; never introduce any term or concept not in "
    "the taught-so-far list; prompt under 10 words, each option under "
    "3 words; do not change the number of options. If you cannot find "
    "a good concrete angle without breaking these rules, respond with "
    'SKIP for that card instead of forcing a bad rewrite. Respond ONLY '
    "with a JSON array, one object per card in the same order given, "
    'no markdown fences: {"card_id": "...", "action": "REWRITE" or '
    '"SKIP", "prompt": "..." (only for REWRITE, omit if unchanged), '
    '"options": "..." (only for REWRITE, omit if unchanged)}'
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


def valid_rewrite(new_prompt, new_options, orig_options):
    if isinstance(new_prompt, list):
        new_prompt = " ".join(str(x) for x in new_prompt)
    if isinstance(new_options, list):
        new_options = "|".join(str(x) for x in new_options)
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


def build_taught_list(units, cards):
    unit_order = {u["id"]: i for i, u in enumerate(units)}

    def sort_key(c):
        return (unit_order.get(c["unit_id"], 10**9), int(c["id"]))

    ordered = sorted(cards, key=sort_key)
    taught_at = {}
    taught_so_far = []
    for c in ordered:
        taught_at[c["id"]] = list(taught_so_far)
        if c.get("role") in ("main", "preview"):
            label = c.get("prompt", "").strip()
            if label:
                taught_so_far.append(label[:80])
    return taught_at


def format_group(card, main_card, taught_so_far):
    taught_block = "; ".join(taught_so_far[-30:]) or "(nothing yet)"
    return (
        f'card_id={card["id"]} type={card["type"]}\n'
        f'current prompt: {card.get("prompt","")}\n'
        f'current options: {card.get("options","")}\n'
        f'correct_index: {card.get("correct_index","")}\n'
        f'main card rule: {main_card.get("prompt","") if main_card else "(n/a)"} '
        f'-> {main_card.get("options","") if main_card else ""}\n'
        f'concepts taught so far (most recent last): {taught_block}'
    )


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


def run_forward_ref_check(course_dir):
    """Absolute-path, isolated invocation of check_key_term_usage.py —
    every course is confirmed clean before this script ever runs, so any
    card id mentioned here was necessarily broken by THIS pass."""
    abs_course_dir = os.path.abspath(course_dir)
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(tools_dir, "check_key_term_usage.py")
    result = subprocess.run(
        [sys.executable, script, abs_course_dir],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    bad_ids = set()
    for line in result.stdout.splitlines():
        m = re.search(r"card (\d+)", line)
        if line.strip().startswith("-") and m:
            bad_ids.add(m.group(1))
    return bad_ids


def fix_course(course_dir, model, batch_size):
    report_path = os.path.join(course_dir, ".internal", "llm_review_report.json")
    if not os.path.isfile(report_path):
        return False
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    units_fields, units = read_csv(os.path.join(course_dir, "source", "units.csv"))
    card_fields, cards = read_csv(os.path.join(course_dir, "source", "cards.csv"))
    if not cards:
        return False
    cards_by_id = {c["id"]: c for c in cards}
    taught_at = build_taught_list(units, cards)

    flagged_ids = [
        cid for cid, r in report.items()
        if r.get("repetitive_practice") and cid in cards_by_id
    ]
    if not flagged_ids:
        return False

    state_path = os.path.join(course_dir, ".internal", "llm_fix_repetitive_state.json")
    done = {}
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as f:
            done = json.load(f)
    todo = [cid for cid in flagged_ids if cid not in done]
    if not todo:
        print(f"  already processed ({len(flagged_ids)} cards): {os.path.basename(course_dir)}")
        return False

    name = os.path.basename(course_dir)
    print(f"  {name}: {len(todo)}/{len(flagged_ids)} repetitive-practice card(s)")

    cards_path = os.path.join(course_dir, "source", "cards.csv")
    original = {}
    touched = set()

    for i in range(0, len(todo), batch_size):
        batch_ids = todo[i : i + batch_size]
        blocks = []
        for cid in batch_ids:
            card = cards_by_id[cid]
            main_card = cards_by_id.get(card.get("related_main_id", ""))
            blocks.append(format_group(card, main_card, taught_at.get(cid, [])))
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
            done[cid] = True
            if not result or result.get("action") != "REWRITE":
                continue
            card = cards_by_id[cid]
            new_prompt = result.get("prompt")
            new_options = result.get("options")
            if isinstance(new_prompt, list):
                new_prompt = " ".join(str(x) for x in new_prompt)
            if isinstance(new_options, list):
                new_options = "|".join(str(x) for x in new_options)
            if not valid_rewrite(new_prompt, new_options, card.get("options", "")):
                continue
            original[cid] = dict(card)
            if new_prompt:
                card["prompt"] = new_prompt
            if new_options:
                card["options"] = new_options
            touched.add(cid)

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(done, f, ensure_ascii=False, indent=2)
        print(f"    batch {i}-{i+len(batch_ids)} done")

    if not touched:
        print(f"  DONE: {name} — no changes applied")
        return False

    tmp = cards_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=card_fields)
        w.writeheader()
        w.writerows(cards)
    os.replace(tmp, cards_path)

    bad_validate = run_validate(course_dir) & touched
    bad_forward_ref = run_forward_ref_check(course_dir) & touched
    reverted = bad_validate | bad_forward_ref
    if reverted:
        for cid in reverted:
            cards_by_id[cid].clear()
            cards_by_id[cid].update(original[cid])
        tmp = cards_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=card_fields)
            w.writeheader()
            w.writerows(cards)
        os.replace(tmp, cards_path)
        print(f"  {name}: reverted {len(reverted)} card(s) — validate:{sorted(bad_validate)} forward-ref:{sorted(bad_forward_ref)}")

    print(f"  DONE: {name} — rewrote {len(touched - reverted)} card(s)")
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

    print(f"Fixing repetitive-practice cards for {len(course_dirs)} course(s) with model={args.model}")
    for course_dir in course_dirs:
        fix_course(course_dir, args.model, args.batch_size)


if __name__ == "__main__":
    main()
