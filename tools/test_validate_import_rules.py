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


# The app fills a prompt with several "___" blanks from a "/"-separated option, one part per
# blank; an option that does not split into exactly that many parts goes whole into the first
# blank and leaves the others empty (selectBlankCard.tsx). Found 2026-11-01: "I/O/CPU" for two
# blanks split into 3 parts.
def multi_blank_errors(prompt, options):
    return [e for e in errors_for("select_blank", prompt, options) if "blank" in e and "/" in e]


def test_a_two_blank_option_must_split_into_two_parts():
    errors = multi_blank_errors("Threading helps ___-bound code, not ___-bound code.", "I/O/CPU|CPU/I/O|memory/disk")
    assert len(errors) == 2 and all("2 blanks" in e for e in errors)
    assert any('"I/O/CPU"' in e for e in errors) and any('"CPU/I/O"' in e for e in errors)


def test_a_two_blank_option_without_a_slash_is_an_error():
    assert multi_blank_errors("About 65% are ___ ___.", "First Nations|Inuit citizens")


def test_an_empty_part_is_an_error():
    assert multi_blank_errors("Concurrency ___ many things; parallelism ___ many.", "dealing/|doing/dealing")


def test_a_longer_underscore_run_counts_as_one_blank_like_the_app():
    assert multi_blank_errors("A ____ and a _____ here.", "x/y|y/x") == []
    assert multi_blank_errors("A ____ and a _____ here.", "x|y")


def test_well_formed_multi_blank_options_are_fine():
    assert multi_blank_errors("Concurrency ___ many things; parallelism ___ many.", "dealing/doing|doing/dealing") == []


def test_a_slash_in_a_single_blank_option_is_shown_whole_and_fine():
    assert multi_blank_errors("Volunteering helps you develop ___.", "friends/contacts|debt|1/2") == []
