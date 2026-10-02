#!/usr/bin/env python3
"""Finds (and optionally fixes) English grammar errors of the kind Farsi
speakers make and that course text can accidentally teach: "I want a
water" (a/an before an uncountable noun), "I am agree", "I have 20
years", "a apple", "she have"... Farsi has no articles and no
countable/uncountable split, so these slip past an author who is also
fluent in Farsi and read the sentence as "fine".

Two layers, same pattern as check_self_standing.py:

1. Deterministic rules (RULES below) — free, 100% reliable, no LLM. Each
   rule carries its own replacement, so these are auto-fixable.
2. A local LLM pass (LM Studio, default google/gemma-4-e4b, must be
   loaded with --context-length 16384) for everything the rules can't
   express. The model must quote the wrong text EXACTLY as it appears
   in the card; a quote that isn't a real substring is dropped, so a
   hallucinated "original" can never edit anything.

Modes:
    (default)  check only — writes findings to <repo root>/english_grammar_report.txt
    --fix      also applies the SAFE fixes to cards.csv / glossary.csv

A fix is "safe" only when it can't break the card's meaning:
  * never touches a wrong option of a choice-type card (that may be a
    deliberate distractor — reported as "needs review" instead);
  * never makes two options of a card identical;
  * model (LLM) findings are NEVER auto-applied — always "needs review"
    (only the deterministic rules edit files).
Everything else is reported as "needs review" for a human or an LLM assistant.

Resumable: <course>/.internal/english_grammar_state.json keeps a hash of
each card's English text, so an edited card is re-checked and an
untouched one is not re-asked.

Usage:
    python tools/check_english_grammar.py <course-folder> [--fix] [--no-llm] [--model NAME] [--batch-size N]
    python tools/check_english_grammar.py --all [--fix] ...
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import time
import urllib.request

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_MODEL = "google/gemma-4-e4b"
BATCH_SIZE_DEFAULT = 8

CHOICE_TYPES = {"multiple_choice", "multi_select", "select_blank", "image_choice"}
# Fields that can hold English learner-facing text.
CARD_FIELDS = ("prompt", "options", "explanation")
GLOSSARY_FIELDS = ("definition",)

RTL_RE = re.compile(r"[֐-ࣿיִ-﷿ﹰ-﻿]")
LATIN_RE = re.compile(r"[A-Za-z]")
WORD_RE = re.compile(r"[A-Za-z']+")
DANGLING_END = re.compile(r"\s(a|an|the|to|some|is|am|are|want|need|have|from|of|in|at|my|your)$", re.I)
BLANK_RE = re.compile(r"\{\{\d+\}\}|___")

# ---------------------------------------------------------------- rules
# Nouns English treats as uncountable — "a/an" before one is an error.
# (a coffee / a tea / a juice are deliberately absent: "a coffee, please"
# is ordinary countable use when ordering.)
UNCOUNTABLE = (
    "water|rice|bread|milk|money|information|advice|furniture|luggage|"
    "baggage|homework|food|sugar|salt|news|traffic|weather|music|help|"
    "butter|cheese|meat|fruit|soup|oil|paper|work|time|luck|"
    "equipment|traffic|progress|knowledge"
)
# a-before-vowel-sound exceptions ("a university") and an-before-
# consonant-letter exceptions ("an hour").
A_BEFORE_VOWEL_OK = re.compile(
    r"^(uni\w*|use\w*|usual\w*|eu\w*|one\w*|once|ubiq\w*|ut\w*)$", re.I)
AN_BEFORE_CONSONANT_OK = re.compile(r"^(hour\w*|honest\w*|honou?r\w*|heir\w*)$", re.I)


def _keep_case(src, repl):
    return repl.capitalize() if src[:1].isupper() else repl


def _mass_noun_fix(m):
    # "I want a water" -> "I want water" (the blunt-but-correct form the
    # courses teach for ordering); elsewhere "a water" -> "some water".
    verb, art, noun = m.group(1), m.group(2), m.group(3)
    if verb:
        return f"{verb} {noun}"
    return f"{_keep_case(art, 'some')} {noun}"


def _article_fix(m):
    art, word = m.group(1), m.group(2)
    if word.isupper():  # acronym: "an SQL", "a US" — sound depends on the letters
        return m.group(0)
    low = art.lower()
    if low == "a" and re.match(r"[aeiou]", word, re.I) and not A_BEFORE_VOWEL_OK.match(word):
        return _keep_case(art, "an") + " " + word
    if low == "an" and re.match(r"[bcdfgjklmnpqrstvwxyz]", word, re.I) and not AN_BEFORE_CONSONANT_OK.match(word):
        return _keep_case(art, "a") + " " + word
    return m.group(0)


RULES = [
    # (name, compiled regex, replacement callable or string, explanation)
    ("article-uncountable",
     re.compile(rf"\b(?:(want|wants|need|needs)\s+)?(a|an)\s+({UNCOUNTABLE})\b(?!\s+of\b)", re.I),
     _mass_noun_fix,
     "'a/an' can't go before an uncountable noun — use 'some' (or no article)."),
    ("article-a-an",
     re.compile(r"\b(a|an)\s+([a-z]+)\b", re.I),
     _article_fix,
     "'a' goes before a consonant sound, 'an' before a vowel sound."),
    ("am-agree",
     re.compile(r"\b(I|we|you|they)\s+(am|are)\s+agree\b", re.I),
     lambda m: f"{m.group(1)} agree",
     "'agree' is a verb — 'I agree', not 'I am agree'."),
    ("age-have",
     re.compile(r"\bI have (\d+) years?( old)?\b", re.I),
     lambda m: f"I am {m.group(1)} years old",
     "English says age with 'be': 'I am 20 years old'."),
    ("third-person-have",
     re.compile(r"\b(he|she|it)\s+have\b", re.I),
     lambda m: f"{m.group(1)} has",
     "Third person singular: 'has', not 'have'."),
    ("third-person-dont",
     re.compile(r"\b(he|she|it)\s+don't\b", re.I),
     lambda m: f"{m.group(1)} doesn't",
     "Third person singular: 'doesn't', not 'don't'."),
    ("plural-be",
     re.compile(r"\b(he|she|it)\s+are\b", re.I),
     lambda m: f"{m.group(1)} is",
     "Third person singular takes 'is'."),
]


def apply_rules(text):
    """Return (fixed_text, [ (rule_name, before, after, why) ])."""
    findings = []
    for name, rx, repl, why in RULES:
        def sub(m, repl=repl, name=name, why=why):
            out = repl(m) if callable(repl) else m.expand(repl)
            if out != m.group(0):
                findings.append((name, m.group(0), out, why))
            return out
        text = rx.sub(sub, text)
    return text, findings


# ----------------------------------------------------- text extraction
def english_segments(field, value):
    """English learner-facing strings inside one CSV cell.

    A segment is a line (or option) that has Latin letters, no RTL
    characters, and at least two words — a lone "Hello" has no grammar
    to get wrong, and a line mixing Farsi and English is a bilingual
    frame, not an English sentence.
    """
    if not value:
        return []
    parts = []
    for line in value.split("\n"):
        if field == "options":
            for opt in re.split(r"[|~↔]", line):
                parts.append(opt)
        else:
            parts.append(line)
    segs = []
    for p in parts:
        has_blank = bool(BLANK_RE.search(p))
        p = re.sub(r"\s+", " ", BLANK_RE.sub("", p).replace("`", "")).strip()
        if not p or RTL_RE.search(p) or not LATIN_RE.search(p):
            continue
        # A sentence with a blank, or a chip that stops mid-phrase
        # ("I want", "I need a"), is a fragment by design, not an error.
        if has_blank or DANGLING_END.search(p) or re.search(r"\s[.,!?]", p):
            continue
        if len(WORD_RE.findall(p)) < 2:
            continue
        segs.append(p)
    return segs


def text_hash(strings):
    return hashlib.sha1("\x1f".join(strings).encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


# ----------------------------------------------------------------- LLM
SYSTEM_PROMPT = (
    "You proofread English text written for native Farsi speakers who are "
    "LEARNING English. Farsi has no articles and no countable/uncountable "
    "distinction, so the typical errors are: 'a/an' before an uncountable "
    "noun ('I want a water' -> 'I want some water'), a missing or wrong "
    "article, wrong 'a'/'an', missing verb 'to be' ('She happy'), "
    "'I am agree', 'I have 20 years', wrong subject-verb agreement, wrong "
    "prepositions, wrong word order, wrong plural forms.\n"
    "You get several cards. Each card lists English strings. For every "
    "string with a REAL grammatical or unnatural-phrasing error, report the "
    "exact wrong text and the corrected text.\n"
    "Rules:\n"
    "- 'original' MUST be copied character-for-character from the string.\n"
    "- Keep the fix minimal — change only what is wrong, keep the meaning, "
    "keep it beginner-level, never add or remove sentences.\n"
    "- Do NOT report capitalization, punctuation, style preferences, or a "
    "correct-but-blunt sentence like 'I want water'. Never report a string "
    "whose corrected form is identical to the original.\n"
    "- Fragments, labels and menu-style phrases ('Menu, please', 'quarter "
    "past', 'a Discount'), single words, names, and short dialogue lines "
    "are acceptable unless clearly wrong.\n"
    "- Do NOT report a string a card deliberately shows as WRONG (a "
    "distractor option or an error-spotting question) — only report text "
    "the course presents as CORRECT English. If you can't tell, skip it.\n"
    "Respond ONLY with a JSON array, one object per card that has at least "
    "one error (omit clean cards), no markdown fences:\n"
    '[{"id": "...", "errors": [{"original": "...", "fixed": "...", "why": "..."}]}]\n'
    "If every card is clean respond with []."
)


def call_llm(model, user_content, max_tokens=2500, retries=3):
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        LM_STUDIO_URL, data=payload, headers={"Content-Type": "application/json"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:  # nosec B310  # URL is a fixed constant / operator config, not user input
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LM Studio call failed after {retries} attempts: {last_err}")


def extract_json_array(text):
    text = (text or "").strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


_CONTRACTIONS = [(r"\bi'm\b", "i am"), (r"\bit's\b", "it is"), (r"\bthat's\b", "that is"),
                 (r"\bdon't\b", "do not"), (r"\bdoesn't\b", "does not"),
                 (r"\bcan't\b", "can not"), (r"\bi'll\b", "i will"), (r"\bi've\b", "i have")]


def _norm(t):
    t = t.lower().replace("’", "'")
    for rx, full in _CONTRACTIONS:
        t = re.sub(rx, full, t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def is_real_change(original, fixed):
    """False for a no-op or a case/punctuation-only 'fix' — the small
    model reports plenty of those and they are not grammar errors."""
    a, b = _norm(original), _norm(fixed)
    if not fixed or a == b:
        return False
    # Only appending words = the model "completing" a fragment.
    return not b.startswith(a + " ")


def llm_fix_is_sane(original, fixed):
    """A model 'fix' must stay small and stay Latin-script English."""
    if not fixed or fixed == original:
        return False
    if RTL_RE.search(fixed):
        return False
    if len(fixed) > len(original) * 1.6 + 8 or len(fixed) < len(original) * 0.5 - 4:
        return False
    return True


# ------------------------------------------------------------ planning
def plan_card_fixes(card, findings):
    """Split findings into (safe, review) for one card.

    findings: list of (source, original, fixed, why) where source is
    "rule" or "llm". Returns two lists of (original, fixed, why, source).
    """
    ctype = card.get("type", "")
    correct = set()
    if ctype in CHOICE_TYPES:
        correct = {c.strip() for c in re.split(r"[|,]", card.get("correct_index", "") or "")}
    options = [o.strip() for o in re.split(r"[|~↔]", card.get("options", "") or "")]

    safe, review = [], []
    seen = set()
    for source, original, fixed, why in findings:
        key = (original, fixed)
        if key in seen:
            continue
        seen.add(key)
        item = (original, fixed, why, source)
        if source == "llm":
            # The small local model is right often enough to be worth
            # reading, never often enough to edit content unsupervised.
            review.append(item)
            continue
        if ctype in CHOICE_TYPES and original in options:
            # A wrong option might be a deliberate distractor — only the
            # correct option (which the course presents as right English)
            # is safe to rewrite.
            idx = options.index(original)
            if str(idx) not in correct:
                review.append(item)
                continue
            if fixed in options:
                review.append(item)
                continue
        safe.append(item)
    return safe, review


def apply_fixes_to_row(row, fields, safe):
    """Exact-substring replace inside the given fields. Returns count applied."""
    applied = 0
    for original, fixed, _why, _src in safe:
        for f in fields:
            val = row.get(f) or ""
            if original in val:
                row[f] = val.replace(original, fixed)
                applied += 1
    return applied


# ------------------------------------------------------------------ IO
def read_rows(path):
    if not os.path.isfile(path):
        return None, None, None
    with open(path, encoding="utf-8-sig", newline="") as f:
        raw = f.read()
    bom = open(path, "rb").read(3) == b"\xef\xbb\xbf"
    eol = "\r\n" if "\r\n" in raw else "\n"
    reader = csv.DictReader(io.StringIO(raw, newline=""))
    rows = list(reader)
    return rows, (reader.fieldnames, eol, bom), raw


def write_rows(path, rows, meta):
    fieldnames, eol, bom = meta
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator=eol)
        w.writeheader()
        w.writerows(rows)


def report_line(course, kind, ident, original, fixed, why, status):
    o = original.replace("\n", " ")
    fx = fixed.replace("\n", " ")
    return f'{course} | {kind} {ident} | "{o}" -> "{fx}" | {why} | {status}\n'


def check_source(course_dir, csv_name, fields, kind, model, batch_size, use_llm,
                 fix, report_path, state):
    name = os.path.basename(course_dir.rstrip("/\\"))
    path = os.path.join(course_dir, "source", csv_name)
    rows, meta, _raw = read_rows(path)
    if not rows:
        return 0, 0
    tag = ":llm" if use_llm else ":rules"
    idkey = "id" if "id" in rows[0] else next(iter(rows[0]))

    # rows -> {ident: [(field, segment)]}
    todo = []
    for row in rows:
        ident = str(row.get(idkey, ""))
        segs = [s for f in fields for s in english_segments(f, row.get(f, ""))]
        if not segs:
            continue
        h = text_hash(segs)
        # An LLM-checked card is also rule-checked; a rules-only pass must
        # not stop a later LLM pass from looking at the card.
        done = {h + ":llm"} if use_llm else {h + ":llm", h + ":rules"}
        if state.get(f"{csv_name}:{ident}") in done:
            continue
        todo.append((row, ident, segs, h))
    if not todo:
        print(f"  {name}/{csv_name}: nothing new to check")
        return 0, 0

    findings_by_id = {}
    # Layer 1: rules — over the raw text of every field, so a fix
    # replaces exactly what is in the CSV.
    for row, ident, segs, _h in todo:
        for seg in segs:
            _fixed, hits = apply_rules(seg)
            for rule_name, before, after, why in hits:
                findings_by_id.setdefault(ident, []).append(("rule", before, after, why))

    # Layer 2: LLM over cards the rules left clean OR dirty (the model can
    # still find a second error), batched.
    if use_llm:
        for i in range(0, len(todo), batch_size):
            batch = todo[i:i + batch_size]
            blocks = []
            for _row, ident, segs, _h in batch:
                lines = "\n".join(f"  - {s}" for s in segs)
                blocks.append(f"id={ident}\n{lines}")
            try:
                parsed = extract_json_array(call_llm(model, "\n---\n".join(blocks)))
            except Exception as e:  # noqa: BLE001
                print(f"    batch {i}-{i+len(batch)} FAILED: {e}")
                continue
            if parsed is None:
                print(f"    batch {i}-{i+len(batch)}: could not parse model output, skipping")
                continue
            segs_by_id = {ident: segs for _r, ident, segs, _h in batch}
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                ident = str(item.get("id"))
                if ident not in segs_by_id:
                    continue
                for err in item.get("errors") or []:
                    orig = (err.get("original") or "").strip()
                    fixed = (err.get("fixed") or "").strip()
                    why = (err.get("why") or "LLM-flagged").strip()
                    # Anti-hallucination: quote must be real text on the card.
                    if orig and is_real_change(orig, fixed) and any(orig in s for s in segs_by_id[ident]):
                        findings_by_id.setdefault(ident, []).append(("llm", orig, fixed, why))
            print(f"    batch {i}-{i+len(batch)} done")

    lines_out, n_found, n_fixed = [], 0, 0
    for row, ident, _segs, h in todo:
        found = findings_by_id.get(ident, [])
        if not found:
            state[f"{csv_name}:{ident}"] = h + tag
            continue
        safe, review = plan_card_fixes(row, found)
        n_found += len(safe) + len(review)
        if fix and safe:
            applied = apply_fixes_to_row(row, fields, safe)
            n_fixed += len(safe) if applied else 0
            for original, fixed, why, _s in safe:
                lines_out.append(report_line(name, kind, ident, original, fixed, why, "auto-fixed"))
        else:
            for original, fixed, why, _s in safe:
                lines_out.append(report_line(name, kind, ident, original, fixed, why, "fixable (run --fix)"))
        for original, fixed, why, _s in review:
            lines_out.append(report_line(name, kind, ident, original, fixed, why, "NEEDS REVIEW"))
        # Only mark the card done if nothing is left for a human; an
        # unresolved finding stays re-checkable.
        if not review and (fix or not safe):
            new_segs = [s for f in fields for s in english_segments(f, row.get(f, ""))]
            state[f"{csv_name}:{ident}"] = text_hash(new_segs) + tag

    if lines_out:
        with open(report_path, "a", encoding="utf-8") as f:
            f.writelines(lines_out)
    if fix and n_fixed:
        write_rows(path, rows, meta)
    print(f"  {name}/{csv_name}: {n_found} issue(s), {n_fixed} auto-fixed")
    return n_found, n_fixed


def check_course(course_dir, args, report_path):
    state_dir = os.path.join(course_dir, ".internal")
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, "english_grammar_state.json")
    state = {}
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    use_llm = not args.no_llm
    check_source(course_dir, "cards.csv", CARD_FIELDS, "card", args.model,
                 args.batch_size, use_llm, args.fix, report_path, state)
    check_source(course_dir, "glossary.csv", GLOSSARY_FIELDS, "term", args.model,
                 args.batch_size, use_llm, args.fix, report_path, state)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def find_all_course_dirs(root):
    return [os.path.join(root, e) for e in sorted(os.listdir(root))
            if os.path.isfile(os.path.join(root, e, "meta.json"))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--fix", action="store_true", help="apply the safe fixes to the CSVs")
    ap.add_argument("--no-llm", action="store_true", help="deterministic rules only")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()
    if not (args.all or args.course):
        ap.error("pass a course folder or --all")
    course_dirs = find_all_course_dirs(os.getcwd()) if args.all else [args.course]
    report_path = args.report or os.path.join(os.getcwd(), "english_grammar_report.txt")
    print(f"English grammar check, {len(course_dirs)} course(s), "
          f"{'rules only' if args.no_llm else 'model=' + args.model}, "
          f"{'FIX' if args.fix else 'check only'}")
    print(f"Report: {report_path}")
    for d in course_dirs:
        check_course(d, args, report_path)


if __name__ == "__main__":
    main()
