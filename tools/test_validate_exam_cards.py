import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "validate_course", Path(__file__).parent.parent / "python-basics" / "validate_course.py"
)
vc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vc)

UNITS = [{"id": "1", "title": "U", "description": "d", "min_level": "1", "image": "x.png"}]


def errors_for(ctype="multiple_choice", related=""):
    card = {
        "id": "1", "unit_id": "1", "type": ctype, "role": "exam", "related_main_id": related,
        "prompt": "Which one?", "options": "a|b|c", "correct_index": "1", "audio": "", "explanation": "e",
    }
    report = vc.Report("t")
    vc.validate_cards(UNITS, [card], report)
    return report.errors


def test_an_exam_card_is_a_valid_role_and_needs_no_main_card():
    assert not any("role" in e or "exam" in e for e in errors_for())


def test_an_exam_card_may_be_true_false():
    assert not any("exam card" in e for e in errors_for("true_false"))


def test_an_exam_card_must_be_a_type_exams_are_built_from():
    assert any("exam card 1: type must be" in e for e in errors_for("order"))


def test_an_exam_card_must_not_be_linked_to_a_main_card():
    assert any("must not have a related_main_id" in e for e in errors_for(related="5"))
