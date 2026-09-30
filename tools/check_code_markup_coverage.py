#!/usr/bin/env python3
"""Find (and optionally fix) inline code that isn't wrapped in the app's
single-backtick markup.

The app (app/src/lib/inlineCode.ts) renders single-backtick spans
(`` `print()` ``) as styled monospace inline code inside otherwise plain
card text - prompt/options/explanation. validate_course.py's
_check_inline_code_markup already checks that any backticks a course DOES
use are well-formed (matched pairs, no triple-backtick fenced blocks), but
nothing checks whether code that appears UNMARKED should have been
backtick-wrapped in the first place. This script is that check - and,
with --fix, a mechanical (not judgment-based) fixer: wrapping an
already-correct span in backticks never changes the wording, only how it
renders, so it's safe to apply automatically once a pattern is
high-precision enough to trust.

Two kinds of unmarked code:
  1. A code token/call embedded inside an otherwise prose line (e.g.
     "print() takes whatever you pass it" - only "print()" is code).
  2. A WHOLE line that is itself a full code statement, inside a
     multi-line prompt on a card type with no dedicated code-block
     renderer (multiple_choice/true_false/etc. only render a CodeBlock for
     types like command_output/code_fill - anything else just prints each
     "\n"-separated line as plain prose unless backtick-wrapped). e.g. in
     "What does this print?\nfor i in range(3):\n    print(i)" the 2nd and
     3rd lines should each become one whole-line backtick span.

Usage:
    python tools/check_code_markup_coverage.py <course-folder>
    python tools/check_code_markup_coverage.py --all
    python tools/check_code_markup_coverage.py <course-folder> --fix
    python tools/check_code_markup_coverage.py --all --fix
"""
import argparse
import csv
import os
import re
import sys

CHECKED_FIELDS = ("prompt", "options", "explanation")

# "options" holds plain, index-graded DISPLAY choices only for these types
# (confirmed by reading each type's app/src/content/csvImport.ts case and,
# where relevant, its grade() function). Every other known type either
# stores exact-match GRADED strings there (type_answer/short_answer/
# code_fill's acceptedAnswers, command_output's expected output,
# listening_card's mode=="type" correctText), a value csvImport parses with
# parseFloat (numeric_answer - a stray backtick would make it NaN and throw
# on import), or a structurally-delimited mini-format ("left↔right" pairs,
# "~"-joined cloze blank groups, "x,y,w,h:label" regions) where an inserted
# backtick pair risks nothing semantically but isn't worth the parsing risk
# for a purely cosmetic change. Wrapping a GRADED string in backticks is a
# real, silent bug: the learner types the plain answer, csvImport's
# acceptedAnswers/output/correctText literally contains backtick characters,
# and the card becomes unsolvable. spot_error's segments already render
# through their own dedicated monospace styling (see spotErrorCard.tsx),
# so backtick-wrapping them would be redundant at best.
SAFE_OPTIONS_TYPES = {
    "multiple_choice", "true_false", "select_blank", "multi_select",
    "media_card", "reading_passage",
}

BACKTICK_SPAN_RE = re.compile(r"`[^`\n]+`")

# Inline candidates (span inside a prose line).
# The identifier must contain at least one real letter - without that
# lookahead, "___('hello')" (select_blank's own "___" placeholder directly
# against a call) matches this pattern too, since underscores alone are
# valid identifier characters, and wrapping it would swallow the blank
# marker itself into the backtick span.
CALL_RE = re.compile(
    r"\b(?=[A-Za-z_]*[A-Za-z])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\([^()\n]*\)"
)

# Curated subcommand whitelist per tool - NOT "any following word", which
# false-positived on ordinary English right after a tool name ("pip to
# install", "pip installs packages" both matched a looser "\s+\w+" pattern).
CLI_SUBCOMMANDS = {
    "git": "commit|push|pull|clone|checkout|branch|merge|status|add|init|log|diff|rebase|reset|stash|remote|fetch|tag",
    "docker": "run|build|pull|push|ps|images|exec|stop|start|rm|rmi|logs|compose",
    "pip": "install|uninstall|list|freeze|show",
    "pip3": "install|uninstall|list|freeze|show",
    "kubectl": "get|apply|delete|describe|logs|exec|create|scale|rollout|expose",
    "npm": "install|run|start|test|init|ci",
    "npx": "[a-z][a-z0-9_-]*",
    "python": "-m",
    "python3": "-m",
    "helm": "install|upgrade|uninstall|list|repo",
    "terraform": "init|plan|apply|destroy|validate",
    "aws": "[a-z][a-z0-9_-]*",
    "gcloud": "[a-z][a-z0-9_-]*",
    "az": "[a-z][a-z0-9_-]*",
}
CLI_RE = re.compile(
    "|".join(
        rf"\b{tool}\s+(?:{subs})\b" for tool, subs in CLI_SUBCOMMANDS.items()
    )
)
FLAG_RE = re.compile(r"(?<![\w-])(--[a-zA-Z][a-zA-Z0-9-]*|-[a-zA-Z](?!\w))")
FILENAME_RE = re.compile(
    r"\b[\w./\-]+\.(py|txt|json|ya?ml|csv|jsx?|tsx?|md|sh|toml|cfg|ini|"
    r"env|lock|gitignore|dockerignore)\b|"
    r"\b(Dockerfile|Makefile|requirements\.txt|package\.json|\.gitignore)\b"
)
# "git ___ file.txt": the tool name, a blank standing in for its subcommand, and an
# optional file-ish argument are ONE command. Matched on the blank placeholder.
CLI_BLANK_RE = re.compile(
    r"\b(?:git|docker|kubectl|pip3?|npm|npx|helm|terraform)\s+ZZBLANKZZ(?:\s+[\w./-]*[./-][\w./-]*)?"
)
INLINE_PATTERNS = [
    ("cli", CLI_BLANK_RE),
    ("call", CALL_RE),
    ("cli", CLI_RE),
    ("flag", FLAG_RE),
    ("filename", FILENAME_RE),
]

# Whole-line-is-code heuristics (only meaningful for multi-line text).
# The block-opener branch REQUIRES a literal colon somewhere in the line -
# without that, "with automatically closes the file for you..." and "class
# starts every class definition..." (real English explanation sentences)
# both matched a looser ".*:?\s*$" (colon optional) version of this pattern.
# return/import/from never take a colon in real Python, so those instead
# get a short-line length cap as their false-positive guard.
CODE_LINE_RE = re.compile(
    r"^\s*("
    r"(for|if|elif|while|def|class|try|except|finally|with|else)\b[^.!?]*:"
    r"|(return|import|from)\b(?=.{0,40}$)\S.*$"
    r"|[A-Za-z_][A-Za-z0-9_]*(\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*\s*=\s*.+$"  # assignment
    r"|[A-Za-z_][A-Za-z0-9_.]*\([^()]*\)\s*$"  # a line that IS just a call
    r")"
)


BLANK_RE = re.compile(r"___")

# Whether a select_blank's blank represents a code token (not a prose word)
# - the blank sits directly against code punctuation on either side, e.g.
# "___('hi')" or "self.___()" or "x___0" for "x != 0". This is the strongest
# available signal that every OPTION offered for that blank is also a code
# token (a candidate function/attribute/operator name), even options with
# no parentheses of their own to match CALL_RE on ("input", "write" next to
# "print()").
# NOTE: a bare "." is deliberately NOT a signal on its own - "Officials
# verify you meet all ___." (plain English, blank right before a sentence-
# ending period) is an extremely common, totally ordinary quiz-sentence
# shape across every non-technical course, and an earlier version of this
# regex included "." in the same char class as "(" / ":" / "=", which
# misfired on hundreds of civics/soft-skills cards (confirmed: canadian-
# citizenship, which has zero code content, showed 724 "fixes" before this
# was caught). A dot only counts when it's part of an attribute-access
# chain - a word character on the FAR side of the dot from the blank
# ("self.___" or "___.lower()"), never a bare trailing period.
BLANK_IS_CODE_CONTEXT_RE = re.compile(
    r"___[(\[]"      # ___( or ___[
    r"|[)\]]___"     # )___ or ]___
    r"|___="         # ___=
    r"|=___"         # =___
    r"|\w\.___"      # word.___  (e.g. self.___)
    r"|___\.\w"      # ___.word  (e.g. ___.lower())
)

# An option is safe to backtick-wrap as a bare code token only if it IS one
# - a single identifier/operator/short call, never a multi-word phrase (a
# select_blank's options are sometimes full clauses, e.g. "both must be
# truthy", which must never get wrapped just because a sibling option
# looks like code).
BARE_CODE_TOKEN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*(\(\))?$|^[!=<>]=?$|^-?\d+(\.\d+)?$")

def find_inline_candidates(text):
    if not text:
        return []
    backtick_spans = [(m.start(), m.end()) for m in BACKTICK_SPAN_RE.finditer(text)]

    def inside_backticks(pos):
        return any(s <= pos < e for s, e in backtick_spans)

    candidates = []
    seen_spans = []
    for kind, pattern in INLINE_PATTERNS:
        for m in pattern.finditer(text):
            if inside_backticks(m.start()):
                continue
            if any(not (m.end() <= s or m.start() >= e) for s, e in seen_spans):
                continue
            seen_spans.append((m.start(), m.end()))
            candidates.append((kind, m.group(), m.start(), m.end()))
    candidates.sort(key=lambda c: c[2])
    return candidates


FENCE_RE = re.compile(r"```.*?```", re.S)
# Stands in for the blank while scanning, so `t.___()` is seen (and wrapped) as ONE call.
BLANK_PLACEHOLDER = "ZZBLANKZZ"


def _fix_prose(text, whole_lines=True):
    """Fix one stretch of text that contains no fenced block."""
    if not text:
        return text, []
    if "___" in text and "`" in text:
        # Already marked up by the author. A `code span` may run straight through
        # the blank; scanning around it would cut the span in two and re-wrap
        # the pieces - leave the text alone.
        return text, []
    fixes = []
    new_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        scan = line.replace("___", BLANK_PLACEHOLDER)
        if whole_lines and "___" not in line and stripped and "`" not in line and CODE_LINE_RE.match(stripped):
            leading_ws = line[: len(line) - len(line.lstrip())]
            new_lines.append(f"{leading_ws}`{stripped}`")
            fixes.append(("whole-line", stripped))
            continue
        candidates = find_inline_candidates(scan)
        if not candidates:
            new_lines.append(line)
            continue
        out = []
        cursor = 0
        for kind, matched, start, end in candidates:
            out.append(scan[cursor:start])
            out.append(f"`{matched}`")
            fixes.append((kind, matched.replace(BLANK_PLACEHOLDER, "___")))
            cursor = end
        out.append(scan[cursor:])
        new_lines.append("".join(out).replace(BLANK_PLACEHOLDER, "___"))
    return "\n".join(new_lines), fixes


def fix_options_cell(text):
    """Fix an options cell option by option. Each option is inline-fixed on its own
    (never as a whole code line, and "|" is never inside a span)."""
    if not text:
        return text, []
    fixes = []
    parts = []
    for option in text.split("|"):
        if "`" in option:
            parts.append(option)
            continue
        fixed, option_fixes = fix_text(option, whole_lines=False)
        parts.append(fixed)
        fixes += option_fixes
    return "|".join(parts), fixes


def fix_text(text, whole_lines=True):
    """Return (new_text, list_of_fix_descriptions). Fenced code blocks are never touched."""
    if not text:
        return text, []
    pieces = []
    fixes = []
    cursor = 0
    for m in FENCE_RE.finditer(text):
        fixed, piece_fixes = _fix_prose(text[cursor : m.start()], whole_lines)
        pieces.append(fixed)
        fixes += piece_fixes
        pieces.append(m.group())
        cursor = m.end()
    fixed, piece_fixes = _fix_prose(text[cursor:], whole_lines)
    pieces.append(fixed)
    fixes += piece_fixes
    return "".join(pieces), fixes


def fix_options_field(options_text, ctype, prompt_text):
    """Bare-identifier options (no parens/dashes/dots - "print", "input",
    "return") never match any INLINE_PATTERNS on their own, but are
    unambiguously code when the row's blank/question is clearly about a
    code token: select_blank's blank sits directly against code
    punctuation ("___('hi')"), or a SIBLING option in the same list already
    reads as a call ("print()" next to "input"). Only fires when EVERY
    non-empty option is itself a plausible bare code token (single
    identifier/operator/number) - if any option is a real phrase, the
    whole row is left alone rather than partially wrapped, so the choice
    list stays visually consistent."""
    if ctype not in SAFE_OPTIONS_TYPES or not options_text or "`" in options_text:
        return options_text, []
    options = options_text.split("|")
    non_empty = [o for o in options if o.strip()]
    if not non_empty or not all(BARE_CODE_TOKEN_RE.match(o.strip()) for o in non_empty):
        return options_text, []

    code_context = bool(BLANK_IS_CODE_CONTEXT_RE.search(prompt_text or ""))
    sibling_is_call = any(CALL_RE.search(o) for o in non_empty)
    if not (code_context or sibling_is_call):
        return options_text, []

    fixes = []
    new_options = []
    for o in options:
        if o.strip() and "`" not in o:
            new_options.append(f"`{o}`")
            fixes.append(("option", o))
        else:
            new_options.append(o)
    return "|".join(new_options), fixes


def csv_quote(value):
    """The text as it sits in the CSV file (quoted when it has commas, quotes or newlines)."""
    if re.search(r'[,"\r\n]', value):
        return '"' + value.replace('"', '""') + '"'
    return value


def check_or_fix_course(course_dir, do_fix):
    cards_path = os.path.join(course_dir, "source", "cards.csv")
    if not os.path.exists(cards_path):
        return None
    with open(cards_path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    field_idx = {name: header.index(name) for name in CHECKED_FIELDS if name in header}
    id_idx = header.index("id")
    type_idx = header.index("type")
    prompt_idx = header.index("prompt")

    all_fixes = []
    for row in rows[1:]:
        cid = row[id_idx]
        ctype = row[type_idx]
        for field, idx in field_idx.items():
            if field == "options" and ctype not in SAFE_OPTIONS_TYPES:
                continue
            text = row[idx]
            if field == "options":
                new_text, fixes = fix_options_field(text, ctype, row[prompt_idx])
                if not fixes:
                    new_text, fixes = fix_options_cell(text)
            else:
                new_text, fixes = fix_text(text)
            if fixes:
                all_fixes.append((cid, field, fixes, text, new_text))
                if do_fix:
                    row[idx] = new_text

    if do_fix and all_fixes:
        with open(cards_path, "rb") as f:
            raw = f.read().decode("utf-8")
        for _cid, _field, _fixes, old, new in all_fixes:
            raw = raw.replace(csv_quote(old), csv_quote(new))
        with open(cards_path, "wb") as f:
            f.write(raw.encode("utf-8"))

    return all_fixes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course", nargs="?", help="path to a single course folder")
    parser.add_argument("--all", action="store_true", help="check every course folder at the repo root")
    parser.add_argument("--fix", action="store_true", help="rewrite cards.csv, wrapping candidates in backticks")
    args = parser.parse_args()

    if args.all:
        root = "."
        course_dirs = sorted(
            d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))
            and os.path.exists(os.path.join(root, d, "source", "cards.csv"))
        )
    elif args.course:
        course_dirs = [args.course]
    else:
        parser.print_help()
        sys.exit(1)

    total = 0
    for course_dir in course_dirs:
        results = check_or_fix_course(course_dir, args.fix)
        if results is None:
            continue
        name = os.path.basename(os.path.normpath(course_dir))
        if not results:
            print(f"{name}: clean (0 unmarked code candidates)")
            continue
        n = sum(len(fixes) for _, _, fixes, _, _ in results)
        verb = "fixed" if args.fix else "candidate(s) found"
        print(f"\n=== {name}: {n} {verb} across {len(results)} field(s) ===")
        for cid, field, fixes, old, new in results:
            for kind, matched in fixes:
                print(f'  card {cid} [{field}] ({kind}): "{matched}"')
        total += n

    verb = "fixed" if args.fix else "candidates"
    print(f"\nTOTAL {verb} across {len(course_dirs)} course(s): {total}")


if __name__ == "__main__":
    main()
