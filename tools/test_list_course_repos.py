"""list_course_repos.py prints the tagged course repos as JSON for pages.yml's clone step."""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import list_course_repos as lcr  # noqa: E402


def test_prints_the_discovered_repos_as_json(monkeypatch):
    repos = [{"full_name": "o/r", "default_branch": "main", "pushed_at": ""}]
    seen = {}

    def fake(org, topic, token):
        seen.update(org=org, topic=topic, token=token)
        return repos

    monkeypatch.setattr(lcr, "discover_course_repos", fake)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    lcr.main()
    assert json.loads(out.getvalue()) == repos
    assert seen == {"org": lcr.DEFAULT_ORG, "topic": lcr.DEFAULT_TOPIC, "token": "t"}
