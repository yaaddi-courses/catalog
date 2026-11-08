"""capture_guide_shots.py argument and device handling (no device or OCR needed)."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "guide"))

import capture_guide_shots as cgs  # noqa: E402

MANIFEST = {"device_size": [1080, 2400], "shots": [{"file": "a.png"}, {"file": "b.png"}]}


def test_only_selects_the_named_shots():
    assert [s["file"] for s in cgs.select_shots(MANIFEST, ["b.png"])] == ["b.png"]
    assert len(cgs.select_shots(MANIFEST, None)) == 2


# Regression (H21): a misspelled --only captured nothing and exited 0.
def test_an_unknown_only_name_is_an_error():
    with pytest.raises(SystemExit, match="b.pgn"):
        cgs.select_shots(MANIFEST, ["a.png", "b.pgn"])
    with pytest.raises(SystemExit, match="no shots"):
        cgs.select_shots({"shots": []}, None)


# Regression (N212): a missing adb or a failing adb command gave a raw traceback.
def test_a_missing_adb_is_a_readable_error(tmp_path):
    with pytest.raises(SystemExit, match="adb not found"):
        cgs.check_adb(str(tmp_path / "no-adb.exe"))


def test_a_failing_adb_command_is_a_readable_error(monkeypatch):
    def fail(*a, **k):
        raise subprocess.CalledProcessError(1, a[0], output=b"", stderr=b"error: no devices/emulators found")
    monkeypatch.setattr(cgs.subprocess, "run", fail)
    with pytest.raises(SystemExit, match="no devices/emulators found"):
        cgs.Device("adb", None).run("shell", "true")


def test_a_device_of_another_size_is_refused(monkeypatch):
    dev = cgs.Device("adb", None)
    monkeypatch.setattr(dev, "run", lambda *a, **k: "Physical size: 720x1600\n")
    with pytest.raises(SystemExit, match="720x1600"):
        cgs.check_device_size(dev, [1080, 2400])
    monkeypatch.setattr(dev, "run", lambda *a, **k: "Physical size: 1080x2400\n")
    cgs.check_device_size(dev, [1080, 2400])
