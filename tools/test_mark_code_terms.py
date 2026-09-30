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
