"""The catalog site build end to end: course discovery and data, the index and course pages, and
the defenses against content from external course repos (script injection, file copying outside
the course, one broken course taking the whole site down)."""
import json
import os
import sys
from pathlib import Path

import pytest

import build_site

FIXTURE = Path(__file__).resolve().parent / "testdata" / "site_courses"


def write_course(root, slug, meta, cards=None, units=None):
    course = root / slug
    (course / "source").mkdir(parents=True)
    (course / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if cards is not None:
        (course / "source" / "cards.csv").write_text(cards, encoding="utf-8")
    if units is not None:
        (course / "source" / "units.csv").write_text(units, encoding="utf-8")
    return course


CARDS = (
    "id,unit_id,role,type,prompt,options,image\n"
    "1,u1,preview,multiple_choice,Intro,,\n"
    "2,u1,main,multiple_choice,What is 2+2?,4|5,\n"
    "3,u1,exercise,true_false,2+2 is 4,True|False,\n"
)
UNITS = "id,title,description\nu1,Basics,The basics\n"


def build(tmp_path, courses_dir, *extra):
    out = tmp_path / "out"
    argv = ["build_site.py", "--out", str(out), "--courses-dir", str(courses_dir), *extra]
    old = sys.argv
    sys.argv = argv
    try:
        build_site.main()
    finally:
        sys.argv = old
    return out


def test_fixture_course_builds_index_and_course_page(tmp_path):
    out = build(tmp_path, FIXTURE)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "Sample course" in index
    page = (out / "courses" / "sample-course" / "index.html").read_text(encoding="utf-8")
    assert "What is 2+2?" in page and "Basics" in page
    assert (out / "images" / "sample-course" / "cover.png").is_file()


def test_course_data_counts_and_examples(tmp_path):
    course = write_course(tmp_path, "c", {"title": "T", "toc": ["a"]}, CARDS, UNITS)
    data = build_site.build_course_data(course)
    assert (data["card_count"], data["main_count"], data["practice_count"]) == (2, 1, 1)
    assert data["example_cards"][0]["options"] == ["4", "5"]
    assert [c.name for c in build_site.discover_courses(tmp_path)] == ["c"]


# Regression (N210): "1 decks" / "1 cards".
def test_counts_are_pluralised(tmp_path):
    one_card = "id,unit_id,role,type,prompt,options,image\n1,u1,main,multiple_choice,What is 2+2?,4|5,\n"
    write_course(tmp_path / "courses", "c", {"title": "T"}, one_card, UNITS)
    out = build(tmp_path, tmp_path / "courses")
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "1 deck<" in index and ">1 card<" in index
    assert "1 decks" not in index and "1 cards" not in index
    page = (out / "courses" / "c" / "index.html").read_text(encoding="utf-8")
    assert "<strong>1</strong><span>deck</span>" in page and "<strong>1</strong><span>main card</span>" in page


# Regression (H12): a course title/description is emitted inside <script>; json.dumps leaves
# "</script>" and "<!--" as they are, so an external repo could inject markup.
def test_course_data_cannot_break_out_of_the_script_tag(tmp_path):
    evil = '</script><script>alert(1)</script><!--'
    write_course(tmp_path / "courses", "c", {"title": evil, "description": evil}, CARDS, UNITS)
    out = build(tmp_path, tmp_path / "courses")
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "<script>alert(1)" not in index and "<!--" not in index
    blob = index.split("window.__COURSES__ = ", 1)[1].split(";</script>", 1)[0]
    assert json.loads(blob)[0]["title"] == evil


# Regression (N183): the cover path from meta.json was copied unchecked, so "../" or a symlink
# published any file the build could read.
def test_cover_outside_the_course_or_not_an_image_is_not_copied(tmp_path):
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"x")
    out = tmp_path / "out"
    for image in ("../secret.png", "meta.json"):
        course = tmp_path / ("c" + str(len(image)))
        course.mkdir()
        (course / "meta.json").write_text("{}", encoding="utf-8")
        build_site.copy_images(course, {"slug": course.name, "image": image}, out)
        assert not any((out / "images" / course.name).iterdir()), image


def test_symlinked_cover_is_not_copied(tmp_path):
    course = tmp_path / "c"
    course.mkdir()
    (tmp_path / "secret.png").write_bytes(b"x")
    try:
        os.symlink(tmp_path / "secret.png", course / "cover.png")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    out = tmp_path / "out"
    build_site.copy_images(course, {"slug": "c", "image": "cover.png"}, out)
    assert not (out / "images" / "c" / "cover.png").exists()


# Regression (H9): one broken course repo aborted the whole build, and a build that found no
# course at all still "succeeded" and deployed an empty site.
def test_a_broken_course_is_skipped_and_the_rest_build(tmp_path, capsys):
    courses = tmp_path / "courses"
    write_course(courses, "good", {"title": "Good"}, CARDS, UNITS)
    bad = write_course(courses, "bad", {"title": "Bad"}, "id,type\n1,x\n", UNITS)  # no role column
    (bad / "meta.json").write_text("{not json", encoding="utf-8")
    out = build(tmp_path, courses)
    assert (out / "courses" / "good" / "index.html").is_file()
    assert not (out / "courses" / "bad").exists()
    assert "bad" in capsys.readouterr().err


def test_no_courses_fails_the_build(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit) as exit_:
        build(tmp_path, tmp_path / "empty")
    assert exit_.value.code not in (0, None)


# N187: Farsi titles, descriptions and cards get a direction (and their language).
def test_course_text_has_dir_auto_and_rtl_lang(tmp_path):
    write_course(tmp_path / "courses", "fa", {"title": "تشخیص", "description": "توضیح", "language": "fa"}, CARDS, UNITS)
    write_course(tmp_path / "courses", "en", {"title": "English for X", "language": "fa"}, CARDS, UNITS)
    out = build(tmp_path, tmp_path / "courses")
    index = (out / "index.html").read_text(encoding="utf-8")
    assert '<h3 dir="auto" lang="fa">تشخیص</h3>' in index
    assert '<h3 dir="auto">English for X</h3>' in index  # meta language is the learner's, not the title's
    page = (out / "courses" / "fa" / "index.html").read_text(encoding="utf-8")
    assert '<h1 dir="auto" lang="fa">تشخیص</h1>' in page
    assert '<p class="card-prompt" dir="auto">What is 2+2?</p>' in page


# N188: filter state, results and the type bar are exposed to assistive technology.
def test_index_and_course_page_accessibility_hooks(tmp_path):
    out = build(tmp_path, FIXTURE)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert 'class="skip-link" href="#main"' in index and 'id="main"' in index
    assert 'data-tag="" aria-pressed="true"' in index
    assert 'aria-pressed="false"' in index
    assert 'role="status"' in index
    assert "<h2" in index.split('id="course-grid"', 1)[0]
    page = (out / "courses" / "sample-course" / "index.html").read_text(encoding="utf-8")
    assert '<div class="type-bar" aria-hidden="true">' in page
    js = (out / "assets" / "site.js").read_text(encoding="utf-8")
    assert "aria-pressed" in js and "results-status" in js


# N184: the Contribute and Help pages describe the one-repo-per-course workflow.
def test_contribute_and_help_describe_the_course_template_workflow(tmp_path):
    build_site.render_contribute_page(tmp_path)
    build_site.render_help_page(tmp_path)
    contribute = (tmp_path / "contribute" / "index.html").read_text(encoding="utf-8")
    help_page = (tmp_path / "help" / "index.html").read_text(encoding="utf-8")
    assert "course-template" in contribute and "yaaddi-course" in contribute
    assert "validate_course.py . --source" in contribute
    assert "&lt;name&gt;/source/" not in contribute and "validate-courses" not in contribute
    assert "same open-source repo" not in help_page and "straight from this repo" not in help_page
