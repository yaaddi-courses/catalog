#!/usr/bin/env python3
"""
Assigns a stable meta.json "id" to any course folder that doesn't have one
yet — see validate_course.py's own check for why this matters: without a
stable id, renaming a course's folder later silently breaks "check for
updates" for everyone who already installed it (the app has no other way
to recognize this is the same course under a new name).

The assigned id is simply the folder name at the time this runs — the same
value the app already fell back to for identity before this feature
existed, so assigning it now is a no-op for every already-installed copy
of an existing course (their stored source_folder already equals this
value). It only pays off the moment a folder is renamed *after* this runs.

Idempotent and safe to run repeatedly: a course that already has an "id"
is left untouched, keys are inserted first (Python 3.7+ dicts preserve
insertion order) so the file's JSON key order stays close to hand-written
(id, title, description, ...), and only files that actually needed a
change are rewritten (so `git diff`/CI only touches what's new).

Usage:
    python ensure_course_ids.py                # every course folder at the repo root
    python ensure_course_ids.py <course-folder> # just one

Exit code is non-zero if it's ever asked to assign an id that collides
with one already used by another course in the repo (extremely unlikely
given ids default to the already-unique folder name, but checked anyway).
"""

import json
import os
import sys


def load_meta(course_dir):
    meta_path = os.path.join(course_dir, "meta.json")
    if not os.path.isfile(meta_path):
        return None, meta_path
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f), meta_path


def ensure_id(course_dir, existing_ids):
    name = os.path.basename(os.path.normpath(course_dir))
    meta, meta_path = load_meta(course_dir)
    if meta is None:
        return None  # not a course folder (no meta.json) — silently skip, same convention validate_course.py --all uses

    current_id = (meta.get("id") or "").strip()
    if current_id:
        if current_id in existing_ids and existing_ids[current_id] != name:
            print(
                f'ERROR: {name}/meta.json "id" ("{current_id}") is already used by '
                f'"{existing_ids[current_id]}" — ids must be unique.',
                file=sys.stderr,
            )
            return False
        existing_ids[current_id] = name
        return None  # already has one, nothing to do

    new_id = name
    if new_id in existing_ids:
        print(
            f'ERROR: {name} has no "id" and its folder name is already used as another '
            f'course\'s id — assign one manually in {meta_path}.',
            file=sys.stderr,
        )
        return False

    # Rebuild the dict with "id" first (Python 3.7+ preserves insertion
    # order) so the file reads naturally, matching how it'd look if an
    # author had written it by hand from the start.
    reordered = {"id": new_id}
    reordered.update(meta)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(reordered, f, indent=2, ensure_ascii=False)
        f.write("\n")

    existing_ids[new_id] = name
    print(f'{name}: assigned id "{new_id}"')
    return True


def main():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    targets = sys.argv[1:] if len(sys.argv) > 1 else None

    if targets is None:
        targets = [
            os.path.join(repo_root, entry)
            for entry in sorted(os.listdir(repo_root))
            if os.path.isdir(os.path.join(repo_root, entry))
            and os.path.isfile(os.path.join(repo_root, entry, "meta.json"))
        ]

    existing_ids = {}
    assigned = 0
    had_error = False
    for course_dir in targets:
        result = ensure_id(course_dir, existing_ids)
        if result is True:
            assigned += 1
        elif result is False:
            had_error = True

    if had_error:
        sys.exit(1)
    if assigned == 0:
        print("Every course already has an id — nothing to do.")
    else:
        print(f"\nAssigned {assigned} course id(s). Review and commit the meta.json change(s).")


if __name__ == "__main__":
    main()
