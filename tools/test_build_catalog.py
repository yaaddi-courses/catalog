import importlib.util
import urllib.error
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "build_catalog", Path(__file__).parent / "build_catalog.py"
)
bc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bc)

META = {
    "title": "T",
    "description": "d",
    "file": "t.zip",
    "id": "abc",
    "changelog": [
        {"version": "1.0.0", "date": "2026-08-01", "notes": "n"},
        {"version": "1.2.0", "date": "2026-10-02", "notes": "n"},
        {"version": "1.1.0", "date": "2026-09-01", "notes": "n"},
    ],
}
NO_CHANGELOG = {k: v for k, v in META.items() if k != "changelog"}


def test_entry_carries_the_newest_release_date_whatever_the_changelog_order():
    entry = bc.build_catalog_entry("o/r", "main", META, pushed_at="2026-10-03")
    assert entry["updated"] == "2026-10-02"


def test_entry_falls_back_to_the_given_date_without_a_changelog():
    entry = bc.build_catalog_entry("o/r", "main", NO_CHANGELOG, pushed_at="2026-10-03T08:00:00Z")
    assert entry["updated"] == "2026-10-03"


def test_entry_omits_the_date_when_nothing_is_known():
    assert "updated" not in bc.build_catalog_entry("o/r", "main", NO_CHANGELOG)


def test_entry_never_carries_stars_or_comments():
    entry = bc.build_catalog_entry("o/r", "main", META, pushed_at="2026-10-03")
    assert "stars" not in entry and "comments" not in entry


def test_last_commit_date_reads_the_newest_commit_touching_the_zip(monkeypatch):
    seen = {}

    def fake(url, token):
        seen["url"] = url
        return [{"commit": {"committer": {"date": "2026-09-30T12:00:00Z"}}}]

    monkeypatch.setattr(bc, "_github_api_get", fake)
    assert bc.fetch_last_commit_date("o/r", "t.zip", None) == "2026-09-30"
    assert "commits?path=t.zip" in seen["url"]


def test_last_commit_date_is_empty_when_github_cannot_be_read(monkeypatch):
    def boom(url, token):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(bc, "_github_api_get", boom)
    assert bc.fetch_last_commit_date("o/r", "t.zip", None) == ""
    monkeypatch.setattr(bc, "_github_api_get", lambda url, token: [])
    assert bc.fetch_last_commit_date("o/r", "t.zip", None) == ""
    monkeypatch.setattr(bc, "_github_api_get", lambda url, token: {"message": "oops"})
    assert bc.fetch_last_commit_date("o/r", "t.zip", None) == ""


def test_discovery_returns_the_push_time(monkeypatch):
    page = {
        "items": [
            {"full_name": "o/r", "default_branch": "main", "pushed_at": "2026-10-03T00:00:00Z"}
        ]
    }
    monkeypatch.setattr(bc, "_github_api_get", lambda url, token: page)
    assert bc.discover_course_repos("o", "t", None) == [
        {"full_name": "o/r", "default_branch": "main", "pushed_at": "2026-10-03T00:00:00Z"}
    ]


def test_build_catalog_uses_the_changelog_and_only_asks_github_when_it_has_none(monkeypatch):
    monkeypatch.setattr(
        bc,
        "discover_course_repos",
        lambda org, topic, token: [
            {"full_name": "o/b", "default_branch": "main", "pushed_at": "2026-10-03T00:00:00Z"},
            {"full_name": "o/a", "default_branch": "main", "pushed_at": "2026-10-03T00:00:00Z"},
        ],
    )
    metas = {"o/a": {**META, "id": "a"}, "o/b": {**NO_CHANGELOG, "id": "b"}}
    monkeypatch.setattr(bc, "fetch_meta", lambda full_name, branch: metas[full_name])
    calls = []

    def fake_commit_date(full_name, path, token):
        calls.append(full_name)
        return "2026-09-20"

    monkeypatch.setattr(bc, "fetch_last_commit_date", fake_commit_date)

    catalog = bc.build_catalog("o", "t", None)

    assert [e["repo"] for e in catalog] == ["o/a", "o/b"]
    assert catalog[0]["updated"] == "2026-10-02"  # from its changelog
    assert catalog[1]["updated"] == "2026-09-20"  # from the newest commit to its zip
    assert calls == ["o/b"]
