import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_code_markup_coverage as cm  # noqa: E402


# Regression: a `code span` running through a fill-in-the-blank was split at the
# blank, so the fixer no longer saw it as already marked and wrapped pieces of it
# again ("`def `f()`: ___ x`").
def test_a_span_that_runs_through_a_blank_is_left_alone():
    text = "`def f(): ___ x; x = 2` lets `f()` modify the module-level `x`."
    fixed, fixes = cm.fix_text(text)
    assert fixed == text
    assert fixes == []


def test_a_line_with_a_blank_and_no_markup_is_still_fixed():
    fixed, fixes = cm.fix_text("___('hi') shows text on the screen.")
    assert fixed == "`___('hi')` shows text on the screen." or "`('hi')`" in fixed
    assert fixes


def test_plain_prose_is_untouched():
    text = "Officials verify you meet all ___."
    assert cm.fix_text(text) == (text, [])


# Regression (2026-09-30): the fixer wrapped lines INSIDE fenced code blocks in
# backticks, and cut "t.___()" into "t.___`()`".
def test_fenced_code_blocks_are_never_touched():
    text = "What prints?\n```python\nx = 5\nprint(x)\n```"
    assert cm.fix_text(text) == (text, [])


def test_text_around_a_fence_is_still_fixed():
    fixed, fixes = cm.fix_text("Call print(x) first.\n```python\nx = 5\n```\nThen len(x) is used.")
    assert "`print(x)`" in fixed and "`len(x)`" in fixed
    assert "```python\nx = 5\n```" in fixed
    assert len(fixes) == 2


def test_a_call_with_a_blank_in_it_is_wrapped_whole():
    fixed, _ = cm.fix_text("t.___() polls a thread without blocking.")
    assert fixed == "`t.___()` polls a thread without blocking."


def test_a_call_with_a_blank_argument_is_wrapped_whole():
    fixed, _ = cm.fix_text("await asyncio.___(1) pauses the loop.")
    assert fixed == "await `asyncio.___(1)` pauses the loop."


def test_a_blank_in_plain_prose_is_left_alone():
    text = "The tool most used to build containers is ___."
    assert cm.fix_text(text) == (text, [])


# Regression: an options cell like "from|import|using|with" looked like ONE code
# line ("from ...") and got wrapped as a single span, destroying the choice list.
def test_an_options_cell_is_fixed_option_by_option_never_as_one_line():
    new, fixes = cm.fix_options_cell("from|import|using|with")
    assert new == "from|import|using|with"
    assert fixes == []


def test_a_call_inside_one_option_is_wrapped_on_its_own():
    new, fixes = cm.fix_options_cell("Use print(x) here|Something else")
    assert new == "Use `print(x)` here|Something else"
    assert len(fixes) == 1


# A command whose subcommand is the blank is still one command: "git ___ file.txt".
def test_a_command_with_a_blank_subcommand_is_wrapped_whole():
    fixed, _ = cm.fix_text("git ___ file.txt stages one file.")
    assert fixed == "`git ___ file.txt` stages one file."
    fixed, _ = cm.fix_text("docker ___ turns a Dockerfile into an image.")
    assert fixed.startswith("`docker ___`")


def test_prose_starting_with_a_tool_name_and_no_blank_is_unchanged():
    text = "git is a version control system."
    assert cm.fix_text(text) == (text, [])


def _write_cards(path, text, bom=False):
    (path / "source").mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    (path / "source" / "cards.csv").write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
    return path / "source" / "cards.csv"


# Regression (H8): --fix replaced the old text everywhere in the file, so the same text in a
# field the fixer never touched (here the options of a match_pairs card) was rewritten too.
def test_fix_rewrites_only_the_fixed_cell(tmp_path):
    cards = _write_cards(
        tmp_path,
        "id,type,prompt,options,explanation\n"
        "1,type_answer,Call print(x) now,,\n"
        "2,match_pairs,Pick one,Call print(x) now|b,\n",
    )
    fixes = cm.check_or_fix_course(str(tmp_path), True)
    assert len(fixes) == 1
    assert cards.read_text(encoding="utf-8") == (
        "id,type,prompt,options,explanation\n"
        "1,type_answer,Call `print(x)` now,,\n"
        "2,match_pairs,Pick one,Call print(x) now|b,\n"
    )


def test_cell_replace_skips_an_ambiguous_match():
    raw = "id,prompt\n1,abc\n2,abc\n"
    new_raw, skipped = cm.replace_cells(raw, [("abc", "`abc`")])
    assert new_raw == raw and skipped == ["abc"]
    new_raw, skipped = cm.replace_cells(raw, [("abc", "`abc`"), ("abc", "`abc`")])
    assert new_raw == "id,prompt\n1,`abc`\n2,`abc`\n" and skipped == []


# Regression (H7): a BOM made header.index("id") raise, and a short row raised IndexError.
def test_bom_and_short_rows_are_handled(tmp_path):
    cards = _write_cards(
        tmp_path,
        "id,type,prompt,options,explanation\n"
        "1,type_answer,Call print(x) now,,\n"
        "2,type_answer\n",
        bom=True,
    )
    fixes = cm.check_or_fix_course(str(tmp_path), True)
    assert [f[0] for f in fixes] == ["1"]
    raw = cards.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and b"`print(x)`" in raw


def test_all_uses_the_repo_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Path(cm.REPO_ROOT) == Path(__file__).resolve().parent.parent
    monkeypatch.setattr(cm, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["check_code_markup_coverage.py", "--all"])
    try:
        cm.main()
    except SystemExit as exit_:
        assert exit_.code not in (0, None)  # no course found is an error
    else:
        raise AssertionError("expected a non-zero exit")
