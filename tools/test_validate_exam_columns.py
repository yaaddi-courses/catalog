import importlib.util
import tempfile
from pathlib import Path

import pytest

# Each course is its own repo with its own validate_course.py; this suite checks the shared
# exam-column rules against one local checkout and is skipped in a bare clone of the catalog.
VALIDATOR = Path(__file__).parent.parent / "canadian-citizenship" / "validate_course.py"
if not VALIDATOR.exists():
    pytest.skip("no course checkout next to the catalog", allow_module_level=True)

SPEC = importlib.util.spec_from_file_location("validate_course", VALIDATOR)
vc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vc)

BASE = "slug,title,description,version,author,color,icon,image"
BASE_ROW = "c,C,d,1.0.0,Y,#1E5AA8,flag-outline,cover.png"


def errors_for(extra_header="", extra_row=""):
    with tempfile.TemporaryDirectory() as tmp:
        header = BASE + ("," + extra_header if extra_header else "")
        row = BASE_ROW + ("," + extra_row if extra_row else "")
        (Path(tmp) / "meta.csv").write_text(f"{header}\n{row}\n", encoding="utf-8")
        report = vc.Report("t")
        vc._validate_meta_csv_exam(tmp, report)
        return report.errors


def test_a_course_without_exam_columns_is_fine():
    assert errors_for() == []
    assert errors_for("exam_questions,exam_minutes,exam_pass_percent,exam_types", ",,,") == []


def test_a_complete_exam_block_is_fine():
    assert errors_for(
        "exam_questions,exam_minutes,exam_pass_percent,exam_types",
        "20,30,75,multiple_choice|true_false",
    ) == []
    assert errors_for("exam_questions,exam_minutes,exam_pass_percent", "20,30,75") == []


def test_a_half_filled_block_is_an_error_naming_the_blank_column():
    errors = errors_for("exam_questions", "20")
    assert len(errors) == 1
    assert any("exam_pass_percent" in e and "blank" in e for e in errors)


def test_a_blank_exam_minutes_means_no_time_limit():
    assert errors_for("exam_questions,exam_minutes,exam_pass_percent", "20,,60") == []


def test_numbers_must_be_whole_and_in_range():
    assert errors_for("exam_questions,exam_minutes,exam_pass_percent", "20,30,101")
    assert errors_for("exam_questions,exam_minutes,exam_pass_percent", "0,30,75")
    assert errors_for("exam_questions,exam_minutes,exam_pass_percent", "20,half an hour,75")
    assert errors_for("exam_questions,exam_minutes,exam_pass_percent", "20,30,7.5")


def test_only_multiple_choice_and_true_false_are_allowed_types():
    errors = errors_for(
        "exam_questions,exam_minutes,exam_pass_percent,exam_types", "20,30,75,order|true_false"
    )
    assert len(errors) == 1 and "order" in errors[0]


def test_missing_meta_csv_is_not_this_checks_problem():
    with tempfile.TemporaryDirectory() as tmp:
        report = vc.Report("t")
        vc._validate_meta_csv_exam(tmp, report)
        assert report.errors == []
