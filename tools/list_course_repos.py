#!/usr/bin/env python3
"""Prints every yaaddi-courses org repo tagged `yaaddi-course` as JSON
(`[{"full_name": ..., "default_branch": ...}, ...]`) — the same discovery
`build_catalog.py` uses, factored out so `pages.yml`'s shallow-clone step
can reuse it without also fetching every course's meta.json (which
build_catalog.py's own CLI always does).

Usage:
    GITHUB_TOKEN=ghp_xxx python tools/list_course_repos.py
"""
from __future__ import annotations

import json
import os
import sys

from build_catalog import DEFAULT_ORG, DEFAULT_TOPIC, discover_course_repos


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repos = discover_course_repos(DEFAULT_ORG, DEFAULT_TOPIC, token)
    json.dump(repos, sys.stdout)


if __name__ == "__main__":
    main()
