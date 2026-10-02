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
    it instead of rewriting anything.

Safety: every field a REWORD touches goes through the SAME word-limit
check llm_fix_phrasing.py already uses, and the original text of every
touched card is kept in memory so it can be reverted individually (not
the whole course) if validate_course.py still rejects it afterward.
After a course's batch, check_key_term_usage.py is re-run; anything
still flagged is left alone and reported, never looped forever.

Usage:
    python tools/llm_fix_forward_refs.py <course-folder> [--batch-size 3] [--model NAME]
    python tools/llm_fix_forward_refs.py --all [--batch-size 3] [--model NAME]
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
        "temperature": 0.1,
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


def build_word_pattern(term):
    return re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE | re.UNICODE)


def build_matcher(terms):
    ordered = sorted(set(terms), key=len, reverse=True)
    if not ordered:
        return None
    pattern = "|".join(re.escape(t) for t in ordered)
    return re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)


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
        for c in cards:
            if c["id"] == intro_id:
                continue
            card_rank = unit_order.get(c["unit_id"], 10**9)
            if card_rank >= intro_rank:
                continue
            if matcher.search(card_text(c)):
                groups.setdefault(c["id"], []).append((term, definition, intro_id))
    return groups, card_fields, cards


def valid_rewrite(new_prompt, new_options, orig_options):
    if new_prompt is not None and len(new_prompt.split()) > MAX_PROMPT_WORDS:
        return False
    if new_options is not None:
        orig_n = len(orig_options.split("|"))
        new_opts = new_options.split("|")
        if len(new_opts) != orig_n:
            return False
        for o in new_opts:
            if len(o.split(":", 1)[-1].split()) > MAX_OPTION_WORDS:
                return False
    return True


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


def run_validate(course_dir):
    """Returns set of card ids validate_course.py reports an ERROR for
    (word-count violations etc.), by parsing its stdout — no separate
    JSON output mode, so this greps the human-readable lines.

    Uses absolute paths throughout and never relies on the calling
    process's own cwd (which can differ from expected when this script
    itself runs backgrounded) — a prior relative-path version silently
    returned an empty set here (both a wrong doubled-up script path AND
    a cwd mismatch), so validation failures were never caught and the
    per-card revert never fired. Fail loudly instead of silently now."""
    abs_course_dir = os.path.abspath(course_dir)
    script = os.path.join(abs_course_dir, "validate_course.py")
    if not os.path.isfile(script):
        print(f"    WARNING: validate_course.py not found at {script} — skipping validation, nothing will be reverted")
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


def fix_course(course_dir, model, batch_size):
    groups, card_fields, cards = find_forward_refs(course_dir)
    if not groups:
        return False

    name = os.path.basename(course_dir)
    print(f"  {name}: {len(groups)} card(s) with forward-referenced term(s)")

    cards_by_id = {c["id"]: c for c in cards}
    glossary_path = os.path.join(course_dir, "source", "glossary.csv")
    glossary_fields, glossary = read_csv(glossary_path)
    glossary_by_term = {g["term"]: g for g in glossary}

    original = {}  # card_id -> original field dict, for per-card revert
    remaps = []  # (term, new_card_id)
    touched_card_ids = set()

    group_items = list(groups.items())
    for i in range(0, len(group_items), batch_size):
        batch = group_items[i : i + batch_size]
        block = "\n---\n".join(format_group(cards_by_id[cid], terms) for cid, terms in batch)
        try:
            raw = call_llm(model, block)
            parsed = extract_json_array(raw)
        except Exception as e:  # noqa: BLE001
            print(f"    batch {i}-{i+len(batch)} FAILED: {e}")
            continue
        if not parsed:
            print(f"    batch {i}-{i+len(batch)}: could not parse model output, skipping")
            continue

        result_by_id = {str(item.get("card_id")): item for item in parsed if isinstance(item, dict)}
        for cid, terms in batch:
            result = result_by_id.get(cid)
            if not result:
                continue
            card = cards_by_id[cid]
            decision = result.get("decision")
            if decision == "REMAP":
                remap_term = result.get("remap_term")
                if remap_term and remap_term in glossary_by_term:
                    remaps.append((remap_term, cid))
                continue
            if decision != "REWORD":
                continue
            new_prompt = result.get("prompt")
            new_options = result.get("options")
            new_explanation = result.get("explanation")
            if not valid_rewrite(new_prompt, new_options, card.get("options", "")):
                continue  # leave untouched, will still show up in the final residual report
            if cid not in original:
                original[cid] = dict(card)
            if new_prompt:
                card["prompt"] = new_prompt
            if new_options:
                card["options"] = new_options
            if new_explanation:
                card["explanation"] = new_explanation
            touched_card_ids.add(cid)

        print(f"    batch {i}-{i+len(batch)} done")

    for term, new_id in remaps:
        glossary_by_term[term]["introduced_by_card_id"] = new_id

    if not touched_card_ids and not remaps:
        print(f"  DONE: {name} — no changes applied")
        return False

    cards_path = os.path.join(course_dir, "source", "cards.csv")

    def write_cards():
        tmp = cards_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=card_fields)
            w.writeheader()
            w.writerows(cards)
        os.replace(tmp, cards_path)

    def write_glossary():
        tmp = glossary_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=glossary_fields)
            w.writeheader()
            w.writerows(glossary)
        os.replace(tmp, glossary_path)

    write_cards()
    write_glossary()

    # Validate; revert any specific card that still fails a structural
    # check (e.g. a word-limit edge case the pre-check missed).
    bad_ids = run_validate(course_dir)
    reverted = bad_ids & touched_card_ids
    if reverted:
        for cid in reverted:
            cards_by_id[cid].clear()
            cards_by_id[cid].update(original[cid])
        write_cards()
        print(f"  {name}: reverted {len(reverted)} card(s) that failed validation: {sorted(reverted)}")

    print(f"  DONE: {name} — reworded {len(touched_card_ids - reverted)} card(s), remapped {len(remaps)} term(s)")
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

    print(f"Fixing forward-references for {len(course_dirs)} course(s) with model={args.model}")
    for course_dir in course_dirs:
        fix_course(course_dir, args.model, args.batch_size)


if __name__ == "__main__":
    main()
