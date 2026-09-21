#!/usr/bin/env python3
"""Local-LLM-assisted bulk review pass: flags forward-referenced concepts
(including paraphrased ones a plain glossary-term matcher would miss),
missing/generic explanations, robotic phrasing, and exercise cards that
just restate the main card's rule instead of giving a fresh example —
across an entire course, or every course.

This is a FLAGGING tool, not an auto-fixer: it writes a JSON report per
course to <course>/.internal/llm_review_report.json for a human (or the
flashcard-course-reviewer agent) to act on. It never edits cards.csv.

Uses LM Studio's local OpenAI-compatible server (http://127.0.0.1:1234) —
nothing leaves the machine, no API cost. Model chosen after a quick manual
comparison (see conversation): "google/gemma-4-e4b" gave correct, complete
judgment in ~15s; a "thinking" model (glm-4.7-flash) was far too slow/
verbose for bulk use, and a plain small coder model (qwen2.5-coder-7b)
was fast but missed real issues.

Resumable: writes progress after every batch, and --resume skips cards
already covered in an existing report for that course — safe to stop and
restart across a long unattended run.

Usage:
    python tools/llm_review_pass.py <course-folder> [--batch-size 6] [--model NAME]
    python tools/llm_review_pass.py --all [--batch-size 6] [--model NAME]
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_MODEL = "google/gemma-4-e4b"
BATCH_SIZE_DEFAULT = 6

SYSTEM_PROMPT = (
    "You are a precise, skeptical flashcard-course reviewer. For each card "
    "given, judge it against the list of concepts already taught earlier "
    "in the SAME course (in teaching order). Respond ONLY with a JSON array, "
    "one object per card in the same order given, no markdown fences, no "
    "commentary outside the JSON. Each object: "
    '{"card_id": "...", "forward_references": [untaught terms/concepts the '
    "card's own text uses as if the learner already knows them — include "
    "paraphrases, not just exact glossary-term matches], "
    '"missing_or_generic_explanation": true/false (true if explanation is '
    "blank AND the card isn't trivially self-evident, OR present but pure "
    'filler like "Great job!" with no real reasoning), '
    '"robotic_phrasing": true/false (stiff, textbook, unnatural phrasing '
    "a real person wouldn't write), "
    '"repetitive_practice": true/false (ONLY for role=exercise cards: true '
    "if it just restates the main card's rule/definition instead of a "
    'fresh concrete example/scenario to apply it to), '
    '"reasoning": "one short sentence"}'
)


def read_csv(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def call_llm(model, user_content, max_tokens=2800, retries=3):
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
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
        except Exception as e:  # noqa: BLE001 — bulk unattended run, log & retry
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LM Studio call failed after {retries} attempts: {last_err}")


def extract_json_array(text):
    """The model sometimes wraps output in stray text despite instructions —
    grab the first [...] block rather than assuming the whole string parses."""
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


def build_taught_list(units, cards):
    """Deterministic 'taught so far' ledger per card position, reusing the
    same first-main/preview-occurrence heuristic as propose_term_ledger.py
    — cheap, no LLM call needed, and gives the model real grounding instead
    of relying on it to track everything itself across a huge course."""
    unit_order = {u["id"]: i for i, u in enumerate(units)}

    def sort_key(c):
        return (unit_order.get(c["unit_id"], 10**9), int(c["id"]))

    ordered = sorted(cards, key=sort_key)
    taught_at = {}  # card_id -> list of concept strings taught strictly before it
    taught_so_far = []
    for c in ordered:
        taught_at[c["id"]] = list(taught_so_far)
        if c.get("role") in ("main", "preview"):
            # Use the card's own prompt as a rough "concept label" — good
            # enough grounding; the LLM does the real judgment, this just
            # keeps it from having to infer the entire course history.
            label = c.get("prompt", "").strip()
            if label:
                taught_so_far.append(label[:80])
    return ordered, taught_at


def format_card(c):
    return (
        f'id={c["id"]} role={c["role"]} type={c["type"]}\n'
        f'prompt: {c.get("prompt","")}\n'
        f'options: {c.get("options","")}\n'
        f'explanation: {c.get("explanation","") or "(blank)"}'
    )


def review_course(course_dir, model, batch_size, resume):
    units = read_csv(os.path.join(course_dir, "source", "units.csv"))
    cards = read_csv(os.path.join(course_dir, "source", "cards.csv"))
    if not cards:
        print(f"  skip (no cards.csv): {course_dir}")
        return

    ordered, taught_at = build_taught_list(units, cards)

    internal_dir = os.path.join(course_dir, ".internal")
    os.makedirs(internal_dir, exist_ok=True)
    report_path = os.path.join(internal_dir, "llm_review_report.json")

    report = {}
    if resume and os.path.isfile(report_path):
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)

    already_done = set(report.keys())
    todo = [c for c in ordered if c["id"] not in already_done]
    if not todo:
        print(f"  already fully reviewed ({len(ordered)} cards): {os.path.basename(course_dir)}")
        return

    print(f"  {os.path.basename(course_dir)}: {len(todo)}/{len(ordered)} cards to review")

    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        # Use the LATEST card in the batch's taught-so-far list — a safe
        # upper bound since earlier cards in the same batch have a subset.
        taught_so_far = taught_at[batch[-1]["id"]]
        taught_block = "; ".join(taught_so_far[-40:]) or "(nothing yet — this is the start of the course)"
        cards_block = "\n---\n".join(format_card(c) for c in batch)
        user_content = (
            f"Concepts taught so far, in order (most recent last, truncated to last 40): {taught_block}\n\n"
            f"Cards to review:\n{cards_block}"
        )
        try:
            raw = call_llm(model, user_content)
            parsed = extract_json_array(raw)
        except Exception as e:  # noqa: BLE001
            print(f"    batch {i}-{i+len(batch)} FAILED: {e}")
            continue

        if not parsed:
            print(f"    batch {i}-{i+len(batch)}: could not parse model output, skipping")
            continue

        by_id = {str(item.get("card_id")): item for item in parsed if isinstance(item, dict)}
        for c in batch:
            result = by_id.get(c["id"])
            if result is None:
                continue
            report[c["id"]] = {
                "unit_id": c["unit_id"],
                "role": c["role"],
                "prompt": c.get("prompt", "")[:100],
                **{k: v for k, v in result.items() if k != "card_id"},
            }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"    batch {i}-{i+len(batch)} done ({len(report)}/{len(ordered)} total)")

    flagged = [
        cid
        for cid, r in report.items()
        if r.get("forward_references")
        or r.get("missing_or_generic_explanation")
        or r.get("robotic_phrasing")
        or r.get("repetitive_practice")
    ]
    print(f"  DONE: {os.path.basename(course_dir)} — {len(flagged)}/{len(report)} cards flagged, report at {report_path}")


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
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    args = ap.parse_args()

    if args.all:
        course_dirs = find_all_course_dirs(os.getcwd())
    elif args.course:
        course_dirs = [args.course]
    else:
        ap.error("pass a course folder or --all")
        return

    print(f"Reviewing {len(course_dirs)} course(s) with model={args.model}, batch_size={args.batch_size}")
    for course_dir in course_dirs:
        review_course(course_dir, args.model, args.batch_size, args.resume)


if __name__ == "__main__":
    main()
