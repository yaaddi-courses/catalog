"""check_self_standing.py: the question text sent to the model, the resumable state file, strict
parsing of the model's verdict, and --all finding courses whatever the current directory is."""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_self_standing as css  # noqa: E402
import filter_self_standing_report as fssr  # noqa: E402

TOOLS = Path(__file__).resolve().parent


def make_course(root, cards):
    course = root / "course"
    (course / "source").mkdir(parents=True)
    (course / "meta.json").write_text("{}", encoding="utf-8")
    with (course / "source" / "cards.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "type", "prompt", "options", "image"], lineterminator="\n")
        w.writeheader()
        w.writerows(cards)
    return course


def test_question_text_has_no_literal_strip_call():
    q = css.format_question({"id": "1", "prompt": "What is Python?", "options": ""})
    assert ".strip()" not in q
    assert q.endswith('question : "What is Python?"')


def test_verdict_parsing_is_strict():
    assert css.parse_verdict(True) is True
    assert css.parse_verdict(False) is False
    assert css.parse_verdict("false") is False
    assert css.parse_verdict("TRUE") is True
    assert css.parse_verdict("maybe") is None
    assert css.parse_verdict(None) is None


def test_state_dir_is_created_and_string_false_is_flagged(tmp_path, monkeypatch):
    course = make_course(tmp_path, [
        {"id": "1", "type": "multiple_choice", "prompt": "What is this idea called?", "options": "a|b", "image": ""},
        {"id": "2", "type": "multiple_choice", "prompt": "Which one is it?", "options": "a|b", "image": ""},
    ])
    monkeypatch.setattr(css, "call_llm", lambda model, block: json.dumps([{"id": "2", "self_standing": "false"}]))
    report = tmp_path / "report.txt"
    css.check_course(str(course), "m", 6, str(report))
    state = json.loads((course / ".internal" / "self_standing_state.json").read_text(encoding="utf-8"))
    assert state == {"1": False, "2": False}
    assert report.read_text(encoding="utf-8").count("card ") == 2


def test_all_uses_the_repo_root_not_the_current_directory(tmp_path):
    assert Path(css.REPO_ROOT) == TOOLS.parent
    # From another directory, --all still means this repo's courses (run with a missing model
    # server it fails per batch, so only check what it found, then stop).
    run = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'%s'); import check_self_standing as c; "
         "print(len(c.find_all_course_dirs(c.REPO_ROOT)))" % TOOLS],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert run.stdout.strip() == str(len(css.find_all_course_dirs(str(TOOLS.parent))))


def test_all_fails_when_no_course_is_found(tmp_path, monkeypatch):
    monkeypatch.setattr(css, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["check_self_standing.py", "--all"])
    try:
        css.main()
    except SystemExit as exit_:
        assert exit_.code not in (0, None)
    else:
        raise AssertionError("expected a non-zero exit")


def test_filter_drops_only_image_references_with_a_real_image(tmp_path, monkeypatch):
    make_course(tmp_path, [
        {"id": "1", "type": "multiple_choice", "prompt": "What does this photo show?", "options": "", "image": "a.png"},
        {"id": "2", "type": "multiple_choice", "prompt": "What does this photo show?", "options": "", "image": ""},
    ])
    report = tmp_path / "self_standing_report.txt"
    report.write_text(
        'course | card 1 | "What does this photo show?"\ncourse | card 2 | "What does this photo show?"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["x", str(report)])
    fssr.main()
    cleaned = (tmp_path / "self_standing_report_cleaned.txt").read_text(encoding="utf-8")
    assert "card 2" in cleaned and "card 1" not in cleaned
    assert os.path.isfile(report)
