"""make_covers.py: readable errors instead of tracebacks (N207). Needs Pillow (requirements-media.txt)."""
import hashlib
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")
sys.path.insert(0, str(Path(__file__).parent))

import make_covers  # noqa: E402


def test_database_cover_is_unchanged_by_dropping_the_duplicate_shapes():
    # sha1 of the drawing before the redundant rectangle/ellipse calls were removed
    assert hashlib.sha1(make_covers.database().tobytes()).hexdigest() == "2a74dc100db78a4b813c02bc8cef3e1f57fe92b9"


def test_a_missing_font_is_a_readable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(make_covers, "FONT", str(tmp_path / "missing.ttf"))
    with pytest.raises(SystemExit, match="YAADDI_FONT"):
        make_covers.main(["deck27"])


def test_an_unwritable_target_is_a_readable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(make_covers, "ROOT", str(tmp_path))  # course folders do not exist there
    monkeypatch.setattr(make_covers, "COVERS", {"nope/source/images/x.png": make_covers.database})
    with pytest.raises(SystemExit, match="cannot write"):
        make_covers.main([])


def test_an_unknown_filter_is_an_error():
    with pytest.raises(SystemExit, match="no cover matches"):
        make_covers.main(["no-such-cover"])
