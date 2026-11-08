"""The local-LLM tools (llm_common + llm_review_pass, llm_fix_*, propose_term_ledger): model
output parsing, the rewrite safety checks, validator handling, state files and the per-script
fix logic. The LLM itself is never called: each script's call_llm is replaced by a fake."""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import csv_io  # noqa: E402
import llm_common  # noqa: E402
import llm_fix_exercise_only_terms  # noqa: E402
import llm_fix_forward_refs  # noqa: E402
import llm_fix_pass  # noqa: E402
import llm_fix_phrasing  # noqa: E402
import llm_fix_repetitive_practice  # noqa: E402
import llm_fix_self_standing_confirmed  # noqa: E402
import llm_review_pass  # noqa: E402
import propose_term_ledger  # noqa: E402

CARD_FIELDS = ["id", "unit_id", "role", "type", "related_main_id", "prompt", "options", "correct_index", "explanation"]


def card(id, unit="u1", role="exercise", type="multiple_choice", main="", prompt="", options="", correct="", explanation=""):
    return {"id": id, "unit_id": unit, "role": role, "type": type, "related_main_id": main,
            "prompt": prompt, "options": options, "correct_index": correct, "explanation": explanation}


def write_csv(path, fieldnames, rows, eol="\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator=eol)
        w.writeheader()
        w.writerows(rows)


def read_cards(course):
    return {r["id"]: r for r in csv.DictReader((course / "source" / "cards.csv").open(encoding="utf-8-sig"))}


def make_course(tmp_path, cards, glossary=None, report=None, units=("u1", "u2")):
    course = tmp_path / "course"
    write_csv(course / "source" / "units.csv", ["id", "title"], [{"id": u, "title": u} for u in units])
    write_csv(course / "source" / "cards.csv", CARD_FIELDS, cards)
    if glossary is not None:
        write_csv(course / "source" / "glossary.csv", ["term", "definition", "introduced_by_card_id"], glossary)
    if report is not None:
        (course / ".internal").mkdir(parents=True, exist_ok=True)
        (course / ".internal" / "llm_review_report.json").write_text(json.dumps(report), encoding="utf-8")
    (course / "meta.json").write_text("{}", encoding="utf-8")
    return course


def fake_llm(*answers):
    """call_llm stand-in returning the given answers in turn (an Exception instance is raised)."""
    queue = list(answers)

    def call(model, block):
        answer = queue.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer if isinstance(answer, str) else json.dumps(answer)
    return call


# ---------------------------------------------------------------- llm_common

def test_extract_json_array_handles_fences_bare_objects_and_junk():
    assert llm_common.extract_json_array('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert llm_common.extract_json_array('{"a": 1}') == [{"a": 1}]
    assert llm_common.extract_json_array('Sure! [{"a": 1}] done') == [{"a": 1}]
    assert llm_common.extract_json_array("no json here") is None
    assert llm_common.extract_json_array(None) is None


def test_coerce_str_joins_lists_and_keeps_none():
    assert llm_common.coerce_str(["a", "b"], "|") == "a|b"
    assert llm_common.coerce_str(" x ") == "x"
    assert llm_common.coerce_str(None) is None


def test_csv_round_trip_keeps_bom_and_line_endings(tmp_path):
    path = tmp_path / "cards.csv"
    path.write_bytes(csv_io.BOM + b"id,prompt\r\n1,hi\r\n")
    fields, rows = llm_common.read_csv(str(path))
    assert fields == ["id", "prompt"] and rows[0]["id"] == "1"
    rows[0]["prompt"] = "hello"
    llm_common.write_dict_csv(str(path), fields, rows)
    assert path.read_bytes() == csv_io.BOM + b"id,prompt\r\n1,hello\r\n"
    assert not list(tmp_path.glob("*.tmp"))


def test_find_all_course_dirs_defaults_to_the_repo_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # running from anywhere (e.g. tools/) must still find the courses
    assert llm_common.find_all_course_dirs() == llm_common.find_all_course_dirs(llm_common.REPO_ROOT)


@pytest.mark.parametrize("change, ok", [
    ({"new_options": "Paris|Rome|Madrid"}, True),               # distractor reworded
    ({"new_options": "Lyon|Rome|Berlin"}, False),               # correct option reworded
    ({"new_options": "Rome|Paris|Berlin"}, False),              # correct option moved
    ({"new_options": "Paris|Rome"}, False),                     # option dropped
    ({"new_prompt": "Which city is the capital of France?"}, True),
    ({"new_prompt": "one two three four five six seven eight nine ten eleven"}, False),
])
def test_rewrite_problem_on_a_multiple_choice_card(change, ok):
    c = card("1", prompt="Capital of France?", options="Paris|Rome|Berlin", correct="0")
    assert (llm_common.rewrite_problem(c, **change) is None) == ok


def test_rewrite_problem_locks_format_bearing_options_and_passages():
    typed = card("1", type="type_answer", prompt="Type the word", options="alive")
    assert llm_common.rewrite_problem(typed, new_prompt="Type that word") is None
    assert llm_common.rewrite_problem(typed, new_options="living") is not None
    listen = card("2", type="listening_card", options="select|a|b", correct="0")
    assert llm_common.rewrite_problem(listen, new_options="type|a") is not None
    pairs = card("3", type="match_pairs", options="a↔b|c↔d")
    assert llm_common.rewrite_problem(pairs, new_options="a↔d|c↔b") is not None
    cloze = card("4", type="cloze_passage", prompt="I ___ water", options="choice|want~need", correct="0")
    assert llm_common.rewrite_problem(cloze, new_prompt="I ___ some water") is not None
    blank = card("5", type="select_blank", prompt="I ___ you", options="see|saw", correct="0")
    assert llm_common.rewrite_problem(blank, new_prompt="I see you") is not None
    multi = card("6", type="multi_select", options="a|b|c", correct="0|2")
    assert llm_common.rewrite_problem(multi, new_options="a|x|c") is None
    assert llm_common.rewrite_problem(multi, new_options="a|b|z") is not None


def write_script(path, body):
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_run_validate_uses_the_trusted_validator_isolated(tmp_path):
    course = make_course(tmp_path, [card("1")])
    marker = tmp_path / "course-script-ran"
    write_script(course / "validate_course.py", f"open({str(marker)!r}, 'w').close()\n")
    trusted = write_script(tmp_path / "trusted.py", "import sys\nprint('  [ERROR] card 7: too long', sys.argv[1])\nsys.exit(1)\n")
    assert llm_common.run_validate(str(course), trusted) == {"7"}
    assert not marker.exists()  # the course's own validate_course.py never runs


def test_run_validate_fails_closed(tmp_path):
    course = make_course(tmp_path, [card("1")])
    assert llm_common.run_validate(str(course), str(tmp_path / "missing.py")) is None
    crash = write_script(tmp_path / "crash.py", "raise RuntimeError('boom')\n")
    assert llm_common.run_validate(str(course), crash) is None
    silent_fail = write_script(tmp_path / "fail.py", "import sys\nsys.exit(1)\n")
    assert llm_common.run_validate(str(course), silent_fail) is None
    clean = write_script(tmp_path / "ok.py", "print('OK')\n")
    assert llm_common.run_validate(str(course), clean) == set()


def test_json_state_is_atomic_and_a_corrupt_file_is_set_aside(tmp_path):
    path = str(tmp_path / ".internal" / "state.json")
    llm_common.save_json(path, {"1": True})
    assert llm_common.load_json(path, {}) == {"1": True}
    Path(path).write_text('{"1": tr', encoding="utf-8")  # truncated by a kill
    assert llm_common.load_json(path, {}) == {}
    assert Path(path + ".corrupt").exists()


def test_llm_failures_trip_after_the_limit():
    f = llm_common.LlmFailures(limit=2)
    assert not f.failed()
    f.ok()
    assert not f.failed()
    assert f.failed() and f.tripped


# ---------------------------------------------------------------- llm_review_pass

def test_review_pass_rereviews_edited_cards_and_ignores_flagless_answers(tmp_path, monkeypatch):
    cards = [card("1", prompt="Old prompt"), card("2", prompt="Same")]
    report = {"1": {"prompt": "Old prompt before edit", "robotic_phrasing": True},  # legacy entry, card edited since
              "2": {"prompt": "Same", "robotic_phrasing": False}}
    course = make_course(tmp_path, cards, report=report)
    seen = []

    def call(model, block):
        seen.append(block)
        return json.dumps([{"card_id": "1", "reasoning": "no flags at all"}])
    monkeypatch.setattr(llm_review_pass, "call_llm", call)
    llm_review_pass.review_course(str(course), "m", 6, True)
    assert len(seen) == 1 and "Old prompt" in seen[0] and "Same" not in seen[0]
    stored = json.loads((course / ".internal" / "llm_review_report.json").read_text(encoding="utf-8"))
    assert "1" not in stored  # an answer without any flag field is not "reviewed, clean"
    assert stored["2"]["robotic_phrasing"] is False


def test_review_pass_stores_hashes_and_survives_a_corrupt_report(tmp_path, monkeypatch):
    course = make_course(tmp_path, [card("1", prompt="Q")], report={})
    (course / ".internal" / "llm_review_report.json").write_text("{", encoding="utf-8")
    monkeypatch.setattr(llm_review_pass, "call_llm", fake_llm([{"card_id": "1", "robotic_phrasing": False}]))
    llm_review_pass.review_course(str(course), "m", 6, True)
    stored = json.loads((course / ".internal" / "llm_review_report.json").read_text(encoding="utf-8"))
    assert stored["1"]["question_hash"] == llm_common.question_hash(card("1", prompt="Q"))


# ---------------------------------------------------------------- llm_fix_pass

def test_fix_pass_accepts_a_list_valued_explanation(tmp_path, monkeypatch):
    course = make_course(tmp_path, [card("1", prompt="Q", options="a|b", correct="0")],
                         report={"1": {"prompt": "Q", "missing_or_generic_explanation": True}})
    monkeypatch.setattr(llm_fix_pass, "call_llm", fake_llm([{"card_id": "1", "explanation": ["Because", "a."]}]))
    llm_fix_pass.fix_course(str(course), "m", 5)
    assert read_cards(course)["1"]["explanation"] == "Because a."


# ---------------------------------------------------------------- llm_fix_phrasing

def test_phrasing_keeps_the_answer_and_retries_rejected_rewrites(tmp_path, monkeypatch):
    cards = [card("1", prompt="Pick the capital", options="Paris|Rome", correct="0"),
             card("2", prompt="Pick the river", options="Nile|Alps", correct="0")]
    report = {cid: {"prompt": c["prompt"], "robotic_phrasing": True} for cid, c in (("1", cards[0]), ("2", cards[1]))}
    course = make_course(tmp_path, cards, report=report)
    monkeypatch.setattr(llm_fix_phrasing, "call_llm", fake_llm([
        {"card_id": "1", "prompt": "Which is the capital?", "options": ["Paris", "Milan"]},  # list value, distractor only
        {"card_id": "2", "prompt": "Which is a river?", "options": "Alps|Nile"},  # swaps the correct answer
    ]))  # one batch of both cards
    llm_fix_phrasing.fix_course(str(course), "m", 4)
    after = read_cards(course)
    assert after["1"]["options"] == "Paris|Milan" and after["1"]["prompt"] == "Which is the capital?"
    assert after["2"]["options"] == "Nile|Alps"
    state = json.loads((course / ".internal" / "llm_fix_phrasing_state.json").read_text(encoding="utf-8"))
    assert "1" in state and "2" not in state  # the rejected card is retried next run


def test_phrasing_never_rewrites_a_type_answer_answer(tmp_path, monkeypatch):
    cards = [card("1", type="type_answer", prompt="Type the word", options="alive")]
    course = make_course(tmp_path, cards, report={"1": {"prompt": "Type the word", "robotic_phrasing": True}})
    monkeypatch.setattr(llm_fix_phrasing, "call_llm", fake_llm([{"card_id": "1", "prompt": "Type it", "options": "living"}]))
    llm_fix_phrasing.fix_course(str(course), "m", 4)
    assert read_cards(course)["1"]["options"] == "alive"


# ---------------------------------------------------------------- llm_fix_repetitive_practice

def test_repetitive_writes_cards_before_marking_a_batch_done(tmp_path, monkeypatch):
    cards = [card("1", role="main", prompt="Rule"), card("2", main="1", prompt="Restates rule", options="a|b", correct="0"),
             card("3", main="1", prompt="Restates again", options="c|d", correct="0")]
    report = {"2": {"prompt": "Restates rule", "repetitive_practice": True},
              "3": {"prompt": "Restates again", "repetitive_practice": True}}
    course = make_course(tmp_path, cards, report=report)
    monkeypatch.setattr(llm_fix_repetitive_practice, "call_llm", fake_llm(
        [{"card_id": "2", "action": "REWRITE", "prompt": "Fresh example"}], KeyboardInterrupt()))
    monkeypatch.setattr(llm_fix_repetitive_practice, "run_validate", lambda d: set())
    monkeypatch.setattr(llm_fix_repetitive_practice, "run_forward_ref_check", lambda d: set())
    with pytest.raises(KeyboardInterrupt):
        llm_fix_repetitive_practice.fix_course(str(course), "m", 1)
    assert read_cards(course)["2"]["prompt"] == "Fresh example"  # batch 1 is on disk
    state = json.loads((course / ".internal" / "llm_fix_repetitive_state.json").read_text(encoding="utf-8"))
    assert state == {"2": True}


def test_repetitive_reverts_everything_when_the_validator_cannot_run(tmp_path, monkeypatch):
    cards = [card("1", role="main", prompt="Rule"), card("2", main="1", prompt="Restates rule", options="a|b", correct="0")]
    course = make_course(tmp_path, cards, report={"2": {"prompt": "Restates rule", "repetitive_practice": True}})
    monkeypatch.setattr(llm_fix_repetitive_practice, "call_llm", fake_llm([{"card_id": "2", "action": "REWRITE", "prompt": "Fresh"}]))
    monkeypatch.setattr(llm_fix_repetitive_practice, "run_validate", lambda d: None)
    monkeypatch.setattr(llm_fix_repetitive_practice, "run_forward_ref_check", lambda d: set())
    llm_fix_repetitive_practice.fix_course(str(course), "m", 3)
    assert read_cards(course)["2"]["prompt"] == "Restates rule"


# ---------------------------------------------------------------- llm_fix_self_standing_confirmed

def test_self_standing_shows_the_preview_of_the_cards_own_pack():
    cards = [card("10", role="preview", type="true_false", main="11", prompt="Other pack preview"),
             card("11", role="main", prompt="Other main"),
             card("20", role="preview", type="true_false", main="21", prompt="Own pack preview"),
             card("21", role="main", prompt="Own main"),
             card("22", main="21", prompt="This one?")]
    preview = llm_fix_self_standing_confirmed.pack_preview(cards, cards[3])
    assert preview["id"] == "20"


def test_self_standing_list_skips_bad_lines(tmp_path, capsys):
    path = tmp_path / "list.txt"
    path.write_text("# comment\ncourse-a|12\nnot a pair\ncourse-a|13|x\n\ncourse-b| 7 \n", encoding="utf-8")
    assert llm_fix_self_standing_confirmed.read_card_list(str(path)) == {"course-a": ["12"], "course-b": ["7"]}
    assert "skipping line 3" in capsys.readouterr().out


def test_self_standing_reverts_when_validation_cannot_run(tmp_path, monkeypatch):
    course = make_course(tmp_path, [card("1", role="main", prompt="Rule"), card("2", main="1", prompt="Is this right?", options="a|b", correct="0")])
    monkeypatch.setattr(llm_fix_self_standing_confirmed, "call_llm", fake_llm([{"card_id": "2", "action": "REWRITE", "prompt": "Is the rule right?"}]))
    monkeypatch.setattr(llm_fix_self_standing_confirmed, "run_validate", lambda d: None)
    llm_fix_self_standing_confirmed.fix_course(str(course), ["2"], "m", 3)
    assert read_cards(course)["2"]["prompt"] == "Is this right?"


# ---------------------------------------------------------------- llm_fix_forward_refs

def forward_ref_course(tmp_path):
    cards = [card("1", unit="u1", role="exercise", main="5", prompt="Use a mutex", options="Yes|No", correct="0"),
             card("2", unit="u1", role="main", prompt="A mutex locks", options="Yes|No", correct="0"),
             card("3", unit="u1", role="exercise", main="2", prompt="A thread runs", options="Yes|No", correct="0"),
             card("5", unit="u2", role="main", prompt="Mutex and thread defined", options="Yes|No", correct="0")]
    glossary = [{"term": "mutex", "definition": "a lock", "introduced_by_card_id": "5"},
                {"term": "thread", "definition": "a worker", "introduced_by_card_id": "5"}]
    return make_course(tmp_path, cards, glossary=glossary)


def read_glossary(course):
    return {r["term"]: r["introduced_by_card_id"] for r in csv.DictReader((course / "source" / "glossary.csv").open(encoding="utf-8"))}


def test_forward_refs_remap_only_a_flagged_term_onto_a_teaching_card(tmp_path, monkeypatch):
    course = forward_ref_course(tmp_path)
    monkeypatch.setattr(llm_fix_forward_refs, "run_validate", lambda d: set())
    monkeypatch.setattr(llm_fix_forward_refs, "call_llm", fake_llm(  # one answer per one-card batch
        {"card_id": "1", "decision": "REMAP", "remap_term": "mutex"},   # card 1 is an exercise: refused
        {"card_id": "2", "decision": "REMAP", "remap_term": "thread"},  # thread is not flagged on card 2: refused
        {"card_id": "3", "decision": "REMAP", "remap_term": "thread"},  # exercise again: refused
    ))
    llm_fix_forward_refs.fix_course(str(course), "m", 1)
    assert read_glossary(course) == {"mutex": "5", "thread": "5"}


def test_forward_refs_valid_remap_and_rewords_are_kept(tmp_path, monkeypatch):
    course = forward_ref_course(tmp_path)
    monkeypatch.setattr(llm_fix_forward_refs, "run_validate", lambda d: set())
    monkeypatch.setattr(llm_fix_forward_refs, "call_llm", fake_llm(
        {"card_id": "1", "decision": "REWORD", "prompt": "Use a lock"},
        {"card_id": "2", "decision": "REMAP", "remap_term": "mutex"},
        {"card_id": "3", "decision": "REWORD", "prompt": "A worker runs"},
    ))
    llm_fix_forward_refs.fix_course(str(course), "m", 1)
    assert read_glossary(course)["mutex"] == "2"
    cards = read_cards(course)
    assert cards["1"]["prompt"] == "Use a lock" and cards["3"]["prompt"] == "A worker runs"


def test_forward_refs_reword_that_brings_in_another_early_term_is_reverted(tmp_path, monkeypatch):
    course = forward_ref_course(tmp_path)
    monkeypatch.setattr(llm_fix_forward_refs, "run_validate", lambda d: set())
    monkeypatch.setattr(llm_fix_forward_refs, "call_llm", fake_llm(
        [{"card_id": "1", "decision": "SKIP"}], [{"card_id": "2", "decision": "SKIP"}],
        [{"card_id": "3", "decision": "REWORD", "prompt": "A mutex runs"}]))  # swaps one early term for another
    llm_fix_forward_refs.fix_course(str(course), "m", 1)
    assert read_cards(course)["3"]["prompt"] == "A thread runs"


def test_forward_refs_survives_list_values_and_keeps_finished_batches(tmp_path, monkeypatch):
    course = forward_ref_course(tmp_path)
    monkeypatch.setattr(llm_fix_forward_refs, "run_validate", lambda d: set())
    monkeypatch.setattr(llm_fix_forward_refs, "call_llm", fake_llm(
        [{"card_id": "1", "decision": "REWORD", "prompt": ["Use", "a", "lock"], "options": ["Yes", "No"]}],
        KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        llm_fix_forward_refs.fix_course(str(course), "m", 1)
    assert read_cards(course)["1"]["prompt"] == "Use a lock"  # written after its batch, not lost


def test_forward_refs_reverts_when_validation_cannot_run(tmp_path, monkeypatch):
    course = forward_ref_course(tmp_path)
    monkeypatch.setattr(llm_fix_forward_refs, "run_validate", lambda d: None)
    monkeypatch.setattr(llm_fix_forward_refs, "call_llm", fake_llm(
        {"card_id": "1", "decision": "REWORD", "prompt": "Use a lock"},
        {"card_id": "2", "decision": "REMAP", "remap_term": "mutex"},
        {"card_id": "3", "decision": "SKIP"}))
    llm_fix_forward_refs.fix_course(str(course), "m", 1)
    assert read_cards(course)["1"]["prompt"] == "Use a mutex"
    assert read_glossary(course)["mutex"] == "5"


def test_forward_refs_stops_after_consecutive_llm_failures(tmp_path, monkeypatch):
    course = forward_ref_course(tmp_path)
    calls = []

    def down(model, block):
        calls.append(block)
        raise RuntimeError("connection refused")
    monkeypatch.setattr(llm_fix_forward_refs, "call_llm", down)
    failures = llm_common.LlmFailures(limit=2)
    llm_fix_forward_refs.fix_course(str(course), "m", 1, failures)
    assert len(calls) == 2 and failures.tripped


# ---------------------------------------------------------------- BOM-safe readers

def test_ledger_tools_read_bom_csvs(tmp_path, capsys):
    course = make_course(tmp_path, [card("1", role="main", prompt="C++ is fast")],
                         glossary=[{"term": "C++", "definition": "x", "introduced_by_card_id": ""}])
    for name in ("cards.csv", "glossary.csv", "units.csv"):
        p = course / "source" / name
        p.write_bytes(csv_io.BOM + p.read_bytes())
    sys.argv = ["propose_term_ledger.py", str(course)]
    propose_term_ledger.main()
    assert '"C++" -> card 1' in capsys.readouterr().out
    results, _glossary, _cards = llm_fix_exercise_only_terms.find_exercise_only_terms(str(course))
    assert results == []
