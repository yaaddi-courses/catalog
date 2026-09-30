import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "validate_course", Path(__file__).parent.parent / "python-basics" / "validate_course.py"
)
vc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vc)


def test_plain_words_are_counted_one_by_one():
    assert vc._word_count("What does this print") == 4
    assert vc._word_count("") == 0
    assert vc._word_count(None) == 0


# Code shown in backticks is one thing to look at, however it is spaced: adding
# the spaces a formatter wants ("x = 5") must not make a card "too wordy".
def test_a_code_span_counts_as_one_word_however_many_spaces_it_has():
    assert vc._word_count("`result = 'yes' if flag else 'no'` is a ternary") == 4
    assert vc._word_count("`x = 5`") == 1
    assert vc._word_count("Use `a b c` and `d e` here") == 5


def test_an_unclosed_backtick_is_just_text():
    assert vc._word_count("odd ` tick here") == 4
