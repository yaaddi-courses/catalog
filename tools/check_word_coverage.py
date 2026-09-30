#!/usr/bin/env python3
"""Audits a language-learning course's REAL, complete vocabulary ledger —
read directly from `source/cards.csv` (the actual shipped content), never
from a vocab spreadsheet like `vocab_source.csv`.

Why cards.csv and not the vocab spreadsheet: a vocab CSV only reflects
whatever was fed through `generate_language_course.py` — a hand-authored
deck (built by a one-off script, or edited directly in the app) can teach
real vocabulary that never touches that spreadsheet at all. This exact gap
produced a real mistake once already in this repo: "Goodbye", "How are
you?", and "I'm fine" were judged "missing" from a course because they
weren't in `vocab_source.csv`, when all three were already fully taught in
a hand-authored deck — the fix ended up being "remove the accidental
duplicate pack this tool would have caught," not "add a new word." Always
audit against cards.csv; treat a vocab spreadsheet as one input to content
generation, never as the ledger of record.

Usage:
    python tools/check_word_coverage.py <course-folder>          # full report
    python tools/check_word_coverage.py <course-folder> --words  # just the taught-word list

Reports, in this order:
  1. The full taught-word list, in teaching order (card id order), one
     section per deck — the actual answer to "what does this course teach?"
  2. Any word taught as its own main card in MORE than one deck — almost
     always a real defect (see AUTHORING.md / the flashcard-course-creator
     skill's "taught twice across decks" rule), not intentional repetition.
  3. Any chip inside an `order`/`match_pairs`/`select_blank` card's options
     that doesn't match any word already taught by that point in the
     ledger — a "used but never taught" reference, the same class of bug
     as the Goodbye example above would have been if it had been real.
     This is a heuristic, not a guarantee: punctuation/quoting variants and
     genuinely multi-word taught phrases can produce a false positive —
     read each flagged line before treating it as a real bug.
"""
import argparse
import csv
import json
import re
from pathlib import Path

MEANING_QUESTION_RE = re.compile(r"^(.*?)\s*یعنی چی؟?$")
# A letters pack: first line is the capital and small letter ("B b" in the sound decks, "Bb" in the names deck).
LETTER_LINE_RE = re.compile(r"^([A-Z]) ?([a-z])$")


def load_cards(course_dir: Path) -> list[dict]:
    path = course_dir / "source" / "cards.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_units(course_dir: Path) -> dict[str, str]:
    path = course_dir / "source" / "units.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {u["id"]: u["title"] for u in csv.DictReader(f)}


def load_unit_order(course_dir: Path) -> dict[str, int]:
    """unit id -> its row position in units.csv (0-based) — the one
    ordering that stays stable across any amount of card-level editing."""
    path = course_dir / "source" / "units.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {u["id"]: i for i, u in enumerate(csv.DictReader(f))}


def extract_target_word(card: dict) -> str | None:
    """The vocabulary item a MAIN card introduces, or None if this main
    card doesn't introduce a single lexical item (e.g. reading_passage/
    cloze_passage recap packs, which test comprehension across many
    already-taught items rather than teaching one new thing)."""
    ctype = card["type"]
    prompt = (card.get("prompt") or "").strip()
    if ctype == "multiple_choice":
        letter = LETTER_LINE_RE.match(prompt.splitlines()[0].strip()) if prompt else None
        # "Bb" / "B b" is a letter; "No" / "My" / "Go" are words (the second letter is not the small form).
        if letter and letter.group(2) == letter.group(1).lower():
            return letter.group(1)
        m = MEANING_QUESTION_RE.match(prompt)
        return m.group(1).strip() if m else None
    if ctype == "speech_recognition":
        return prompt or None
    return None


def normalize(word: str) -> str:
    return word.strip().rstrip(".!?,").lower()


def build_ledger(cards: list[dict]) -> list[tuple[int, str, str]]:
    """(card_id, unit_id, target_word) for every main card that introduces
    a vocabulary item, in id (== teaching) order."""
    ledger = []
    for c in cards:
        if c["role"] != "main":
            continue
        word = extract_target_word(c)
        if word:
            ledger.append((int(c["id"]), c["unit_id"], word))
    ledger.sort(key=lambda x: x[0])
    return ledger


def find_duplicates(ledger: list[tuple[int, str, str]]) -> dict[str, list[tuple[int, str, str]]]:
    by_norm: dict[str, list[tuple[int, str, str]]] = {}
    for entry in ledger:
        by_norm.setdefault(normalize(entry[2]), []).append(entry)
    return {k: v for k, v in by_norm.items() if len(v) > 1}


def classify_chip_references(
    cards: list[dict], ledger: list[tuple[int, str, str]], unit_order: dict[str, int]
) -> list[dict]:
    """Every chip inside an order/match_pairs/select_blank card's options that
    is not taught in that card's own unit or an earlier one, classified as:

    - ``taught_later``: the word IS taught, but in a LATER deck (a forward
      reference — the learner meets it before being taught it). The finding
      says exactly where it is taught (``taught_in_unit`` / ``taught_in_card``).
    - ``never_taught``: no card in the course teaches it at all.

    Report-only by design (owner decision 2026-09-30, docs/TASKS.md T59.12):
    what to do about a forward reference — reorder packs, add a teaching card,
    or reword the exercise — is a content decision for a human or the
    reviewer skill, so this tool only makes each one precise and easy to act on.

    Scoped to these three types deliberately: their options are already
    discrete, atomic chips (not free prose), so comparing them to the ledger is
    reliable — unlike a full sentence (speech_recognition/reading_passage),
    which would need real tokenization against multi-word taught phrases to
    check safely.

    Deliberately UNIT-granularity, not card-id-granularity: card ids only
    reflect true teaching order within a course generated in one single
    pass. A course edited incrementally over time (a deck regenerated later
    to add a few words, a recap pack appended afterward) ends up with ids
    that don't monotonically track teaching order within a unit anymore —
    checking against raw id order produced a wall of false positives on
    exactly this repo's own course the first time this was tried. Checking
    "taught anywhere in this unit or an earlier unit" instead is robust to
    that history at the cost of not catching a same-unit forward-reference
    (a narrower, less common class of bug) — a reasonable trade for a tool
    meant to be re-run after every edit, not a one-time perfect audit."""
    main_word_by_id = {cid: w for cid, _unit, w in ledger}
    # First deck (lowest unit rank) and card that teaches each normalized word.
    first_taught: dict[str, tuple[int, str, str]] = {}
    for cid, unit_id, word in ledger:
        rank = unit_order.get(unit_id, 10**9)
        key = normalize(word)
        if key not in first_taught or (rank, cid) < (first_taught[key][0], int(first_taught[key][2])):
            first_taught[key] = (rank, unit_id, str(cid))

    findings = []
    for c in cards:
        ctype = c["type"]
        if ctype not in ("order", "match_pairs", "select_blank"):
            continue
        related = c.get("related_main_id") or ""
        if not related or not related.isdigit():
            continue

        # A word-split exercise (e.g. "Good morning" broken into "Good" +
        # "morning" chips to arrange back into the ONE phrase that pack
        # itself introduces) isn't a cross-reference at all — its chips are
        # sub-word pieces of the pack's own new item, not independently
        # taught units. Detected by checking whether the chips, joined back
        # together, reconstruct the pack's own target word/phrase.
        if ctype == "order":
            own_word = main_word_by_id.get(int(related))
            if own_word:
                rejoined = normalize(" ".join(o.strip() for o in (c.get("options") or "").split("|")))
                if rejoined == normalize(own_word):
                    continue

        card_unit_rank = unit_order.get(c["unit_id"], 10**9)
        taught_before = {
            normalize(w) for _cid, unit_id, w in ledger if unit_order.get(unit_id, 10**9) <= card_unit_rank
        }
        options_raw = c.get("options") or ""
        if ctype == "match_pairs":
            chips = [pair.split("↔", 1)[0] for pair in options_raw.split("|") if "↔" in pair]
        else:
            chips = options_raw.split("|")
        for chip in chips:
            chip = chip.strip()
            if not chip or chip == "___":
                continue
            key = normalize(chip)
            if key in taught_before:
                continue
            where = first_taught.get(key)
            findings.append(
                {
                    "card_id": str(c["id"]),
                    "type": ctype,
                    "unit_id": c["unit_id"],
                    "related_main_id": related,
                    "chip": chip,
                    "kind": "taught_later" if where else "never_taught",
                    "taught_in_unit": where[1] if where else None,
                    "taught_in_card": where[2] if where else None,
                }
            )
    return findings


def format_reference(finding: dict, units: dict[str, str] | None = None) -> str:
    """One human-readable line for a `classify_chip_references` finding."""
    head = (
        f'card {finding["card_id"]} ({finding["type"]}, unit={finding["unit_id"]}, '
        f'related_main_id={finding["related_main_id"]}): "{finding["chip"]}"'
    )
    if finding["kind"] == "taught_later":
        deck = (units or {}).get(finding["taught_in_unit"], finding["taught_in_unit"])
        return f'{head} is used before it is taught - taught later, in deck "{deck}" (card {finding["taught_in_card"]})'
    return f"{head} is taught nowhere in this course (or is a proper noun - verify)"


def find_undefined_references(
    cards: list[dict], ledger: list[tuple[int, str, str]], unit_order: dict[str, int]
) -> list[str]:
    """Human-readable lines for `classify_chip_references` (kept for callers of the old API)."""
    return [format_reference(f) for f in classify_chip_references(cards, ledger, unit_order)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course_folder")
    parser.add_argument("--words", action="store_true", help="print only the taught-word list")
    parser.add_argument("--json", action="store_true", help="print the reference findings as JSON and nothing else")
    args = parser.parse_args()

    course_dir = Path(args.course_folder)
    cards = load_cards(course_dir)
    units = load_units(course_dir)
    ledger = build_ledger(cards)

    if args.json:
        references = classify_chip_references(cards, ledger, load_unit_order(course_dir))
        print(json.dumps({"course": course_dir.name, "references": references}, ensure_ascii=False, indent=2))
        return

    print(f"=== {course_dir.name}: {len(ledger)} vocabulary items across {len(units)} decks ===\n")

    current_unit = None
    n = 0
    for _cid, unit_id, word in ledger:
        title = units.get(unit_id, unit_id)
        if title != current_unit:
            print(f"\n## {title}")
            current_unit = title
        n += 1
        print(f"{n}. {word}")

    if args.words:
        return

    dupes = find_duplicates(ledger)
    print("\n=== Words taught more than once across decks ===")
    if not dupes:
        print("(none)")
    for norm, entries in dupes.items():
        locs = ", ".join(f'"{w}" in {units.get(uid, uid)} (card {cid})' for cid, uid, w in entries)
        print(f"- {locs}")

    unit_order = load_unit_order(course_dir)
    references = classify_chip_references(cards, ledger, unit_order)
    undefined = [format_reference(f, units) for f in references]
    print(
        "\n=== Possibly-undefined references (heuristic — verify before fixing; "
        "a proper noun in an example sentence, e.g. a person's name, is an "
        "expected false positive, not a bug) ==="
    )
    if not undefined:
        print("(none)")
    for line in undefined:
        print(f"- {line}")


if __name__ == "__main__":
    main()
