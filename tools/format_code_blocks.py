#!/usr/bin/env python3
"""Turns a course's code samples into properly formatted fenced code blocks.

The app renders two code conventions in card text (`prompt` / `explanation`):

* a single-backtick span (`` `x = 1` ``) — short code INSIDE a sentence;
* a triple-backtick fenced block (```python ... ```) — a code sample that
  stands on its own line(s): monospace, indentation kept, syntax colored per
  language (see app/docs/CARD_TYPES.md, "Code in free text").

Older cards wrote a multi-line snippet as one inline span PER LINE
(`` `x=0` `` / `` `if x:print('a')` `` / ...), which shows as unrelated
chips. This tool rewrites every run of code lines into ONE fenced block,
keeping each line's own indentation, and — for Python — normalizes the code
itself (spacing, one statement per line, 4-space indentation) via `ast`,
refusing to change anything whose parsed meaning would differ.

A "code line" is either a line that is exactly one inline span, or (Python) a
line whose pieces were wrapped in spans by hand (``print(`len(x)`)``) and that
parses as code once the backticks are removed. Prose that merely contains
inline spans is never touched. A line that looks like broken-up code but cannot
be repaired safely is reported as MANUAL and its card is left alone. The tool
is idempotent: text that already holds a fenced block is left alone.

Usage:
    python tools/format_code_blocks.py <course-folder> --lang python           # report only
    python tools/format_code_blocks.py <course-folder> --lang python --write   # rewrite cards.csv
    python tools/format_code_blocks.py <course-folder> --lang python --check   # exit 1 if work is needed

Run it, fix any MANUAL cards by hand, then rebuild the course zip and bump
`meta.json`'s version (see AUTHORING.md).
"""
from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from pathlib import Path

FIELDS = ("prompt", "explanation")
# Card types whose renderer nests the text inside another <Text>, where a
# block-level code view cannot legally sit (select_blank builds a sentence
# out of inline chips). Their text is never converted.
SKIP_TYPES = frozenset({"select_blank"})

CODE_KEYWORD_LINE = re.compile(
    r"^\s*(for|if|while|def|class|else|elif|try|except|finally|with|import|from|return|print)\b"
)
# Three or more real words (2+ letters) outside any span means the line is a sentence.
WORD = re.compile(r"[A-Za-z]{2,}")


def is_span_line(line: str) -> bool:
    """True for a line that is exactly one inline code span, e.g. ``x = 1``."""
    stripped = line.strip()
    return (
        len(stripped) >= 3
        and stripped.startswith("`")
        and stripped.endswith("`")
        and "`" not in stripped[1:-1]
    )


def _python_tree(code: str) -> ast.Module | None:
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def classify_line(line: str, language: str) -> str:
    """'span' (exactly one inline span), 'mixed-code' (Python only: hand-wrapped
    pieces that parse as code once the backticks are removed), 'prose', or
    'manual' (looks like broken-up code but cannot be repaired safely)."""
    if "`" not in line:
        return "prose"
    if is_span_line(line):
        return "span"
    if language == "python":
        tree = _python_tree(line.replace("`", "").strip())
        if tree is not None and tree.body:
            only = tree.body[0] if len(tree.body) == 1 else None
            # A bare word or literal is just a sentence fragment that happens to parse.
            lone_word = (
                isinstance(only, ast.Expr) and isinstance(only.value, (ast.Name, ast.Constant))
            )
            if not lone_word:
                return "mixed-code"
    outside_spans = re.sub(r"`[^`]*`", " ", line)
    if len(WORD.findall(outside_spans)) >= 3:
        return "prose"
    if line.count("`") >= 4 or CODE_KEYWORD_LINE.match(line):
        return "manual"
    return "prose"


def needs_manual_review(text: str, language: str = "python") -> bool:
    """True when some line looks like code broken into spans by hand but cannot
    be repaired safely; the tool reports the card instead of guessing."""
    return any(classify_line(line, language) == "manual" for line in text.split("\n"))


def format_python(code: str) -> str:
    """Formats Python like a professional codebase would.

    Uses `black` when installed (keeps comments and the author's quote style,
    and itself verifies the result is equivalent code); otherwise falls back to
    `ast.unparse`, which is less pretty (parenthesizes tuple targets) and would
    drop comments, so comment-bearing code is then left as written. In both
    paths code that does not parse, or whose parsed meaning would change, is
    returned unchanged."""
    tree = _python_tree(code)
    if tree is None:
        return code
    try:
        import black

        formatted = black.format_str(code, mode=black.Mode(string_normalization=False)).rstrip("\n")
    except ImportError:
        if "#" in code:
            return code
        formatted = ast.unparse(tree)
    except Exception:  # black refused (e.g. internal error) - keep the author's text
        return code
    if ast.dump(ast.parse(formatted)) != ast.dump(tree):
        return code
    # black puts two blank lines after a def/class (right for a file, wasteful
    # in a few-line card snippet); collapse any run of blank lines to one.
    return re.sub(r"\n{3,}", "\n\n", formatted)


def to_fence(lines: list[str], language: str) -> str:
    """`lines` keep their own leading indentation."""
    code = "\n".join(lines)
    if language == "python":
        code = format_python(code)
    return f"```{language}\n{code}\n```"


def convert(text: str, language: str) -> str:
    """Replaces each run of consecutive code lines with one fenced block."""
    if "\r\n" in text:
        # Work in "\n" and give the field back in its own newline style
        # (Git on Windows checks CSVs out with CRLF inside multi-line fields).
        converted = convert(text.replace("\r\n", "\n"), language)
        return converted.replace("\n", "\r\n") if converted != text.replace("\r\n", "\n") else text
    if "```" in text or "`" not in text or needs_manual_review(text, language):
        return text
    lines = text.split("\n")
    kinds = [classify_line(line, language) for line in lines]
    out: list[str] = []
    i = 0
    while i < len(lines):
        if kinds[i] in ("span", "mixed-code"):
            snippet: list[str] = []
            while i < len(lines) and kinds[i] in ("span", "mixed-code"):
                line = lines[i]
                indent = line[: len(line) - len(line.lstrip())]
                body = line.strip()
                body = body[1:-1] if kinds[i] == "span" else body.replace("`", "")
                snippet.append(indent + body)
                i += 1
            out.append(to_fence(snippet, language))
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def manual_review_fields(rows: list[dict], language: str = "python") -> list[tuple[str, str]]:
    return [
        (row.get("id", "?"), field)
        for row in rows
        if row.get("type") not in SKIP_TYPES
        for field in FIELDS
        if needs_manual_review(row.get(field) or "", language)
    ]


def convert_rows(rows: list[dict], language: str) -> tuple[list[dict], list[tuple[str, str]]]:
    """Returns (new rows, [(card id, field)] that changed)."""
    changed: list[tuple[str, str]] = []
    result = []
    for row in rows:
        new_row = dict(row)
        if row.get("type") not in SKIP_TYPES:
            for field in FIELDS:
                original = row.get(field) or ""
                converted = convert(original, language)
                if converted != original:
                    new_row[field] = converted
                    changed.append((row.get("id", "?"), field))
        result.append(new_row)
    return result, changed


def process_course(
    course_dir: Path, language: str, write: bool
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Returns (changed fields, fields left for manual review)."""
    path = course_dir / "source" / "cards.csv"
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    new_rows, changed = convert_rows(rows, language)
    if write and changed:
        with path.open("w", encoding="utf-8-sig" if has_bom else "utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator=newline)
            writer.writeheader()
            writer.writerows(new_rows)
    return changed, manual_review_fields(rows, language)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course", type=Path, help="course folder (contains source/cards.csv)")
    parser.add_argument("--lang", required=True, help="fence language tag for this course's code (python, sql, ...)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="rewrite source/cards.csv in place")
    mode.add_argument("--check", action="store_true", help="exit 1 when work is needed, write nothing")
    args = parser.parse_args(argv)

    changed, manual = process_course(args.course, args.lang.strip().lower(), write=args.write)
    for card_id, field in changed:
        print(f"card {card_id}: {field}")
    for card_id, field in manual:
        print(f"MANUAL: card {card_id}: {field} looks like broken-up code - fix by hand")
    verb = "rewrote" if args.write else "would rewrite"
    print(f"{verb} {len(changed)} field(s); {len(manual)} need manual review")
    return 1 if (args.check and (changed or manual)) else 0


if __name__ == "__main__":
    sys.exit(main())
