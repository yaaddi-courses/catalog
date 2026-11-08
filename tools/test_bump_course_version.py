import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("bump", Path(__file__).parent / "bump_course_version.py")
bump = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bump)

CARDS = "id,unit_id,text\n1,1,hello\n2,1,world\n"
UNITS = "id,title\n1,One\n"
GLOSSARY = "term,definition\nfoo,a foo\n"
META_CSV = "slug,title,version\nc,C,1.0.0\n"


def run(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def course(tmp_path):
    """A committed course folder inside a throwaway git repo."""
    (tmp_path / "source").mkdir()
    (tmp_path / "meta.json").write_text(json.dumps({"version": "1.0.0", "changelog": []}), encoding="utf-8")
    (tmp_path / "source" / "meta.csv").write_text(META_CSV, encoding="utf-8")
    (tmp_path / "source" / "cards.csv").write_text(CARDS, encoding="utf-8")
    (tmp_path / "source" / "units.csv").write_text(UNITS, encoding="utf-8")
    (tmp_path / "source" / "glossary.csv").write_text(GLOSSARY, encoding="utf-8")
    run(tmp_path, "init", "-q")
    run(tmp_path, "config", "user.email", "t@example.com")
    run(tmp_path, "config", "user.name", "t")
    run(tmp_path, "add", "-A")
    run(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def edit(course, name, text):
    (course / "source" / name).write_text(text, encoding="utf-8")


def version(course):
    return json.loads((course / "meta.json").read_text(encoding="utf-8"))["version"]


@pytest.mark.parametrize(
    "version_in, level, expected",
    [("1.2.3", "patch", "1.2.4"), ("1.2.3", "minor", "1.3.0"), ("1.2.3", "major", "2.0.0")],
)
def test_bump_levels(version_in, level, expected):
    assert bump.bump(version_in, level) == expected


def test_no_change_means_no_bump(course):
    assert bump.main([str(course), "--skip-build"]) == 0
    assert version(course) == "1.0.0"
    assert bump.main([str(course), "--check"]) == 0


def test_check_fails_when_content_changed_without_a_bump(course):
    edit(course, "cards.csv", CARDS.replace("hello", "hi"))
    assert bump.main([str(course), "--check"]) == 1
    assert version(course) == "1.0.0"


def test_wording_change_is_a_patch_in_both_version_files_with_a_changelog_entry(course):
    edit(course, "cards.csv", CARDS.replace("hello", "hi"))
    assert bump.main([str(course), "--skip-build", "--note", "Fixed a typo."]) == 0
    assert version(course) == "1.0.1"
    meta = json.loads((course / "meta.json").read_text(encoding="utf-8"))
    assert meta["changelog"][-1]["version"] == "1.0.1"
    assert meta["changelog"][-1]["notes"] == "Fixed a typo."
    assert "1.0.1" in (course / "source" / "meta.csv").read_text(encoding="utf-8")
    assert bump.main([str(course), "--check"]) == 0


def test_running_twice_does_not_bump_twice(course):
    edit(course, "cards.csv", CARDS.replace("hello", "hi"))
    bump.main([str(course), "--skip-build"])
    bump.main([str(course), "--skip-build"])
    assert version(course) == "1.0.1"


def test_a_failed_build_restores_the_old_version_so_a_rerun_bumps_again(course, monkeypatch):
    edit(course, "cards.csv", CARDS.replace("hello", "hi"))
    real_run = subprocess.run

    def failing_build(cmd, *args, **kwargs):
        if "build_course_zip.py" in cmd:
            return subprocess.CompletedProcess(cmd, 1)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(bump.subprocess, "run", failing_build)
    assert bump.main([str(course)]) == 1
    assert version(course) == "1.0.0"
    assert "1.0.0" in (course / "source" / "meta.csv").read_text(encoding="utf-8")
    monkeypatch.setattr(bump.subprocess, "run", real_run)
    assert bump.main([str(course), "--skip-build"]) == 0
    assert version(course) == "1.0.1"


def test_added_card_is_a_minor(course):
    edit(course, "cards.csv", CARDS + "3,1,new\n")
    bump.main([str(course), "--skip-build"])
    assert version(course) == "1.1.0"


def test_new_glossary_term_is_a_minor(course):
    edit(course, "glossary.csv", GLOSSARY + "bar,a bar\n")
    bump.main([str(course), "--skip-build"])
    assert version(course) == "1.1.0"


def test_removed_deck_is_a_major(course):
    edit(course, "units.csv", "id,title\n")
    bump.main([str(course), "--skip-build"])
    assert version(course) == "2.0.0"


def test_new_article_is_a_minor_and_untracked_files_count(course):
    (course / "source" / "articles").mkdir()
    (course / "source" / "articles" / "a.md").write_text("# A", encoding="utf-8")
    bump.main([str(course), "--skip-build"])
    assert version(course) == "1.1.0"


def test_removed_picture_is_a_patch_and_the_note_names_it(course):
    (course / "source" / "images").mkdir()
    (course / "source" / "images" / "a.png").write_bytes(b"x")
    run(course, "add", "-A")
    run(course, "commit", "-q", "-m", "image")
    (course / "source" / "images" / "a.png").unlink()
    bump.main([str(course), "--skip-build"])
    assert version(course) == "1.0.1"
    meta = json.loads((course / "meta.json").read_text(encoding="utf-8"))
    assert meta["changelog"][-1]["notes"] == "Updated pictures."


def test_level_can_be_overridden(course):
    edit(course, "cards.csv", CARDS.replace("hello", "hi"))
    bump.main([str(course), "--skip-build", "--level", "minor"])
    assert version(course) == "1.1.0"


def test_a_rebuilt_zip_alone_is_not_a_content_change(course):
    (course / "c.zip").write_bytes(b"zip")
    assert bump.main([str(course), "--check"]) == 0


def test_force_bumps_a_change_that_was_already_committed(course):
    edit(course, "cards.csv", CARDS.replace("hello", "hi"))
    run(course, "add", "-A")
    run(course, "commit", "-q", "-m", "committed without a bump")
    assert bump.main([str(course), "--check"]) == 0  # nothing uncommitted, so the check cannot see it
    assert bump.main([str(course), "--skip-build", "--force", "--note", "Late bump."]) == 0
    assert version(course) == "1.0.1"


@pytest.fixture
def pushed(course, tmp_path_factory):
    """The course repo with an upstream that already has its first commit."""
    remote = tmp_path_factory.mktemp("remote")
    run(remote, "init", "-q", "--bare")
    run(course, "remote", "add", "origin", str(remote))
    run(course, "push", "-q", "-u", "origin", "HEAD:main")
    run(course, "branch", "--set-upstream-to=origin/main")
    return course


def test_commits_made_before_the_push_are_bumped_once_at_push_time(pushed):
    for word in ("hi", "hey"):  # two commits, no bump in either
        edit(pushed, "cards.csv", CARDS.replace("hello", word))
        run(pushed, "add", "-A")
        run(pushed, "commit", "-q", "-m", f"wording {word}")
    assert bump.main([str(pushed), "--check"]) == 1  # committed but not bumped: the push must be blocked
    assert bump.main([str(pushed), "--skip-build", "--note", "Reworded a card."]) == 0
    assert version(pushed) == "1.0.1"  # one bump for the whole push, not one per commit
    assert bump.main([str(pushed), "--check"]) == 0
    bump.main([str(pushed), "--skip-build"])
    assert version(pushed) == "1.0.1"


def test_nothing_new_since_the_push_means_no_bump(pushed):
    assert bump.main([str(pushed), "--skip-build"]) == 0
    assert version(pushed) == "1.0.0"


def test_a_course_that_was_never_pushed_is_left_alone(tmp_path):
    (tmp_path / "meta.json").write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
    run(tmp_path, "init", "-q")
    assert bump.main([str(tmp_path), "--check"]) == 0
