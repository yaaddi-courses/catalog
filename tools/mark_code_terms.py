#!/usr/bin/env python3
"""Wrap bare code words in card text in the app's single-backtick markup.

check_code_markup_coverage.py catches code that LOOKS like code (calls such as
`print()`, flags, file names, whole statements). This tool catches the plain
WORDS that are code when a lesson talks about them: the `for` in "a for loop",
`True`, `None`, `self`, `__init__`, and a keyword quoted as 'and'. They read as
ordinary English until they are marked, so they render in the prose font
instead of the code font (owner, 2026-09-30).

Deliberately conservative - a word is only marked when the surrounding text
makes it code:
  * a structural keyword directly before loop/statement/keyword/clause/block/
    expression ("a for loop" -> "a `for` loop"),
  * in/is/not/and/or/as only before "operator" or "keyword",
  * a keyword in quotes ("'and'" -> "`and`"),
  * the Python constants True/False/None (not at the start of a sentence, not
    "None of ...") and self / cls / dunder names (not "self-deadlocks"),
and only in Python courses (slug contains "python" or "pytest"), where those
words are always code. Text already inside a `span` or a fenced block is left
alone, and so is the ___ blank.

Usage:
    python tools/mark_code_terms.py --all            # report
    python tools/mark_code_terms.py --all --fix      # rewrite cards.csv
    python tools/mark_code_terms.py <course-folder> [--fix]
"""
import argparse
import csv
import io
import os
import re
import sys

from check_code_markup_coverage import csv_quote

STRUCTURAL_KEYWORDS = (
    "for|while|if|elif|else|try|except|finally|with|def|class|import|from|lambda|return|"
    "yield|break|continue|pass|raise|assert|global|nonlocal|del"
)
OPERATOR_WORDS = "in|is|not|and|or|as"
ALL_KEYWORDS = f"{STRUCTURAL_KEYWORDS}|{OPERATOR_WORDS}"
NOUNS = r"(?:loops?|statements?|keywords?|clauses?|blocks?|expressions?)\b"
# "a for loop", "the else clause": a structural keyword right before its noun.
KEYWORD_WITH_NOUN_RE = re.compile(
    rf"(?<![`\w])({STRUCTURAL_KEYWORDS})(?![`\w])(?=\s+{NOUNS})"
)
# "the in operator", "the is keyword": an operator word only before operator/keyword.
OPERATOR_WORD_RE = re.compile(
    rf"(?<![`\w])({OPERATOR_WORDS})(?![`\w])(?=\s+(?:operators?|keywords?)\b)"
)
QUOTED_KEYWORD_RE = re.compile(rf"""(?<![`\w])['"]({ALL_KEYWORDS})['"](?![`\w])""")
TRY_SLASH_RE = re.compile(r"(?<![`\w])(try)(?=/`?(?:finally|except|else)\b)")
CONSTANT_RE = re.compile(
    r"(?<![`\w'])(True|False|None|self|cls|__\w+__)(?![`\w-])(?!\s+of\b)"
)
# True/False/None at the start of a sentence are plain English ("True. Because ...",
# "True about X?"), not the constants.
SENTENCE_START_RE = re.compile(r"(?:^|[.!?;:\n])\s*$")
# ...unless it is clearly the constant used as a subject: "True and False are ...", "True is ...".
CONSTANT_SUBJECT_RE = re.compile(r"\s+(?:and|or|is|are)\b|\s*[:/]")
FIELDS = ("prompt", "explanation")
FENCE_RE = re.compile(r"```.*?```", re.S)
SPAN_RE = re.compile(r"`[^`\n]+`")


def is_python_course(name: str) -> bool:
    return "python" in name or "pytest" in name


def _protected_ranges(text: str):
    return [(m.start(), m.end()) for rx in (FENCE_RE, SPAN_RE) for m in rx.finditer(text)]


def mark_code_terms(text: str) -> tuple[str, int]:
    """Returns (new_text, number_of_words_marked)."""
    if not text:
        return text, 0
    # A span that runs through a blank cannot be scanned piecewise: leave it to the author
    # (same rule as check_code_markup_coverage).
    if "___" in text and text.count("`") % 2 == 1:
        return text, 0
    protected = _protected_ranges(text)

    def free(start: int, end: int) -> bool:
        return not any(not (end <= s or start >= e) for s, e in protected)

    edits: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for m in QUOTED_KEYWORD_RE.finditer(text):
        if free(m.start(), m.end()):
            edits.append((m.start(), m.end(), f"`{m.group(1)}`"))
            taken.append((m.start(), m.end()))
    for rx in (KEYWORD_WITH_NOUN_RE, OPERATOR_WORD_RE, CONSTANT_RE):
        for m in rx.finditer(text):
            start, end = m.start(1), m.end(1)
            if not free(start, end) or any(not (end <= s or start >= e) for s, e in taken):
                continue
            if (
                rx is CONSTANT_RE
                and m.group(1)[0].isupper()
                and SENTENCE_START_RE.search(text[:start])
                and not CONSTANT_SUBJECT_RE.match(text[end:])
            ):
                continue
            edits.append((start, end, f"`{m.group(1)}`"))
            taken.append((start, end))
            if rx is KEYWORD_WITH_NOUN_RE:
                if text[max(0, start - 4) : start] == "try/" and free(start - 4, start - 1):
                    edits.append((start - 4, start - 1, "`try`"))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, len(edits)


def process_course(course_dir: str, fix: bool) -> list[tuple[str, str, str]]:
    path = os.path.join(course_dir, "source", "cards.csv")
    with open(path, "rb") as handle:
        raw = handle.read().decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(raw, newline="")))
    changes = []
    for row in rows:
        for field in FIELDS:
            new, count = mark_code_terms(row[field])
            if count:
                changes.append((row["id"], row[field], new))
    if fix and changes:
        for _id, old, new in changes:
            raw = raw.replace(csv_quote(old), csv_quote(new))
        with open(path, "wb") as handle:
            handle.write(raw.encode("utf-8"))
    return changes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("course", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if args.all:
        courses = [
            d for d in sorted(os.listdir(root))
            if os.path.isfile(os.path.join(root, d, "source", "cards.csv"))
        ]
    elif args.course:
        courses = [os.path.basename(os.path.normpath(args.course))]
    else:
        parser.error("give a course folder or --all")
    total = 0
    for name in courses:
        if not is_python_course(name):
            continue
        changes = process_course(os.path.join(root, name), args.fix)
        total += len(changes)
        print(f"{name}: {len(changes)} field(s) {'fixed' if args.fix else 'to mark'}")
        for card_id, old, new in changes[:200]:
            print(f"  card {card_id}: {old[:80]!r} -> {new[:80]!r}")
    return 0 if args.fix or total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
