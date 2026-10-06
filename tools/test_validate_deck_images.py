import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "validate_course", Path(__file__).parent.parent / "python-basics" / "validate_course.py"
)
vc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vc)


def run(tmp_path, units, files):
    images = tmp_path / "images"
    images.mkdir()
    for name, content in files.items():
        (images / name).write_bytes(content)
    report = vc.Report("t")
    vc.validate_deck_images(units, str(images), report)
    return report.errors


def unit(uid, image):
    return {"id": uid, "title": f"Deck {uid}", "image": image}


def test_two_decks_pointing_at_the_same_file_are_an_error(tmp_path):
    errors = run(tmp_path, [unit("1", "a.png"), unit("2", "a.png")], {"a.png": b"AAA"})
    assert any("same image" in e and "Deck 1" in e and "Deck 2" in e for e in errors)


def test_two_different_files_with_identical_pixels_are_an_error(tmp_path):
    errors = run(tmp_path, [unit("1", "a.png"), unit("2", "b.png")], {"a.png": b"AAA", "b.png": b"AAA"})
    assert any("same image" in e for e in errors)


def test_every_deck_with_its_own_image_passes(tmp_path):
    errors = run(tmp_path, [unit("1", "a.png"), unit("2", "b.png")], {"a.png": b"AAA", "b.png": b"BBB"})
    assert errors == []


def test_a_deck_without_an_image_file_is_left_to_the_other_checks(tmp_path):
    assert run(tmp_path, [unit("1", "missing.png"), unit("2", "")], {}) == []
