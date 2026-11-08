"""add_article_support.py patches a course's build_course_zip.py and validate_course.py as a pair:
both or neither, idempotent on its own marker, never fooled by an unrelated "articles_dir"."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import add_article_support as aas  # noqa: E402

BUILD = (
    "def build(source_dir):\n"
    + aas.BUILD_READ
    + "    with zipfile.ZipFile(out, 'w') as zf:\n"
    + aas.BUILD_WRITE
    + aas.BUILD_NOTE
)
VALIDATE = (
    "\ndef validate_glossary_rows(rows, report, card_ids=None):\n"
    "    for i, row in enumerate(rows):\n"
    '        link = (row.get("link") or "").strip()\n        # Which card actually teaches it\n'
    "def check(source_dir):\n"
    "    validate_glossary_rows(rows, report, card_ids)\n"
    "def check_zip(zf):\n"
    "                validate_glossary_rows(read_csv_text(glossary_text), report, card_ids)\n"
)


def make_course(tmp_path, build=BUILD, validate=VALIDATE):
    course = tmp_path / "c"
    course.mkdir()
    (course / "build_course_zip.py").write_text(build, encoding="utf-8")
    (course / "validate_course.py").write_text(validate, encoding="utf-8")
    return course


def test_patches_both_files_once(tmp_path):
    course = make_course(tmp_path)
    assert aas.patch_course(str(course)) == (True, True)
    build = (course / "build_course_zip.py").read_text(encoding="utf-8")
    validate = (course / "validate_course.py").read_text(encoding="utf-8")
    assert 'zf.writestr("articles/" + name, text)' in build
    assert "def validate_article_ref(" in validate
    assert aas.patch_course(str(course)) == (False, False)  # idempotent


def test_unrelated_articles_dir_text_is_not_taken_as_patched(tmp_path):
    course = make_course(tmp_path, build="# articles_dir is mentioned here\n" + BUILD)
    assert aas.patch_course(str(course))[0] is True


def test_a_failed_second_patch_leaves_both_files_untouched(tmp_path):
    course = make_course(tmp_path, validate="nothing to patch here\n")
    with pytest.raises(SystemExit):
        aas.patch_course(str(course))
    assert (course / "build_course_zip.py").read_text(encoding="utf-8") == BUILD
    assert (course / "validate_course.py").read_text(encoding="utf-8") == "nothing to patch here\n"
