#!/usr/bin/env python3
"""
Zips one course's source/{meta,units,cards}.csv (+ any referenced images/
audio) into <slug>.zip at the course folder's own root — this IS the file
the app downloads, so it gets committed to the repo tree alongside
meta.json, not left as a build artifact.

Why committed, not a GitHub Release asset: a GitHub Release asset would
avoid the git-history cost of a multi-MB binary, but Release assets
(objects.githubusercontent.com / release-assets.githubusercontent.com,
whichever the download redirect lands on) don't send
Access-Control-Allow-Origin — a browser fetch() from the Yaaddi web app
fails there with a CORS error every time (confirmed against the real repo,
not just docs). raw.githubusercontent.com — what a co-located, committed
file is served from — does support CORS. There's no backend to route
around that gap, so the committed file is the only option that works on
every platform (web included) without standing up server infrastructure.

No dependencies beyond the standard library (same convention as
validate_course.py) — this repo works standalone, without the Yaaddi app
repo cloned alongside.

Usage:
    python build_course_zip.py <course-folder>

Run this after any change to a course's source/, then `git add
<course-folder>/<slug>.zip` before committing — see README.md's
"Adding a new course" / "Updating an existing course" sections.
"""

import csv
import io
import os
import sys
import zipfile


def read_csv_text(text):
    return list(csv.DictReader(io.StringIO(text)))


def find_media_file(source_dir, filename):
    for candidate in (
        os.path.join(source_dir, filename),
        os.path.join(source_dir, "images", filename),
        os.path.join(source_dir, "media", filename),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def collect_referenced_filenames(meta_rows, unit_rows, card_rows):
    names = set()
    for row in meta_rows:
        if (row.get("image") or "").strip():
            names.add(row["image"].strip())
    for row in unit_rows:
        if (row.get("image") or "").strip():
            names.add(row["image"].strip())
        if (row.get("section_image") or "").strip():
            names.add(row["section_image"].strip())
    for row in card_rows:
        for col in ("image", "audio", "video"):
            value = (row.get(col) or "").strip()
            if value:
                names.add(value)
    return sorted(names)


def main():
    if len(sys.argv) != 2:
        print("Usage: python build_release_zip.py <course-folder>", file=sys.stderr)
        sys.exit(1)

    course_dir = sys.argv[1]
    source_dir = os.path.join(course_dir, "source")
    meta_path = os.path.join(source_dir, "meta.csv")
    units_path = os.path.join(source_dir, "units.csv")
    cards_path = os.path.join(source_dir, "cards.csv")

    for path in (meta_path, units_path, cards_path):
        if not os.path.isfile(path):
            print(f"Missing required file: {path}", file=sys.stderr)
            sys.exit(1)

    with open(meta_path, encoding="utf-8-sig") as f:
        meta_text = f.read()
    with open(units_path, encoding="utf-8-sig") as f:
        units_text = f.read()
    with open(cards_path, encoding="utf-8-sig") as f:
        cards_text = f.read()

    glossary_path = os.path.join(source_dir, "glossary.csv")
    glossary_text = None
    if os.path.isfile(glossary_path):
        with open(glossary_path, encoding="utf-8-sig") as f:
            glossary_text = f.read()

    meta_rows = read_csv_text(meta_text)
    if not meta_rows or not (meta_rows[0].get("slug") or "").strip():
        print("source/meta.csv is missing a \"slug\" column/value.", file=sys.stderr)
        sys.exit(1)
    slug = meta_rows[0]["slug"].strip()
    version = (meta_rows[0].get("version") or "").strip()
    if not version:
        print("source/meta.csv is missing a \"version\" column/value.", file=sys.stderr)
        sys.exit(1)

    referenced = collect_referenced_filenames(
        meta_rows, read_csv_text(units_text), read_csv_text(cards_text)
    )
    missing = []
    resolved = {}
    for filename in referenced:
        path = find_media_file(source_dir, filename)
        if path is None:
            missing.append(filename)
        else:
            resolved[filename] = path
    if missing:
        print(
            "Referenced but not found (checked source/, source/images/, source/media/): "
            + ", ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)

    out_path = os.path.join(course_dir, f"{slug}.zip")
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("meta.csv", meta_text)
        zf.writestr("units.csv", units_text)
        zf.writestr("cards.csv", cards_text)
        if glossary_text is not None:
            zf.writestr("glossary.csv", glossary_text)
        for filename, path in resolved.items():
            zf.write(path, filename)

    size_kb = round(os.path.getsize(out_path) / 1024)
    glossary_note = " + glossary.csv" if glossary_text is not None else ""
    print(
        f"Wrote {out_path} ({size_kb} KB — meta/units/cards.csv{glossary_note} + {len(resolved)} media file(s))",
        file=sys.stderr,
    )
    print(f"slug={slug} version={version}")


if __name__ == "__main__":
    main()
