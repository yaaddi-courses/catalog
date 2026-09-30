import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "validate_course", Path(__file__).parent.parent / "python-basics" / "validate_course.py"
)
vc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vc)

UNITS = [{"id": "1", "title": "U", "description": "d", "min_level": "1", "image": "x.png"}]


def card(prompt, ctype="media_card"):
    return {
        "id": "1", "unit_id": "1", "type": ctype, "role": "main", "related_main_id": "",
        "prompt": prompt, "options": "a|b", "correct_index": "0", "audio": "", "explanation": "e",
    }


def errors_for(prompt, ctype="media_card"):
    report = vc.Report("t")
    vc.validate_cards(UNITS, [card(prompt, ctype)], report)
    return [e for e in report.errors if "Listen" in e or "listen" in e]


def test_a_stray_listen_prefix_on_a_prompt_is_an_error():
    assert errors_for("Listen: What does the modulo operator do?")
    assert errors_for("listen - what is a string?")


def test_a_normal_question_about_listening_is_fine():
    assert not errors_for("What is the goal of active listening?")
    assert not errors_for("Active listening means listening to understand.", "true_false")
