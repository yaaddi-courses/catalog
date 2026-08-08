#!/usr/bin/env python3
"""
Zips one course's source/{meta,units,cards}.csv (+ any referenced images/
audio) into <slug>.zip at the course folder's own root, ready to attach to
a GitHub Release — see README.md's "Delivery mechanism" note for why the
built file is a Release asset, never something committed to the repo tree.

No dependencies beyond the standard library (same convention as
validate_course.py) — this repo works standalone, without the Yaaddi app
repo cloned alongside.

Usage:
    python build_release_zip.py <course-folder>

Prints "slug=<slug> version=<version>" on success, for the calling CI step
to name/tag the Release with — see .github/workflows/release-courses.yml.
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
        for filename, path in resolved.items():
            zf.write(path, filename)

    size_kb = round(os.path.getsize(out_path) / 1024)
    print(
        f"Wrote {out_path} ({size_kb} KB — meta/units/cards.csv + {len(resolved)} media file(s))",
        file=sys.stderr,
    )
    print(f"slug={slug} version={version}")


if __name__ == "__main__":
    main()
