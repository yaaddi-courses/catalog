#!/usr/bin/env python3
"""Post-processing filter for self_standing_report.txt.

check_self_standing.py only sends a card's prompt+options text to the
model, not whether the card has an attached image — so a card like
"What does this photo show?" gets flagged as relying on unstated
context, when in the real app the learner sees the image right on the
card and "this photo" has a perfectly valid referent. Confirmed by
sampling: every flagged "this/that photo/picture/image/portrait/
uniform/..." card in canadian-citizenship's run genuinely had a non-
blank `image` field.

This script re-checks every flagged line against its real `image`
field in that course's cards.csv and drops the ones that are almost
certainly false positives for this specific reason, writing a cleaned
report next to the original (original is untouched, for audit).

Usage:
    python tools/filter_self_standing_report.py [report_path]
"""
import csv
import os
import re
import sys

IMAGE_REFERENCE_PATTERN = re.compile(
    r"\b(this|that|these|those)\b.{0,15}\b"
    r"(photo|picture|image|portrait|uniform|badge|flag|map|symbol|diagram|icon|logo|scene)",
    re.IGNORECASE,
)
# Also catches the inverted phrasing, e.g. "Which portrait shows...".
IMAGE_LEAD_PATTERN = re.compile(
    r"^(which|what)\b.{0,30}\b(photo|picture|image|portrait|uniform|badge|flag|map|symbol|diagram|icon|logo|scene)\b",
    re.IGNORECASE,
)

LINE_RE = re.compile(r"^(?P<course>[^|]+)\|\s*card\s+(?P<id>\S+)\s*\|\s*\"(?P<prompt>.*)\"\s*$")


def load_card_images(repo_root, course):
    path = os.path.join(repo_root, course, "source", "cards.csv")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        return {r["id"]: (r.get("image") or "").strip() for r in csv.DictReader(f)}


def main():
    report_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "self_standing_report.txt")
    if not os.path.isfile(report_path):
        print(f"no report at {report_path}")
        return

    with open(report_path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]

    repo_root = os.getcwd()
    image_cache = {}
    kept, dropped = [], []

    for line in lines:
        m = LINE_RE.match(line)
        if not m:
            kept.append(line)  # don't drop anything we can't parse
            continue
        course, cid, prompt = m.group("course").strip(), m.group("id"), m.group("prompt")
        looks_image_referencing = bool(IMAGE_REFERENCE_PATTERN.search(prompt) or IMAGE_LEAD_PATTERN.search(prompt))
        if not looks_image_referencing:
            kept.append(line)
            continue
        if course not in image_cache:
            image_cache[course] = load_card_images(repo_root, course)
        has_image = bool(image_cache[course].get(cid))
        if has_image:
            dropped.append(line)
        else:
            kept.append(line)  # references an image but has none — genuinely broken, keep

    cleaned_path = report_path.replace(".txt", "_cleaned.txt")
    with open(cleaned_path, "w", encoding="utf-8") as f:
        for l in kept:
            f.write(l + "\n")

    print(f"kept {len(kept)}, dropped {len(dropped)} likely false positives (image-referencing card with a real attached image)")
    print(f"cleaned report: {cleaned_path}")
    if dropped:
        print("\ndropped lines (for audit — re-add manually if any of these look wrong):")
        for l in dropped:
            print(f"  {l}")


if __name__ == "__main__":
    main()
