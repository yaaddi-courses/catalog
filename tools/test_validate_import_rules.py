import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "validate_course", Path(__file__).parent.parent / "python-basics" / "validate_course.py"
)
vc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vc)

UNITS = [{"id": "1", "title": "U", "description": "d", "min_level": "1", "image": "x.png"}]


def errors_for(ctype, prompt, options, correct="0"):
    card = {
        "id": "1", "unit_id": "1", "type": ctype, "role": "main", "related_main_id": "",
        "prompt": prompt, "options": options, "correct_index": correct, "audio": "", "explanation": "e",
    }
    report = vc.Report("t")
    vc.validate_cards(UNITS, [card], report)
    return report.errors


# The app refuses to import a course containing these (found 2026-09-30: four
# published courses could not be installed, and this validator passed them).
def test_a_match_pair_without_a_separator_is_an_error():
    errors = errors_for("match_pairs", "Match.", "Param↔Input|Output file saved")
    assert any("match_pairs" in e and "Output file saved" in e for e in errors)


def test_match_pairs_needs_two_pairs():
    assert any("match_pairs" in e for e in errors_for("match_pairs", "Match.", "A↔B"))


def test_a_well_formed_match_is_fine():
    assert not any("match_pairs" in e for e in errors_for("match_pairs", "Match.", "A↔B|C↔D"))


def test_the_importer_also_accepts_colon_slash_and_comma_pairs():
    assert not any("match_pairs" in e for e in errors_for("match_pairs", "Match.", "A:B|C/D"))


def test_select_blank_needs_a_blank_in_the_prompt():
    errors = errors_for("select_blank", "No blank here.", "a|b")
    assert any("select_blank" in e and "___" in e for e in errors)


def test_select_blank_with_a_blank_is_fine():
    assert not any("select_blank" in e for e in errors_for("select_blank", "The ___ runs.", "a|b"))
