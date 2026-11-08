"""Glossary-term matching (shared by the ledger/key-term tools) and the two tools that rewrite or
check glossary.csv: terms that start or end with a non-word character ("C++", ".dockerignore",
"-p", "How are you?") must match, and apply_clean_ledger must never empty a glossary."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import apply_clean_ledger  # noqa: E402
import check_key_term_usage  # noqa: E402
import csv_io  # noqa: E402
import llm_fix_exercise_only_terms  # noqa: E402
import llm_fix_forward_refs  # noqa: E402
import propose_term_ledger  # noqa: E402
import term_match  # noqa: E402


def test_terms_with_non_word_edges_match():
    cases = [
        ("C++", "I use C++ daily"),
        (".dockerignore", "Add a .dockerignore file"),
        ("-p", "docker run -p 8080:80 nginx"),
        ("start()", "Call start() on the thread"),
        ("How are you?", "Say How are you? to a friend"),
    ]
    for term, text in cases:
        assert term_match.build_word_pattern(term).search(text), term


def test_whole_word_matching_is_kept():
    assert not term_match.build_word_pattern("cat").search("concatenate")
    assert not term_match.build_word_pattern("C++").search("C++x")
    assert term_match.build_word_pattern("cat").search("A Cat sat")


def test_combined_matcher_prefers_the_longest_term():
    rx = term_match.build_matcher(["Governor", "Governor General"])
    assert rx.search("the Governor General signs").group(0) == "Governor General"
    assert term_match.build_matcher([]) is None


def test_every_tool_uses_the_shared_matcher():
    for module in (apply_clean_ledger, llm_fix_exercise_only_terms, llm_fix_forward_refs, propose_term_ledger):
        assert module.build_word_pattern("C++").search("I use C++ daily"), module.__name__
    assert llm_fix_forward_refs.build_matcher(["C++"]).search("I use C++ daily")
    assert check_key_term_usage.build_matcher(["C++"]).search("I use C++ daily")


def write_csv(path, fieldnames, rows, eol="\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator=eol)
        w.writeheader()
        w.writerows(rows)


def make_course(tmp_path, cards=True):
    course = tmp_path / "course"
    write_csv(course / "source" / "units.csv", ["id", "title"], [{"id": "u1", "title": "One"}, {"id": "u2", "title": "Two"}])
    if cards:
        write_csv(
            course / "source" / "cards.csv",
            ["id", "unit_id", "role", "type", "prompt", "options", "explanation"],
            [
                {"id": "1", "unit_id": "u1", "role": "exercise", "type": "type_answer", "prompt": "Is C++ fast?", "options": "", "explanation": ""},
                {"id": "2", "unit_id": "u2", "role": "main", "type": "type_answer", "prompt": "C++ is a language", "options": "", "explanation": ""},
            ],
        )
    write_csv(
        course / "source" / "glossary.csv",
        ["term", "definition", "introduced_by_card_id"],
        [{"term": "C++", "definition": "a language", "introduced_by_card_id": ""},
         {"term": "Rust", "definition": "another language", "introduced_by_card_id": ""}],
    )
    return course


def test_apply_clean_ledger_leaves_the_glossary_alone_without_cards(tmp_path):
    course = make_course(tmp_path, cards=False)
    glossary = course / "source" / "glossary.csv"
    before = glossary.read_bytes()
    assert apply_clean_ledger.apply_course(str(course)) is False
    assert glossary.read_bytes() == before


def test_apply_clean_ledger_maps_non_word_terms_and_keeps_line_endings(tmp_path):
    course = make_course(tmp_path)
    assert apply_clean_ledger.apply_course(str(course)) is True
    raw = (course / "source" / "glossary.csv").read_bytes()
    assert b"\r\n" not in raw  # the file was LF and stays LF
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    assert [(r["term"], r["introduced_by_card_id"]) for r in rows] == [("C++", "2")]  # Rust is dead
    assert not list((course / "source").glob("*.tmp"))


def test_detect_eol(tmp_path):
    crlf = tmp_path / "a.csv"
    crlf.write_bytes(b"a,b\r\n1,2\r\n")
    lf = tmp_path / "b.csv"
    lf.write_bytes(b'a,b\n"x\r\ny",2\n')
    assert csv_io.detect_eol(str(crlf)) == "\r\n"
    assert csv_io.detect_eol(str(lf)) == "\n"
    assert csv_io.detect_eol(str(tmp_path / "missing.csv")) == "\n"


def test_key_term_usage_flags_a_non_word_term_used_before_its_card(tmp_path):
    course = make_course(tmp_path)
    write_csv(
        course / "source" / "glossary.csv",
        ["term", "definition", "introduced_by_card_id"],
        [{"term": "C++", "definition": "a language", "introduced_by_card_id": "2"}],
    )
    findings = check_key_term_usage.check_course(str(course))
    assert len(findings) == 1 and "card 1" in findings[0]
