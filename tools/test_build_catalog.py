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


class _Resp:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def _http_error(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


def test_fetch_meta_retries_a_temporary_failure_then_succeeds(monkeypatch):
    replies = [_http_error(503), TimeoutError(), _Resp(b'{"title": "T"}')]

    def fake_urlopen(url, timeout):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(bc.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(bc.time, "sleep", lambda s: None)
    assert bc.fetch_meta("o/r", "main") == {"title": "T"}


def test_fetch_meta_fails_instead_of_dropping_a_course_on_a_persistent_error(monkeypatch):
    def fake_urlopen(url, timeout):
        raise _http_error(503)

    monkeypatch.setattr(bc.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(bc.time, "sleep", lambda s: None)
    try:
        bc.fetch_meta("o/r", "main")
    except SystemExit as exit_:
        assert "o/r" in str(exit_)
    else:
        raise AssertionError("expected SystemExit")


def test_fetch_meta_returns_none_for_a_missing_or_broken_file(monkeypatch):
    for reply in (_http_error(404), _Resp(b"\xff\xfe")):

        def fake_urlopen(url, timeout, reply=reply):
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(bc.urllib.request, "urlopen", fake_urlopen)
        assert bc.fetch_meta("o/r", "main") is None


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


# Regression (H10): a meta.json saved with a UTF-8 BOM was "unreadable" and the course dropped.
def test_fetch_meta_reads_a_bom_meta_json(monkeypatch):
    monkeypatch.setattr(bc.urllib.request, "urlopen", lambda url, timeout: _Resp(b'\xef\xbb\xbf{"title": "T"}'))
    assert bc.fetch_meta("o/r", "main") == {"title": "T"}


# Regression (H10): a search result GitHub marks incomplete silently dropped repos.
def test_discovery_fails_on_an_incomplete_search_result(monkeypatch):
    page = {"incomplete_results": True, "items": []}
    monkeypatch.setattr(bc, "_github_api_get", lambda url, token: page)
    try:
        bc.discover_course_repos("o", "t", None)
    except SystemExit as exit_:
        assert "incomplete" in str(exit_)
    else:
        raise AssertionError("expected SystemExit")


# Regression (H11): a zip path with a space made an invalid URL (http.client.InvalidURL), and
# connection resets were not caught, so the whole catalog job crashed.
def test_last_commit_date_quotes_the_path_and_survives_any_network_error(monkeypatch):
    seen = {}

    def fake(url, token):
        seen["url"] = url
        return []

    monkeypatch.setattr(bc, "_github_api_get", fake)
    bc.fetch_last_commit_date("o/r", "my course.zip", None)
    assert "path=my%20course.zip" in seen["url"]
    import http.client

    for err in (ConnectionResetError(), http.client.IncompleteRead(b""), http.client.InvalidURL("x")):

        def boom(url, token, err=err):
            raise err

        monkeypatch.setattr(bc, "_github_api_get", boom)
        assert bc.fetch_last_commit_date("o/r", "t.zip", None) == ""
