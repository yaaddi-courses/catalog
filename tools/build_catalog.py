#!/usr/bin/env python3
"""Builds catalog.json — a single-file index of every course repo in the
yaaddi-courses GitHub organization.

Rearchitected for the one-repo-per-course split (each course used to be a
subfolder of this monorepo; now each course is its own repo, tagged with
the `yaaddi-course` topic). Discovery can no longer read local folders —
it queries GitHub's Search API for every repo in the org carrying that
topic, then fetches each one's own meta.json directly.

Two GitHub endpoints, for two different reasons:
  - api.github.com/search/repositories — lists every yaaddi-course-tagged
    repo in the org. Needs authentication (a token with at least
    `public_repo`/`Contents: read` on the org) since the unauthenticated
    rate limit (60/hour, and lower still for Search specifically — 10/min
    unauthenticated) is far too low for a scheduled job — see
    `.github/workflows/rebuild-catalog.yml`.
  - raw.githubusercontent.com — every actual meta.json fetch. NOT subject
    to the API rate limit at all, and doesn't need a token even for a
    public repo — matches the reasoning already documented in the Yaaddi
    app repo's src/lib/githubMarketplace.ts for why raw content (not the
    Contents API) is used for actual file bytes.

catalog.json's entry shape changes from the old monorepo version: `path`
(a folder within this repo) is replaced by `repo` ("owner/repo", the
course's own dedicated repo) + `branch` (that repo's default branch) — see
the Yaaddi app repo's src/lib/githubMarketplace.ts's `catalogSchema`,
which accepts BOTH the old `path`-based shape and this one, permanently
(there's no way to force an already-installed app build to stop
understanding the legacy shape). Every other field (title, description,
file, id, image, version, tags, language, titleTranslations,
descriptionTranslations, deckCount) is unchanged.

Cross-course id-uniqueness checking (previously validate_course.py --all's
job, run against local folders) happens here now instead, since this is
the only place that ever has every course's meta.json in memory at once —
see check_id_uniqueness() below. A collision is a hard failure (non-zero
exit), same severity as before.

Pure Python stdlib (urllib, not requests) — matches validate_course.py and
build_site.py's own "stdlib-only" convention, even though this now makes
real network calls instead of reading local files.

Usage:
    python tools/build_catalog.py                     # writes ./catalog.json
    python tools/build_catalog.py --out other.json     # custom output path
    python tools/build_catalog.py --org other-org --topic other-topic
    GITHUB_TOKEN=ghp_xxx python tools/build_catalog.py  # authenticated (required for CI-scale use)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_ORG = "yaaddi-courses"
DEFAULT_TOPIC = "yaaddi-course"

# How much of meta.json's full `description` survives into the summary
# catalog — the rest is only ever fetched on demand, via the app's
# fetchSingleCourseEntry.
DESCRIPTION_MAX_CHARS = 240


def truncate_description(text: str) -> str:
    if len(text) <= DESCRIPTION_MAX_CHARS:
        return text
    # Cut at the last space before the limit so a word never gets sliced
    # mid-way, then append the ellipsis the app's expand-tap logic looks
    # for (src/screens/MarketplaceScreen.tsx) to know more text exists.
    cut = text[:DESCRIPTION_MAX_CHARS].rsplit(" ", 1)[0]
    return cut.rstrip(",.;: ") + "…"


def _github_api_get(url: str, token: str | None) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def discover_course_repos(org: str, topic: str, token: str | None) -> list[dict]:
    """Every repo in `org` tagged with `topic`, paginated. Returns each
    repo's `full_name` ("owner/repo") and `default_branch`."""
    repos: list[dict] = []
    page = 1
    while True:
        url = (
            "https://api.github.com/search/repositories"
            f"?q=org:{org}+topic:{topic}&per_page=100&page={page}"
        )
        try:
            data = _github_api_get(url, token)
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            raise SystemExit(
                f"GitHub search API request failed (status {err.code}): {body}\n"
                "If this is a rate-limit error (403), the workflow's token "
                "may be missing or expired — see .github/workflows/rebuild-catalog.yml."
            ) from err
        items = data.get("items", [])
        repos.extend(
            {"full_name": item["full_name"], "default_branch": item["default_branch"]}
            for item in items
        )
        if len(items) < 100:
            break
        page += 1
    return repos


def fetch_meta(full_name: str, branch: str) -> dict | None:
    url = f"https://raw.githubusercontent.com/{full_name}/{branch}/meta.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None


# The lean field set src/lib/githubMarketplace.ts's summary-listing path
# builds from one course's meta.json — deliberately NOT the same full set
# fetchSingleCourseEntry gets from a direct meta.json fetch (see module
# docstring for why `toc`/`changelog` are trimmed/dropped here).
def build_catalog_entry(full_name: str, branch: str, meta: dict) -> dict | None:
    if "title" not in meta or "file" not in meta:
        return None

    entry = {
        "repo": full_name,
        "branch": branch,
        "title": meta["title"],
        "description": truncate_description(meta.get("description", "")),
        "file": meta["file"],
    }
    for key in (
        "id", "image", "version", "tags", "language",
        "titleTranslations", "descriptionTranslations",
    ):
        if key in meta:
            entry[key] = meta[key]
    if meta.get("toc"):
        entry["deckCount"] = len(meta["toc"])
    return entry


def check_id_uniqueness(entries: list[dict]) -> list[str]:
    """Returns a list of error messages for any `id` used by more than one
    entry — ported from validate_course.py's --all mode, which used to run
    this against local folders; this is now the only place that ever has
    every course in memory at once."""
    by_id: dict[str, list[str]] = {}
    for entry in entries:
        course_id = entry.get("id")
        if not course_id:
            continue
        by_id.setdefault(course_id, []).append(entry["repo"])

    errors = []
    for course_id, repos in by_id.items():
        if len(repos) > 1:
            errors.append(f'id "{course_id}" is used by multiple repos: {", ".join(repos)}')
    return errors


def build_catalog(org: str, topic: str, token: str | None) -> list[dict]:
    repos = discover_course_repos(org, topic, token)
    entries = []
    for repo in repos:
        meta = fetch_meta(repo["full_name"], repo["default_branch"])
        if meta is None:
            print(
                f"warning: {repo['full_name']} is tagged '{topic}' but has no "
                "readable meta.json at its repo root — skipped.",
                file=sys.stderr,
            )
            continue
        entry = build_catalog_entry(repo["full_name"], repo["default_branch"], meta)
        if entry is not None:
            entries.append(entry)

    id_errors = check_id_uniqueness(entries)
    if id_errors:
        for msg in id_errors:
            print(f"ERROR: {msg}", file=sys.stderr)
        raise SystemExit(1)

    # Sorted by repo for a stable, low-diff-noise output.
    entries.sort(key=lambda e: e["repo"])
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", default=DEFAULT_ORG, help="GitHub organization to scan")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="Repo topic identifying a course")
    parser.add_argument(
        "--out", default=str(REPO_ROOT / "catalog.json"), help="Output file path"
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    catalog = build_catalog(args.org, args.topic, token)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(catalog)} course(s))")


if __name__ == "__main__":
    main()
