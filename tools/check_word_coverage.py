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
import re
import sys
from pathlib import Path

MEANING_QUESTION_RE = re.compile(r"^(.*?)\s*یعنی چی؟?$")


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


def find_undefined_references(
    cards: list[dict], ledger: list[tuple[int, str, str]], unit_order: dict[str, int]
) -> list[str]:
    """Chips inside order/match_pairs/select_blank options that don't match
    anything taught in this card's own unit or an earlier one. Scoped to
    these three types deliberately: their options are already discrete,
    atomic chips (not free prose), so comparing them to the ledger is
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
        options_raw = (c.get("options") or "")
        if ctype == "match_pairs":
            chips = [pair.split("↔", 1)[0] for pair in options_raw.split("|") if "↔" in pair]
        else:
            chips = options_raw.split("|")
        for chip in chips:
            chip = chip.strip()
            if not chip or chip == "___":
                continue
            if normalize(chip) not in taught_before:
                findings.append(
                    f'card {c["id"]} ({ctype}, unit={c["unit_id"]}, related_main_id={related}): '
                    f'"{chip}" does not match any word taught in this deck or an earlier one'
                )
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course_folder")
    parser.add_argument("--words", action="store_true", help="print only the taught-word list")
    args = parser.parse_args()

    course_dir = Path(args.course_folder)
    cards = load_cards(course_dir)
    units = load_units(course_dir)
    ledger = build_ledger(cards)

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
    undefined = find_undefined_references(cards, ledger, unit_order)
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
