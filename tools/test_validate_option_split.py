import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "validate_course", Path(__file__).parent.parent / "python-basics" / "validate_course.py"
)
vc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vc)


def test_options_split_on_plain_pipes():
    assert vc._split_options("a|b|c") == ["a", "b", "c"]
    assert vc._split_options("") == []


# The app reads "\|" as a literal pipe inside one option (e.g. the set-union symbol).
def test_a_backslash_escaped_pipe_stays_inside_one_option():
    assert vc._split_options("`\|`|`&`|`-`") == ["`|`", "`&`", "`-`"]
    assert vc._split_options("a\|b|c") == ["a|b", "c"]
