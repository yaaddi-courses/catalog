"""Pronunciation (speech_recognition) cards were removed from the app (owner, 2026-10-08): no microphone use.
A course that still contains one would fail to import in the app, so the validator must reject it."""
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "validate_course", Path(__file__).parent.parent / "python-basics" / "validate_course.py"
)
vc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vc)

UNITS = [{"id": "1", "title": "U", "description": "d", "min_level": "1", "image": "x.png"}]


def errors_for(ctype):
    card = {
        "id": "1", "unit_id": "1", "type": ctype, "role": "main", "related_main_id": "",
        "prompt": "Hello", "options": "a|b", "correct_index": "0", "audio": "", "explanation": "e",
    }
    report = vc.Report("t")
    vc.validate_cards(UNITS, [card], report)
    return [e for e in report.errors if "type" in e.lower()]


def test_a_speech_recognition_card_is_an_error():
    assert errors_for("speech_recognition")


def test_the_listening_card_it_sits_next_to_is_still_allowed():
    assert not errors_for("listening_card")
