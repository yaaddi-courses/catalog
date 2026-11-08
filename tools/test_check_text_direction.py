"""check_text_direction.py and check_cross_course_consistency.py: BOM-prefixed files are read like
any other, and --all means this repo's courses whatever the current directory is."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_cross_course_consistency as cccc  # noqa: E402
import check_text_direction as ctd  # noqa: E402

TOOLS = Path(__file__).resolve().parent


def test_text_direction_reads_a_bom_csv(tmp_path):
    path = tmp_path / "meta.csv"
    path.write_bytes(b"\xef\xbb\xbfid,language\r\n1,fa\r\n")
    assert ctd.read_csv(str(path)) == [{"id": "1", "language": "fa"}]


def test_text_direction_all_uses_the_repo_root(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ctd, "find_all_course_dirs", lambda root: seen.setdefault("root", root) and [])
    monkeypatch.setattr(sys, "argv", ["check_text_direction.py", "--all"])
    try:
        ctd.main()
    except SystemExit as exit_:
        assert exit_.code not in (0, None)  # no courses found is an error, not a clean pass
    assert Path(seen["root"]) == TOOLS.parent


def test_cross_course_reads_tags_from_a_bom_meta_json(tmp_path):
    (tmp_path / "meta.json").write_bytes(b"\xef\xbb\xbf" + json.dumps({"tags": ["Python "]}).encode("utf-8"))
    assert cccc.load_tags(tmp_path) == {"python"}
