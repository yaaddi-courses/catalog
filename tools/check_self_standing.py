#!/usr/bin/env python3
"""Flags cards whose prompt+options can't be answered on their own,
without hidden context from a nearby card — the exact bug class of
"What's the general term for this idea?" (found by hand in
concurrency-in-python's card 5): a spaced-repetition app can resurface
any card alone, so "this idea"/"these"/"that" with no antecedent on the
card itself is a real defect, not just style.

Uses a small, fast local model (qwen2.5-coder-7b-instruct) for a cheap
per-card true/false classification instead of a human (or a slower,
more expensive model) reading every card — the question asked is
literally the one confirmed to work:

    "respond with true if it is self standing clear and without any
    additional context it can be responded and say false if not"

This is a FLAGGING tool, not an auto-fixer: it never edits cards.csv.
It writes only the FLAGGED (false) cards to a single, easy-to-grep
report file so a human or an LLM assistant can find and fix each one — for a
flagged card, the line has course + card id + prompt so a direct search
on the id in that course's cards.csv jumps straight to it.

Resumable: tracks already-checked card ids in
<course>/.internal/self_standing_state.json (both true and false
verdicts, so it never re-asks something it already judged clear).

Usage:
    python tools/check_self_standing.py <course-folder> [--batch-size 8] [--model NAME]
    python tools/check_self_standing.py --all [--batch-size 8] [--model NAME]

Report: <repo-root>/self_standing_report.txt (one line per flagged card,
appended across all courses this is run against).
"""
import argparse
import csv
import json
import os
import re
import time
import urllib.request

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
# qwen2.5-coder-7b-instruct was tried first for speed, but on this
# judgment task it flagged ~38% of cards with a high false-positive
# rate (systematically confused by select_blank's "___" and by
# standalone true/false claims). google/gemma-4-e4b, loaded with
# --context-length 16384 (the default 4096 causes empty/truncated
# responses — its internal reasoning eats the token budget before the
# JSON answer), flagged ~6% with every sampled flag being a real issue.
# Slower, but the accuracy difference was large enough to be worth it.
DEFAULT_MODEL = "google/gemma-4-e4b"
BATCH_SIZE_DEFAULT = 6

SYSTEM_PROMPT = (
    "For each question given, respond with true if it is self standing "
    "clear and without any additional context it can be responded, and "
    "say false if not. A question relying on an unstated 'this'/'that'/"
    "'these' with no antecedent in its own text, or assuming context "
    "from some other question, is false — this includes a question that "
    "only makes sense if the reader already knows a specific analogy, "
    "framing, or role this course has defined (e.g. calling the learner "
    "'a director' only means something once that metaphor has been "
    "taught; don't assume it's the ordinary real-world job title). The "
    "ONE exception: a question marked '[this card has an attached image "
    "the learner sees]' may say 'this photo'/'that portrait'/'this "
    "image' etc. and still be self standing, since the learner sees the "
    "image right on the card — don't flag that specific pattern as "
    "missing context on such a question. Respond ONLY with a JSON "
    "array, one object per question in the same order given, no "
    'markdown fences: {"id": "...", "self_standing": true or false}'
)

# select_blank's whole point is a fill-in-the-blank sentence — the "___"
# reads as "missing context" to a smaller model even when the sentence
# is perfectly clear (confirmed by sampling: this was the single
# biggest source of false positives). Exclude it rather than fight the
# model on every single one.
EXCLUDED_TYPES = {"select_blank"}

# Deterministic, 100%-reliable pre-check for the most blatant self-
# reference phrases — no LLM call needed, and no risk of the model
# waffling on an unambiguous case (confirmed by testing: prompt
# rewording that fixed one false-positive class made the model
# inconsistently miss "What is a hallucination in this context?" —
# literally containing "in this context" with no context given).
_VAGUE_REFERENT_NOUNS = r"(idea|concept|pattern|approach|principle|method|technique|step|rule|notion)"
BLATANT_SELF_REFERENCE = re.compile(
    r"\b(in this context|as (covered|mentioned|discussed|noted|shown)\s"
    r"(earlier|above|before)|as we (covered|discussed|mentioned)|"
    r"in this case\b(?!\s+of\b)|"
    # "this/that/these/those/the <vague noun>" — the original complaint
    # pattern ("What's the general term for this idea?"). Excludes a
    # following "of"/colon/dash/quote, since those usually mean the
    # sentence goes on to specify which one right there.
    rf"\b(this|that|these|those|the)\s+{_VAGUE_REFERENT_NOUNS}\b"
    r"(?!\s*(of\b|:|—|-|['\"“]))"
    r")",
    re.IGNORECASE,
)


def read_csv(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def call_llm(model, user_content, max_tokens=2000, retries=3):
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        LM_STUDIO_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310  # URL is a fixed constant / operator config, not user input
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


def format_question(card):
    # If the card has a real attached image, "this photo"/"that portrait"/
    # etc. has a valid referent the learner actually sees — tell the model
    # so it doesn't flag that pattern as missing context (confirmed by
    # sampling: this was a real, sizeable false-positive source).
    has_image = bool((card.get("image") or "").strip())
    image_note = " [this card has an attached image the learner sees]" if has_image else ""
    return f'id={card["id"]}{image_note}\nquestion : "{card.get("prompt","")} {card.get("options","")}".strip()'


def check_course(course_dir, model, batch_size, report_path):
    cards = read_csv(os.path.join(course_dir, "source", "cards.csv"))
    if not cards:
        return

    name = os.path.basename(course_dir.rstrip("/\\"))
    state_path = os.path.join(course_dir, ".internal", "self_standing_state.json")
    state = {}
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)

    candidates = [c for c in cards if c["id"] not in state and c.get("type") not in EXCLUDED_TYPES]
    if not candidates:
        print(f"  {name}: already fully checked ({len(cards)} cards)")
        return

    # Blatant cases never go to the model at all — free, and 100% reliable.
    todo = []
    auto_flagged = []
    for c in candidates:
        text = f'{c.get("prompt","")} {c.get("options","")}'
        if BLATANT_SELF_REFERENCE.search(text):
            auto_flagged.append(c)
        else:
            todo.append(c)

    if auto_flagged:
        for c in auto_flagged:
            state[c["id"]] = False
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        with open(report_path, "a", encoding="utf-8") as f:
            for c in auto_flagged:
                prompt = (c.get("prompt") or "").replace("\n", " ")
                f.write(f'{name} | card {c["id"]} | "{prompt}"\n')
        print(f"  {name}: {len(auto_flagged)} card(s) auto-flagged (blatant self-reference phrase, no LLM call)")

    if not todo:
        print(f"  {name}: fully checked ({len(cards)} cards)")
        return
    print(f"  {name}: {len(todo)}/{len(cards)} card(s) to check")

    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        block = "\n---\n".join(format_question(c) for c in batch)
        try:
            raw = call_llm(model, block)
            parsed = extract_json_array(raw)
        except Exception as e:  # noqa: BLE001
            print(f"    batch {i}-{i+len(batch)} FAILED: {e}")
            continue
        if not parsed:
            print(f"    batch {i}-{i+len(batch)}: could not parse model output, skipping")
            continue

        result_by_id = {str(item.get("id")): item for item in parsed if isinstance(item, dict)}
        newly_flagged = []
        for c in batch:
            result = result_by_id.get(c["id"])
            if result is None:
                continue
            verdict = bool(result.get("self_standing"))
            state[c["id"]] = verdict
            if not verdict:
                newly_flagged.append(c)

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        if newly_flagged:
            with open(report_path, "a", encoding="utf-8") as f:
                for c in newly_flagged:
                    prompt = (c.get("prompt") or "").replace("\n", " ")
                    f.write(f'{name} | card {c["id"]} | "{prompt}"\n')

        print(f"    batch {i}-{i+len(batch)} done ({sum(1 for v in state.values() if v is False)} flagged so far)")


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
    ap.add_argument("--report", default=None, help="path to the flagged-cards report (default: <repo root>/self_standing_report.txt)")
    args = ap.parse_args()

    if args.all:
        course_dirs = find_all_course_dirs(os.getcwd())
        report_path = args.report or os.path.join(os.getcwd(), "self_standing_report.txt")
    elif args.course:
        course_dirs = [args.course]
        report_path = args.report or os.path.join(os.getcwd(), "self_standing_report.txt")
    else:
        ap.error("pass a course folder or --all")
        return

    print(f"Checking self-standing clarity for {len(course_dirs)} course(s) with model={args.model}")
    print(f"Report: {report_path}")
    for course_dir in course_dirs:
        check_course(course_dir, args.model, args.batch_size, report_path)


if __name__ == "__main__":
    main()
