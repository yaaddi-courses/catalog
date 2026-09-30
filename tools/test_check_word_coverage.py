import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_word_coverage as cwc  # noqa: E402

# Two decks: the second teaches "Goodbye". A select_blank in deck 1 that uses
# "Goodbye" is a FORWARD reference; one that uses "Banana" (taught nowhere) is
# an undefined reference; "Hello" (taught in its own deck) is fine.
UNIT_ORDER = {"u1": 0, "u2": 1}
CARDS = [
    {"id": "1", "unit_id": "u1", "type": "multiple_choice", "role": "main", "related_main_id": "",
     "prompt": "Hello یعنی چی؟", "options": "a|b"},
    {"id": "2", "unit_id": "u1", "type": "select_blank", "role": "exercise", "related_main_id": "1",
     "prompt": "___", "options": "Hello|Goodbye|Banana"},
    {"id": "3", "unit_id": "u2", "type": "multiple_choice", "role": "main", "related_main_id": "",
     "prompt": "Goodbye یعنی چی؟", "options": "a|b"},
]


def ledger():
    return cwc.build_ledger(CARDS)


def test_a_word_taught_only_in_a_later_deck_is_classified_as_taught_later_with_where():
    findings = cwc.classify_chip_references(CARDS, ledger(), UNIT_ORDER)
    later = [f for f in findings if f["chip"] == "Goodbye"]
    assert later == [
        {
            "card_id": "2",
            "type": "select_blank",
            "unit_id": "u1",
            "related_main_id": "1",
            "chip": "Goodbye",
            "kind": "taught_later",
            "taught_in_unit": "u2",
            "taught_in_card": "3",
        }
    ]


def test_a_word_taught_nowhere_is_classified_as_never_taught():
    findings = cwc.classify_chip_references(CARDS, ledger(), UNIT_ORDER)
    never = [f for f in findings if f["chip"] == "Banana"]
    assert len(never) == 1
    assert never[0]["kind"] == "never_taught"
    assert never[0]["taught_in_card"] is None


def test_a_word_taught_in_its_own_or_an_earlier_deck_is_not_reported():
    chips = {f["chip"] for f in cwc.classify_chip_references(CARDS, ledger(), UNIT_ORDER)}
    assert "Hello" not in chips


def test_text_report_says_where_a_later_word_is_taught():
    lines = cwc.find_undefined_references(CARDS, ledger(), UNIT_ORDER)
    goodbye = next(line for line in lines if '"Goodbye"' in line)
    assert "taught later" in goodbye
    assert "card 3" in goodbye
    banana = next(line for line in lines if '"Banana"' in line)
    assert "taught nowhere" in banana


def test_a_pack_own_word_split_exercise_is_not_a_reference():
    cards = [
        {"id": "1", "unit_id": "u1", "type": "multiple_choice", "role": "main", "related_main_id": "",
         "prompt": "Good morning یعنی چی؟", "options": "a|b"},
        {"id": "2", "unit_id": "u1", "type": "order", "role": "exercise", "related_main_id": "1",
         "prompt": "x", "options": "Good|morning"},
    ]
    assert cwc.classify_chip_references(cards, cwc.build_ledger(cards), {"u1": 0}) == []


def test_json_flag_prints_machine_readable_findings(tmp_path, capsys, monkeypatch):
    course = tmp_path / "demo"
    (course / "source").mkdir(parents=True)
    import csv

    with (course / "source" / "cards.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CARDS[0].keys()))
        writer.writeheader()
        writer.writerows(CARDS)
    with (course / "source" / "units.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "title"])
        writer.writeheader()
        writer.writerows([{"id": "u1", "title": "One"}, {"id": "u2", "title": "Two"}])
    monkeypatch.setattr(sys, "argv", ["check_word_coverage.py", str(course), "--json"])
    cwc.main()
    payload = json.loads(capsys.readouterr().out)
    kinds = sorted(f["kind"] for f in payload["references"])
    assert kinds == ["never_taught", "taught_later"]


def test_a_letter_card_teaches_its_letter_so_letter_chips_are_not_reported():
    cards = [
        {"id": "1", "unit_id": "u0", "type": "multiple_choice", "role": "main", "related_main_id": "",
         "prompt": "B b\nنام این حرف چیست؟", "options": "بی|سی"},
        {"id": "2", "unit_id": "u0", "type": "match_pairs", "role": "exercise", "related_main_id": "1",
         "prompt": "x", "options": "B↔بی"},
    ]
    assert cwc.classify_chip_references(cards, cwc.build_ledger(cards), {"u0": 0}) == []


def test_a_names_deck_letter_written_without_a_space_also_teaches_the_letter():
    cards = [
        {"id": "1", "unit_id": "u0", "type": "multiple_choice", "role": "main", "related_main_id": "",
         "prompt": "Qq\nاسم این حرف چیست؟", "options": "کیو|سی"},
        {"id": "2", "unit_id": "u0", "type": "match_pairs", "role": "exercise", "related_main_id": "1",
         "prompt": "x", "options": "Q↔کیو|C↔سی"},
    ]
    findings = cwc.classify_chip_references(cards, cwc.build_ledger(cards), {"u0": 0})
    assert [f["chip"] for f in findings] == ["C"]  # only C is untaught here; Q is


def test_a_two_letter_word_is_not_mistaken_for_a_capital_and_small_letter():
    cards = [
        {"id": "1", "unit_id": "u0", "type": "multiple_choice", "role": "main", "related_main_id": "",
         "prompt": "No\nیعنی چی؟", "options": "نه|بله"},
    ]
    assert [w for _id, _u, w in cwc.build_ledger(cards)] == ["No"]
