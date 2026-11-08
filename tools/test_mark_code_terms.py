import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import mark_code_terms as mc  # noqa: E402


def marked(text):
    return mc.mark_code_terms(text)[0]


def test_a_keyword_before_loop_or_clause_is_marked_but_not_the_noun():
    assert marked("A for loop repeats") == "A `for` loop repeats"
    assert marked("the else clause runs") == "the `else` clause runs"
    assert marked("A for loop's else block runs") == "A `for` loop's `else` block runs"


def test_ordinary_english_uses_of_the_same_words_are_left_alone():
    text = "Use it for example when you go in or out."
    assert marked(text) == text


def test_python_constants_and_self_are_marked():
    assert marked("What is the type of True?") == "What is the type of `True`?"
    assert marked("returns None here") == "returns `None` here"
    assert marked("the self argument and __init__") == "the `self` argument and `__init__`"


def test_none_of_the_above_is_english():
    assert marked("None of these is right") == "None of these is right"


def test_a_quoted_keyword_loses_its_quotes():
    assert marked("'and' requires both sides") == "`and` requires both sides"


def test_text_already_in_a_span_or_fence_is_left_alone():
    text = "Use `True` and\n```python\nx = None\n```\nfor real"
    assert marked(text) == text


def test_the_blank_is_never_touched():
    assert marked("If A ___ B, both must be True.") == "If A ___ B, both must be `True`."


def test_a_span_running_through_a_blank_is_left_to_the_author():
    text = "`x = ___ None` is odd"
    assert marked(text) == text


def test_only_python_courses_are_processed():
    assert mc.is_python_course("python-basics")
    assert mc.is_python_course("testing-with-pytest")
    assert not mc.is_python_course("canadian-citizenship")


def test_sentence_initial_true_false_is_english_not_the_constant():
    assert marked("True. Because the GIL prevents it") == "True. Because the GIL prevents it"
    assert marked("True about async clients?") == "True about async clients?"
    assert marked("It says. False, because x") == "It says. False, because x"


def test_self_in_a_hyphenated_english_word_is_left_alone():
    assert marked("A plain Lock self-deadlocks") == "A plain Lock self-deadlocks"


def test_operator_words_need_operator_or_keyword_after_them():
    assert marked("one slow client not block others") == "one slow client not block others"
    assert marked("the in operator tests membership") == "the `in` operator tests membership"


def test_try_finally_block_marks_both_words():
    assert marked("skip using a try/finally block") == "skip using a `try`/`finally` block"


def test_true_false_as_a_subject_at_the_start_of_a_sentence_are_the_constants():
    assert marked("True and False are the two values") == "`True` and `False` are the two values"


def make_course(base, name, text, bom=False):
    course = base / name
    (course / "source").mkdir(parents=True)
    path = course / "source" / "cards.csv"
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    return course, path


# Regression (N204): an explicit course path is used as given, not re-rooted at the repo root,
# and a non-Python course named explicitly is an error, not a silent exit 0.
def test_an_explicit_course_path_outside_the_repo_is_used(tmp_path, monkeypatch, capsys):
    course, path = make_course(tmp_path, "my-python-course", "id,prompt,options,explanation\n1,use None here,,\n")
    monkeypatch.setattr(sys, "argv", ["mark_code_terms.py", str(course), "--fix"])
    assert mc.main() == 0
    assert "`None`" in path.read_text(encoding="utf-8")


def test_an_explicit_non_python_course_is_reported(tmp_path, monkeypatch, capsys):
    course, _ = make_course(tmp_path, "canadian-citizenship", "id,prompt,options,explanation\n1,x,,\n")
    monkeypatch.setattr(sys, "argv", ["mark_code_terms.py", str(course)])
    assert mc.main() == 2
    assert "not a Python course" in capsys.readouterr().out


# Regression (H18): a BOM cards.csv is read and keeps its BOM.
def test_a_bom_cards_csv_is_fixed_and_keeps_its_bom(tmp_path):
    course, path = make_course(tmp_path, "python-x", "id,prompt,options,explanation\n1,use None here,,\n", bom=True)
    mc.process_course(str(course), True)
    assert path.read_bytes() == b"\xef\xbb\xbfid,prompt,options,explanation\n1,use `None` here,,\n"


# Regression (H8): the fix must change only the cell it was computed for, not a longer cell
# that merely contains the same text.
def test_fix_rewrites_only_the_fixed_cell(tmp_path):
    course = tmp_path / "python-basics"
    (course / "source").mkdir(parents=True)
    path = course / "source" / "cards.csv"
    text = (
        "id,prompt,options,explanation\n"
        "1,use None here,,\n"
        '2,x,"Note, use None here",\n'  # options are never marked by this tool
    )
    path.write_text(text, encoding="utf-8", newline="")
    mc.process_course(str(course), True)
    assert path.read_bytes().decode("utf-8") == text.replace("1,use None here", "1,use `None` here")
