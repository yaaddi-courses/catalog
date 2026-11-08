"""Whole-term, case-insensitive regex matching for glossary terms, shared by the tools that look
for a term in card text (apply_clean_ledger, check_key_term_usage, propose_term_ledger,
llm_fix_exercise_only_terms, llm_fix_forward_refs).

`\\b` only sits between a word and a non-word character, so `\\bC\\+\\+\\b` never matches "C++"
followed by a space, and terms like ".dockerignore", "-p", "start()" or "How are you?" were never
found. The lookarounds below mean "not inside a longer word" on each side instead, which works
whatever the term's first and last characters are.
"""
import re


def build_matcher(terms):
    """One compiled regex for every term, longest first (so "Governor General" wins over
    "Governor"); None when there are no terms."""
    ordered = sorted(set(terms), key=len, reverse=True)
    if not ordered:
        return None
    pattern = "|".join(re.escape(t) for t in ordered)
    return re.compile(rf"(?<!\w)(?:{pattern})(?!\w)", re.IGNORECASE)


def build_word_pattern(term):
    return build_matcher([term])
