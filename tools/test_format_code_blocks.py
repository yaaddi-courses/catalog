import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import format_code_blocks as fcb  # noqa: E402


def test_is_span_line_only_matches_a_line_that_is_exactly_one_span():
    assert fcb.is_span_line("`x = 1`")
    assert fcb.is_span_line("  `x = 1`  ")
    assert not fcb.is_span_line("Run `x = 1` now")
    assert not fcb.is_span_line("`a` and `b`")
    assert not fcb.is_span_line("``")
    assert not fcb.is_span_line("plain")


def test_single_standalone_span_becomes_a_fenced_block():
    assert fcb.convert("What does this print?\n`print(7 % 2)`", "python") == (
        "What does this print?\n```python\nprint(7 % 2)\n```"
    )


def test_consecutive_span_lines_become_one_normalized_python_block():
    text = "What prints?\n`x=5`\n`if x>10:print('big')`\n`else:print('small')`"
    assert fcb.convert(text, "python") == (
        "What prints?\n```python\nx = 5\nif x > 10:\n    print('big')\nelse:\n    print('small')\n```"
    )


def test_inline_code_inside_a_sentence_is_left_alone():
    text = "Use `len(s)` to count characters."
    assert fcb.convert(text, "python") == text


def test_is_idempotent():
    once = fcb.convert("Q\n`x=1`\n`y=2`", "python")
    assert fcb.convert(once, "python") == once


def test_python_comments_are_kept_and_quotes_are_not_rewritten():
    # A plain `ast.unparse` would silently drop the comment; black keeps it and,
    # with string normalization off, keeps the author's quote style.
    text = "Q\n`x='a'  # one`"
    assert fcb.convert(text, "python") == "Q\n```python\nx = 'a'  # one\n```"


def test_tuple_targets_are_not_parenthesized():
    # ast.unparse would print `for (k, v) in ...`.
    text = "Q\n`for k,v in d.items():print(k,v)`"
    assert "for k, v in d.items():" in fcb.convert(text, "python")


def test_falls_back_to_ast_when_black_is_not_installed(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_black(name, *args, **kwargs):
        if name == "black":
            raise ImportError("black not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_black)
    assert fcb.format_python("x=1\nif x:print(x)") == "x = 1\nif x:\n    print(x)"
    # Comment-bearing code is left exactly as written in the fallback path.
    assert fcb.format_python("x=1  # one") == "x=1  # one"


def test_unparseable_python_is_fenced_verbatim():
    text = "Q\n`print(`"
    assert fcb.convert(text, "python") == "Q\n```python\nprint(\n```"


def test_other_languages_are_fenced_without_reformatting():
    assert fcb.convert("Q\n`SELECT  1`", "sql") == "Q\n```sql\nSELECT  1\n```"


def test_python_normalization_never_changes_the_parsed_meaning():
    import ast

    for code in ["x=0\nif x:print('t')\nelse:print('f')", "s='Py'\nprint(s[-1])", "for i in range(3):print(i)"]:
        assert ast.dump(ast.parse(fcb.format_python(code))) == ast.dump(ast.parse(code))


def test_indentation_of_a_span_line_is_preserved_in_the_block():
    # Card 30 of python-basics: the loop body is indented under `for`, and an
    # incomplete block does not parse, so the indentation must survive verbatim.
    text = "What does this print?\n`for i in range(3):`\n    `print(i)`"
    assert fcb.convert(text, "python") == (
        "What does this print?\n```python\nfor i in range(3):\n    print(i)\n```"
    )


def test_a_hand_wrapped_code_line_is_repaired_into_the_block():
    # Card 56 of python-basics: `for k,v in `d.items()`:`print(k,v)`` is code
    # whose pieces were wrapped in spans by hand; it parses once the backticks
    # go, so it joins its neighbours in ONE normalized block.
    text = "What does this print?\n`d={'a':1}`\nfor k,v in `d.items()`:`print(k,v)`"
    assert fcb.convert(text, "python") == (
        "What does this print?\n```python\nd = {'a': 1}\nfor k, v in d.items():\n    print(k, v)\n```"
    )


def test_a_call_with_the_argument_in_a_span_is_repaired():
    assert fcb.convert("Q\n`s='a,b'`\nprint(`s.split(',')`)", "python") == (
        "Q\n```python\ns = 'a,b'\nprint(s.split(','))\n```"
    )


def test_code_that_cannot_be_repaired_is_flagged_not_guessed():
    text = "Q\n`a=1`\ndef `f`(a,`b`:"
    assert fcb.needs_manual_review(text)
    assert fcb.convert(text, "python") == text


def test_prose_with_several_inline_spans_is_never_treated_as_code():
    sentence = "`append()` adds exactly one item; `extend()` adds several."
    assert not fcb.needs_manual_review(sentence)
    assert fcb.convert(sentence, "python") == sentence
    # Card 68 / 206 of python-basics: short sentences with two spans are prose too.
    for prose in (
        "`h` defaults to 2, so `area(3)` is 3 * 2 = 6.",
        "`sorted()` copies; `list.sort()` sorts in place.",
    ):
        assert fcb.convert(prose, "python") == prose
        assert not fcb.needs_manual_review(prose)
    # A sentence that merely STARTS with a code-looking word is still prose.
    starts_with_keyword = "class starts every class definition, so `Dog()` builds one."
    assert fcb.convert(starts_with_keyword, "python") == starts_with_keyword


def test_ordinary_prose_with_inline_code_does_not_need_review():
    assert not fcb.needs_manual_review("Use `len(s)` to count characters.\n`print(1)`")


def test_manual_review_cards_are_reported_by_the_cli(tmp_path, capsys):
    (tmp_path / "source").mkdir()
    with (tmp_path / "source" / "cards.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "type", "prompt", "explanation"])
        writer.writeheader()
        writer.writerow(
            {"id": "9", "type": "multiple_choice", "prompt": "Q\n`a=1`\ndef `f`(a,`b`:", "explanation": ""}
        )
    fcb.main([str(tmp_path), "--lang", "python"])
    assert "MANUAL: card 9: prompt" in capsys.readouterr().out


def test_select_blank_cards_are_never_converted(tmp_path):
    rows = [
        {"id": "1", "type": "select_blank", "prompt": "Q\n`x=1`", "explanation": ""},
        {"id": "2", "type": "multiple_choice", "prompt": "Q\n`x=1`", "explanation": ""},
    ]
    new_rows, changed = fcb.convert_rows(rows, "python")
    assert changed == [("2", "prompt")]
    assert new_rows[0]["prompt"] == "Q\n`x=1`"


def _write_course(tmp_path, newline="\n", bom=True):
    (tmp_path / "source").mkdir()
    path = tmp_path / "source" / "cards.csv"
    encoding = "utf-8-sig" if bom else "utf-8"
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["id", "type", "prompt", "explanation"], lineterminator=newline
        )
        writer.writeheader()
        writer.writerow({"id": "1", "type": "multiple_choice", "prompt": "Q\n`x=1`\n`y=2`", "explanation": ""})
    return path


def test_check_mode_reports_and_writes_nothing(tmp_path, capsys):
    path = _write_course(tmp_path)
    before = path.read_bytes()
    assert fcb.main([str(tmp_path), "--lang", "python", "--check"]) == 1
    assert path.read_bytes() == before
    assert "card 1: prompt" in capsys.readouterr().out


def test_write_mode_rewrites_and_a_second_run_is_clean(tmp_path):
    path = _write_course(tmp_path)
    assert fcb.main([str(tmp_path), "--lang", "python", "--write"]) == 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["prompt"] == "Q\n```python\nx = 1\ny = 2\n```"
    assert fcb.main([str(tmp_path), "--lang", "python", "--check"]) == 0


def test_write_preserves_bom_and_crlf(tmp_path):
    path = _write_course(tmp_path, newline="\r\n", bom=True)
    fcb.main([str(tmp_path), "--lang", "python", "--write"])
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in raw


def test_blank_lines_are_collapsed_to_one_in_a_short_card_snippet():
    # black puts two blank lines after a def (right for a file, wasteful in a
    # four-line card); one keeps the block compact and is equally readable.
    code = fcb.format_python("def add(a,b):return a+b\nprint(add(2,3))")
    assert code == "def add(a, b):\n    return a + b\n\nprint(add(2, 3))"


def test_a_field_keeps_its_own_newline_style():
    # Git on Windows checks CSVs out with CRLF inside multi-line fields; the
    # converted text must not mix "\r\n" and "\n".
    crlf = fcb.convert("What prints?\r\n`x=1`\r\n`print(x)`", "python")
    assert crlf == "What prints?\r\n```python\r\nx = 1\r\nprint(x)\r\n```"
    lf = fcb.convert("What prints?\n`x=1`\n`print(x)`", "python")
    assert lf == "What prints?\n```python\nx = 1\nprint(x)\n```"
