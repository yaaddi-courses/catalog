#!/usr/bin/env python3
"""Builds catalog.json — a single-file index of every course in this repo.

The Yaaddi app's in-app Course Library used to discover courses by asking
GitHub for this repo's root directory listing, then fetching every single
course folder's own meta.json individually — one HTTP request per course.
That works fine at today's scale (a dozen courses) but doesn't at
thousands: even batched, thousands of individual requests take tens of
seconds to fully resolve, and GitHub's directory-listing API silently
truncates at 1000 entries with no pagination, meaning a course beyond
that point wouldn't even be discovered.

catalog.json collapses all of that into one file, and therefore one
request: every course folder's meta.json, concatenated into a single JSON
array at the repo root. The app tries fetching this first and only falls
back to the old per-folder scan if catalog.json is missing or fails to
parse — see src/lib/githubMarketplace.ts's fetchMarketplaceCoursesUncached
in the Yaaddi app repo.

This is regenerated automatically in CI (.github/workflows/validate-courses.yml,
the same auto-commit pattern already used for ensure_course_ids.py) on every
push to main — an author never needs to remember to run this by hand,
though `python tools/build_catalog.py` also works standalone for a local
sanity check.

Kept deliberately lean as the course count grows: `description` is
truncated to DESCRIPTION_MAX_CHARS (full text lives in the course's own
meta.json), `toc` is collapsed to a `deckCount` integer (the app only
shows the real deck list once a learner actually expands a course, at
which point it fetches that one course's full meta.json on demand —
see the Yaaddi app repo's src/lib/githubMarketplace.ts's
fetchSingleCourseEntry), and `changelog` is dropped entirely (the app's
"check for updates" flow already re-fetches each installed course's own
meta.json fresh, never reading changelog from this bulk file).

Pure Python stdlib — no dependencies, matches validate_course.py and
build_site.py's own "stdlib-only" convention.

Usage:
    python tools/build_catalog.py                    # writes ./catalog.json
    python tools/build_catalog.py --out other.json    # custom output path
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Folders at repo root that are never course folders — matches
# build_site.py's SKIP_DIRS exactly (kept as a separate copy, not a shared
# import, since these are independent CLI scripts with no package
# structure between them — see AUTHORING.md for why this repo stays a flat
# script layout rather than introducing a shared module).
SKIP_DIRS = {
    ".git", ".github", ".internal", "__pycache__", "tools", "_site",
    "node_modules",
}


def discover_courses(root: Path) -> list[Path]:
    courses = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in SKIP_DIRS or child.name.startswith("."):
            continue
        if (child / "meta.json").exists():
            courses.append(child)
    return courses


# How much of meta.json's full `description` survives into the summary
# catalog — the rest is only ever fetched on demand (see module docstring).
DESCRIPTION_MAX_CHARS = 240


def truncate_description(text: str) -> str:
    if len(text) <= DESCRIPTION_MAX_CHARS:
        return text
    # Cut at the last space before the limit so a word never gets sliced
    # mid-way, then append the ellipsis the app's expand-tap logic looks
    # for (src/screens/MarketplaceScreen.tsx) to know more text exists.
    cut = text[:DESCRIPTION_MAX_CHARS].rsplit(" ", 1)[0]
    return cut.rstrip(",.;: ") + "…"


# The lean field set src/lib/githubMarketplace.ts's summary-listing path
# builds from one folder's meta.json — deliberately NOT the same full set
# fetchSingleCourseEntry gets from a direct meta.json fetch (see module
# docstring for why `toc`/`changelog` are trimmed/dropped here). "path" is
# the only field not read verbatim from meta.json (it's the folder name,
# needed to resolve `image`/`file`'s relative paths and to build the
# course's install/update URLs).
def build_catalog_entry(course_dir: Path) -> dict | None:
    meta_path = course_dir / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if "title" not in meta or "file" not in meta:
        return None

    entry = {
        "path": course_dir.name,
        "title": meta["title"],
        "description": truncate_description(meta.get("description", "")),
        "file": meta["file"],
    }
    # Optional fields are only included when meta.json actually provides
    # them — matches fetchCourseEntry's own "undefined, not null/empty"
    # convention for an absent optional field, so the app's existing
    # zod schema (which already treats these as optional) parses either
    # source identically. `changelog` is deliberately never included here
    # (see module docstring) and `toc` becomes a bare count.
    for key in (
        "id", "image", "version", "tags", "language",
        "titleTranslations", "descriptionTranslations",
    ):
        if key in meta:
            entry[key] = meta[key]
    if meta.get("toc"):
        entry["deckCount"] = len(meta["toc"])
    return entry


def build_catalog(root: Path) -> list[dict]:
    entries = []
    for course_dir in discover_courses(root):
        entry = build_catalog_entry(course_dir)
        if entry is not None:
            entries.append(entry)
    # Sorted by folder path for a stable, low-diff-noise output — otherwise
    # every regeneration could reorder entries based on filesystem
    # iteration order alone and make every PR's catalog.json diff larger
    # than the actual change.
    entries.sort(key=lambda e: e["path"])
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=str(REPO_ROOT / "catalog.json"), help="Output file path"
    )
    args = parser.parse_args()

    catalog = build_catalog(REPO_ROOT)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(catalog)} course(s))")


if __name__ == "__main__":
    main()
