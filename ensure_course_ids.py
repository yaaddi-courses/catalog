#!/usr/bin/env python3
"""
Assigns a stable, NEUTRAL meta.json "id" to any course folder that doesn't
have one yet — see validate_course.py's own check for why this matters:
without a stable id, renaming a course's folder (or retitling it) later
silently breaks "check for updates" for everyone who already installed it
(the app has no other way to recognize this is the same course under a new
name/folder).

The assigned id is an opaque random token (12 hex chars) — deliberately
NOT the folder name or a slug of the title, both of which can change after
publishing. An id that reads as "obviously derived from the current name"
invites someone to "helpfully" update it to match after a rename, which is
exactly the mistake that breaks existing installs; an opaque token has no
such temptation.

Idempotent and safe to run repeatedly: a course that already has a
non-slug-derived "id" is left untouched, keys are inserted first (Python
3.7+ dicts preserve insertion order) so the file's JSON key order stays
close to hand-written (id, title, description, ...), and only files that
actually needed a change are rewritten (so `git diff`/CI only touches
what's new).

Usage:
    python ensure_course_ids.py                     # assign ids to courses missing one
    python ensure_course_ids.py <course-folder>      # just one
    python ensure_course_ids.py --regenerate-slug-ids [course-folder ...]
        # also replaces any EXISTING id that looks derived from the
        # course's current title/folder name (validate_course.py's
        # id-neutrality warning) with a fresh opaque token. Only safe to
        # run before a course has real installs relying on its old id —
        # this repo is pre-1.0 with no tagged releases, so every course's
        # slug-derived id gets replaced once, then this flag never needs
        # to run again.

Exit code is non-zero if it's ever asked to assign an id that collides
with one already in use (vanishingly unlikely with a random 12-hex-char
token, but checked and retried anyway).
"""

import json
import os
import secrets
import sys


def _slugify(text):
    out = []
    prev_hyphen = False
    for ch in (text or "").lower():
        if ch.isalnum():
            out.append(ch)
            prev_hyphen = False
        elif not prev_hyphen:
            out.append("-")
            prev_hyphen = True
    return "".join(out).strip("-")


def _looks_like_slug(course_id, reference_text):
    reference_slug = _slugify(reference_text)
    if not reference_slug:
        return False
    normalized_id = course_id.strip().lower()
    return normalized_id == reference_slug or normalized_id == reference_slug.replace("-", "")


def _new_opaque_id(existing_ids):
    while True:
        candidate = secrets.token_hex(6)  # 12 hex chars
        if candidate not in existing_ids:
            return candidate


def load_meta(course_dir):
    meta_path = os.path.join(course_dir, "meta.json")
    if not os.path.isfile(meta_path):
        return None, meta_path
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f), meta_path


def _write_id(meta, meta_path, new_id):
    # Rebuild the dict with "id" first (Python 3.7+ preserves insertion
    # order) so the file reads naturally, matching how it'd look if an
    # author had written it by hand from the start.
    reordered = {"id": new_id}
    reordered.update({k: v for k, v in meta.items() if k != "id"})
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(reordered, f, indent=2, ensure_ascii=False)
        f.write("\n")


def ensure_id(course_dir, existing_ids, regenerate_slug_ids=False):
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
        if regenerate_slug_ids and (
            _looks_like_slug(current_id, meta.get("title") or "") or _looks_like_slug(current_id, name)
        ):
            new_id = _new_opaque_id(existing_ids)
            _write_id(meta, meta_path, new_id)
            existing_ids[new_id] = name
            print(f'{name}: replaced slug-derived id "{current_id}" with opaque id "{new_id}"')
            return True
        existing_ids[current_id] = name
        return None  # already has a good id, nothing to do

    new_id = _new_opaque_id(existing_ids)
    _write_id(meta, meta_path, new_id)
    existing_ids[new_id] = name
    print(f'{name}: assigned id "{new_id}"')
    return True


def main():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    args = sys.argv[1:]
    regenerate_slug_ids = "--regenerate-slug-ids" in args
    positional = [a for a in args if a != "--regenerate-slug-ids"]
    targets = positional if positional else None

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
        result = ensure_id(course_dir, existing_ids, regenerate_slug_ids=regenerate_slug_ids)
        if result is True:
            assigned += 1
        elif result is False:
            had_error = True

    if had_error:
        sys.exit(1)
    if assigned == 0:
        print("Every course already has a good id — nothing to do.")
    else:
        print(f"\nChanged {assigned} course id(s). Review and commit the meta.json change(s).")


if __name__ == "__main__":
    main()
