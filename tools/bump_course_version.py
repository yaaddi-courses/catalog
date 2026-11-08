#!/usr/bin/env python3
"""Bumps a course's version when it is about to be pushed (owner, 2026-10-31: at push time, not at every commit).

Rule (flashcard-course-creator section 7a): the content that is going to GitHub must carry a new version, in
`meta.json` (what "check for updates" reads) AND `source/meta.csv` (baked into the zip), with a changelog entry,
and the zip rebuilt. Commit freely while working; run this once, right before the push. It compares the course
against what is already pushed (the upstream branch, else origin/main, else HEAD), whether the changes are
committed or not:

  python tools/bump_course_version.py <course-folder>                 # bump if content differs from the pushed one, build the zip, validate
  python tools/bump_course_version.py <course-folder> --note "text"   # with your own changelog note (preferred)
  python tools/bump_course_version.py <course-folder> --level minor   # override the level
  python tools/bump_course_version.py <course-folder> --check         # exit 1 if content changed but the version did not
  python tools/bump_course_version.py <course-folder> --force --note "text"   # bump although nothing differs

Level (from the diff against the pushed version): major when deck (unit) ids were added or removed; minor when
card ids or glossary terms or article files were added or removed; patch for any other content change (wording,
links, images). The new version is computed from the pushed version, so running it twice never bumps twice.
It does NOT commit or push: commit the version files and zip it wrote, then push.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

# Paths whose changes are not "content": the version bookkeeping itself and the build output.
NOT_CONTENT = {"meta.json", "source/meta.csv"}


def git(course: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=course, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def base_ref(course: Path) -> str:
    """What is already pushed: the upstream branch, else origin/main, else HEAD (a repo with no remote).
    Empty when the repo has no commit yet."""
    for ref in ("@{u}", "origin/main", "HEAD"):
        try:
            return git(course, "rev-parse", "--verify", "--quiet", ref).strip()
        except RuntimeError:
            continue
    return ""


def changed_paths(course: Path, base: str) -> list[str]:
    """Paths under the course folder that differ from `base` (committed or not, new files too), content only."""
    out = git(course, "diff", "--name-only", "--relative", base, "--", ".")
    out += git(course, "ls-files", "--others", "--exclude-standard", "--", ".")
    return sorted({p for p in out.splitlines() if p not in NOT_CONTENT and not p.endswith(".zip")})


def base_text(course: Path, base: str, rel: str) -> str | None:
    try:
        return git(course, "show", f"{base}:{(Path(git(course, 'rev-parse', '--show-prefix').strip()) / rel).as_posix()}")
    except RuntimeError:
        return None


def column_ids(text: str | None, column: str) -> set[str]:
    if not text:
        return set()
    return {row[column] for row in csv.DictReader(io.StringIO(text)) if row.get(column)}


def id_column(text: str | None) -> str:
    header = (text or "").splitlines()[0] if text else ""
    return "id" if "id" in header.split(",") else header.split(",")[0]


def ids_changed(course: Path, base: str, rel: str, column: str | None = None) -> bool:
    new_path = course / rel
    new = new_path.read_text(encoding="utf-8") if new_path.exists() else None
    old = base_text(course, base, rel)
    col = column or id_column(new or old)
    return column_ids(old, col) != column_ids(new, col)


def suggest_level(course: Path, base: str, changed: list[str]) -> str:
    if "source/units.csv" in changed and ids_changed(course, base, "source/units.csv"):
        return "major"
    if "source/cards.csv" in changed and ids_changed(course, base, "source/cards.csv"):
        return "minor"
    if "source/glossary.csv" in changed and ids_changed(course, base, "source/glossary.csv", "term"):
        return "minor"
    if any(p.startswith("source/articles/") and (course / p).exists() != (base_text(course, base, p) is not None) for p in changed):
        return "minor"
    return "patch"


def bump(version: str, level: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def auto_note(changed: list[str]) -> str:
    kinds = []
    for label, test in (
        ("card content", lambda p: p == "source/cards.csv"),
        ("deck list", lambda p: p == "source/units.csv"),
        ("glossary", lambda p: p == "source/glossary.csv"),
        ("articles", lambda p: p.startswith("source/articles/")),
        ("pictures", lambda p: "/images/" in p or p.endswith((".png", ".jpg", ".webp"))),
        ("audio", lambda p: "/audio/" in p or p.endswith((".mp3", ".wav"))),
    ):
        if any(test(p) for p in changed):
            kinds.append(label)
    return "Updated " + (", ".join(kinds) if kinds else "course content") + "."


def write_version(course: Path, version: str, note: str) -> None:
    meta_path = course / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["version"] = version
    meta.setdefault("changelog", []).append({"version": version, "date": date.today().isoformat(), "notes": note})
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    csv_path = course / "source" / "meta.csv"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0].keys())
    rows[0]["version"] = version
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def base_version(course: Path, base: str) -> str | None:
    text = base_text(course, base, "meta.json")
    return json.loads(text).get("version") if text else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course")
    parser.add_argument("--level", choices=["patch", "minor", "major"])
    parser.add_argument("--note")
    parser.add_argument("--check", action="store_true", help="only report; exit 1 when a bump is missing")
    parser.add_argument("--force", action="store_true", help="bump even when there is no uncommitted content change")
    parser.add_argument("--skip-build", action="store_true", help="do not rebuild the zip or run the validator")
    args = parser.parse_args(argv)
    course = Path(args.course).resolve()

    ref = base_ref(course)
    current = json.loads((course / "meta.json").read_text(encoding="utf-8"))["version"]
    base = base_version(course, ref) if ref else None
    if base is None:
        print(f"{course.name}: not pushed yet, version stays {current}")
        return 0
    changed = changed_paths(course, ref)
    if not changed and not args.force:
        print(f"{course.name}: no content change, version stays {current}")
        return 0
    if current != base:
        print(f"{course.name}: content changed and the version is already {current} (was {base})")
        return 0
    if args.check:
        print(f"{course.name}: content changed but the version is still {base}: run bump_course_version.py")
        return 1

    level = args.level or ("patch" if not changed else suggest_level(course, ref, changed))
    version = bump(base, level)
    version_files = [course / "meta.json", course / "source" / "meta.csv"]
    before = [path.read_bytes() for path in version_files]
    write_version(course, version, args.note or auto_note(changed))
    print(f"{course.name}: {base} -> {version} ({level})")
    if args.skip_build:
        return 0
    failed = (
        subprocess.run([sys.executable, "build_course_zip.py", "."], cwd=course).returncode
        or subprocess.run([sys.executable, "validate_course.py", ".", "--source"], cwd=course).returncode
    )
    if failed:
        # Put the old version back: otherwise a re-run sees "already bumped", skips the build and
        # leaves a pushed version number with no matching zip.
        for path, data in zip(version_files, before):
            path.write_bytes(data)
        print(f"{course.name}: build or validation failed, version restored to {base}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
