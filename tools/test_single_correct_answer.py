"""Every single-answer choice card must have exactly ONE correct option.

Covers multiple_choice, select_blank and image_choice in every course's
source/cards.csv. A card fails when:
  - correct_index is missing, non-numeric, out of range, or lists several
    indexes ("0|2" belongs to multi_select only);
  - an option is empty;
  - two options are identical after normalising whitespace/backticks — a
    distractor that duplicates the correct answer is a second correct answer.

Whether a distractor is *semantically* right can't be checked by a script;
that stays with review-course. Run: python -m pytest tools/test_single_correct_answer.py
"""
import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SINGLE_ANSWER_TYPES = {"multiple_choice", "select_blank", "image_choice"}


def _norm(option):
    # Case-sensitive on purpose: `name` and `Name` are different identifiers.
    return re.sub(r"\s+", " ", option.replace("`", "")).strip()


def single_answer_problems(card):
    """Return a list of human-readable problems for one card row (empty = ok)."""
    options = [o for o in (card.get("options") or "").split("|")] if (card.get("options") or "").strip() else []
    raw = (card.get("correct_index") or "").strip()
    if len(options) < 2:
        return [f"needs at least 2 options, has {len(options)}"]
    if not re.fullmatch(r"\d+", raw):
        return [f'correct_index "{raw}" must be exactly one number (use multi_select for several)']
    problems = []
    if int(raw) >= len(options):
        problems.append(f"correct_index {raw} is out of range for {len(options)} options")
    if any(not o.strip() for o in options):
        problems.append("has an empty option")
    seen = {}
    for i, o in enumerate(options):
        if _norm(o) and _norm(o) in seen:
            problems.append(f'options {seen[_norm(o)]} and {i} are identical ("{o.strip()}")')
        seen.setdefault(_norm(o), i)
    return problems


def _all_cards():
    for path in sorted(ROOT.glob("*/source/cards.csv")):
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("type") or "multiple_choice") in SINGLE_ANSWER_TYPES:
                    yield path.parent.parent.name, row


def test_every_course_single_answer_card_has_exactly_one_correct_option():
    failures = [
        f"{course} card {row.get('id')}: {p}"
        for course, row in _all_cards()
        for p in single_answer_problems(row)
    ]
    assert not failures, "\n".join(failures)


# --- the checker itself -----------------------------------------------------

def _card(options, correct):
    return {"type": "multiple_choice", "options": options, "correct_index": correct}


def test_good_card_passes():
    assert single_answer_problems(_card("a|b|c|d", "2")) == []


@pytest.mark.parametrize("correct", ["", "x", "0|1", "-1"])
def test_bad_correct_index_is_flagged(correct):
    assert single_answer_problems(_card("a|b|c", correct))


def test_out_of_range_index_is_flagged():
    assert single_answer_problems(_card("a|b|c", "3"))


def test_duplicate_option_is_flagged_even_with_spacing_differences():
    assert single_answer_problems(_card("Use `git add`|Use  git add|other", "0"))


def test_options_differing_only_by_case_are_distinct_identifiers():
    assert single_answer_problems(_card("`name`|`Name`|`NAME`", "0")) == []


def test_empty_option_is_flagged():
    assert single_answer_problems(_card("a||c", "0"))


def test_fewer_than_two_options_is_flagged():
    assert single_answer_problems(_card("", "0"))
