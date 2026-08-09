#!/usr/bin/env python3
"""
Validates a course folder against the rules this repo's README/AUTHORING.md
document, and that Yaaddi's own importer enforces — catches the mistakes a
CSV file can't catch on its own: dangling references, missing media, an
exercise with no main card, a too-long prompt, a duplicate card, an
orphaned deck with no cards, low explanation coverage, a main card whose
practice cards are all one type, a course leaning on too few of the 14
card types, a course with too much typing overall, and a course with no
narrated (media_card) cards at all — before you open a PR or import into
the app.

No dependencies beyond the standard library.

Usage:
    python validate_course.py <course-folder>            # one course, meta.json checks only
    python validate_course.py <course-folder> --source    # also check source/*.csv directly
    python validate_course.py --all --source              # every course at the repo root

A course folder is expected to look like:
    <name>/
      meta.json
      cover.png            (whatever meta.json's "image" points to)
      source/               (the actual course content — units.csv, cards.csv,
                              meta.csv, images/, media/ — checked via --source)

meta.json's "file" field must point at a real, committed zip in the course's
own folder (see README.md's "Delivery mechanism" note) — a missing file is
a hard error, not a warning: the app fetches it directly from
raw.githubusercontent.com, so a course whose zip isn't actually there is
not installable, full stop.

Exit code is non-zero if any check fails.
"""

import argparse
import csv
import io
import json
import os
import sys
import zipfile

KNOWN_TYPES = {
    "multiple_choice", "true_false", "order", "select_blank", "multi_select",
    "match_pairs", "image_choice", "type_answer", "code_fill", "media_card",
    "image_occlusion", "numeric_answer", "command_output", "short_answer",
    "preview_card",
}

# Typing is slower and more error-prone than tapping, so courses are
# expected to keep it rare — must match `requiresTyping` in the app's own
# src/cardTypes/*.tsx definitions (see src/domain/cardTypeMix.ts).
TYPING_TYPES = {"type_answer", "numeric_answer", "code_fill", "command_output", "short_answer"}
MAX_TYPING_CARD_RATIO = 0.1

# Cards must be short enough to read at a glance: a prompt under 10 words,
# and — for choice-list card types, where "options" are genuinely parallel
# short answer choices — each option under 3 words. A card that can't fit a
# real fact into that shape should be split into more cards (a main plus
# more practice cards), not padded past the limit. The one escape hatch:
# a card whose prompt+options TOTAL is at or under 10 words passes even if
# an individual option runs to 3+ words, since a short prompt can "spend"
# its budget on the options instead (e.g. a one-word prompt with a
# two-and-a-half-word option). This replaces the older, softer
# character-length heuristic (docs/TASKS.md T50.x) with a hard rule.
MAX_PROMPT_WORDS = 10
MAX_OPTION_WORDS = 3
MAX_TOTAL_WORDS = 10

# Only these types hold genuinely parallel, human-read "pick one/some of
# these" choices in `options` — the per-option word check only makes sense
# for them. Other types repurpose the `options` column for structurally
# different data (match_pairs' `term=definition` pairs, order's ordered
# steps, code_fill/command_output's code-or-output text, numeric_answer's
# `value|tolerance|unit`, short_answer/type_answer's single accepted
# answer) where a "3 words per option" rule doesn't apply.
CHOICE_LIST_TYPES = {"multiple_choice", "multi_select", "image_choice", "select_blank"}


def _word_count(text):
    return len((text or "").split())


class Report:
    def __init__(self, label):
        self.label = label
        self.errors = []
        self.warnings = []
        self.infos = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def info(self, msg):
        self.infos.append(msg)

    def ok(self):
        return not self.errors

    def print(self):
        status = "OK" if self.ok() else "FAILED"
        print(f"\n=== {self.label}: {status} ===")
        for i in self.infos:
            print(f"  [info]  {i}")
        for e in self.errors:
            print(f"  [ERROR] {e}")
        for w in self.warnings:
            print(f"  [warn]  {w}")
        if not self.errors and not self.warnings:
            print("  no issues found")


def read_csv_text(text):
    return list(csv.DictReader(io.StringIO(text)))


def validate_meta_json(course_dir, report):
    meta_path = os.path.join(course_dir, "meta.json")
    if not os.path.isfile(meta_path):
        report.error("meta.json is missing")
        return None
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        report.error(f"meta.json is not valid JSON: {e}")
        return None

    # `or ""` guards against an explicit `"title": null` in the JSON, not just
    # a missing key — .get(key, "") only falls back to "" when the key is
    # absent, and still returns None (crashing the next .strip()) when it's
    # present but null.
    if not (meta.get("title") or "").strip():
        report.error('meta.json "title" is required and must be non-empty')

    # A course's stable identity — distinct from the folder it currently
    # lives in. Without it, renaming this folder later silently breaks
    # "check for updates" for everyone who already installed it (the app
    # has no other way to recognize this is the same course under a new
    # name). Warn, not error, so older un-migrated courses still validate —
    # run `python ensure_course_ids.py` to auto-assign one.
    course_id = (meta.get("id") or "").strip()
    if not course_id:
        report.warn(
            'meta.json has no "id" — course identity currently falls back to this folder\'s '
            'name, which breaks "check for updates" for existing installs if the folder is ever '
            "renamed. Run `python ensure_course_ids.py` to assign one."
        )
    file_name = meta.get("file") or ""
    if not file_name.strip():
        report.error('meta.json "file" is required')
    else:
        file_path = os.path.join(course_dir, file_name)
        if not os.path.isfile(file_path):
            report.error(
                f'meta.json "file" points to "{file_name}", which doesn\'t exist — '
                "run build_course_zip.py and commit the result before publishing"
            )

    image = meta.get("image")
    if image:
        image_path = os.path.join(course_dir, image)
        if not os.path.isfile(image_path):
            report.error(f'meta.json "image" points to "{image}", which doesn\'t exist')

    return meta


def validate_cards(units, cards, report, media_files=None):
    """media_files: set of filenames available to reference (image/audio), or
    None to skip the file-existence check (e.g. when validating raw source/
    CSVs where images/media aren't co-located the same way)."""
    unit_ids = set()
    for u in units:
        uid = u.get("id")
        if uid in unit_ids:
            report.error(f'units.csv: duplicate unit id "{uid}"')
        unit_ids.add(uid)

    card_ids = set()
    mains_by_id = {}
    exercises = []
    previews = []
    units_with_cards = set()
    prompt_seen_at = {}  # normalized prompt -> first card id that used it
    cards_with_explanation = 0
    for c in cards:
        cid = c.get("id")
        if cid in card_ids:
            report.error(f'cards.csv: duplicate card id "{cid}"')
        card_ids.add(cid)
        units_with_cards.add(c.get("unit_id"))
        if (c.get("explanation") or "").strip():
            cards_with_explanation += 1

        ctype = c.get("type") or "multiple_choice"
        if ctype not in KNOWN_TYPES:
            report.error(f'card {cid}: unknown type "{ctype}"')

        role = c.get("role")
        if role not in ("main", "exercise", "preview"):
            report.error(f'card {cid}: role must be "main", "exercise", or "preview", got "{role}"')

        uid = c.get("unit_id")
        if uid not in unit_ids:
            report.error(f'card {cid}: unit_id "{uid}" does not match any row in units.csv')

        prompt = (c.get("prompt") or "").strip()
        if not prompt:
            report.error(f"card {cid}: empty prompt")
        elif ctype == "preview_card":
            # preview_card's "prompt" column holds teaching prose (the
            # `concept`), not a quiz question — the atomicity word-count
            # rule below is aimed at prompts a learner must parse under
            # time pressure and doesn't apply here.
            pass
        else:
            options_raw = (c.get("options") or "").strip()
            option_list = [o for o in options_raw.split("|")] if options_raw else []
            prompt_words = _word_count(prompt)
            option_word_counts = [_word_count(o) for o in option_list]
            total_words = prompt_words + sum(option_word_counts)

            prompt_ok = prompt_words < MAX_PROMPT_WORDS
            if ctype in CHOICE_LIST_TYPES:
                options_ok = all(w < MAX_OPTION_WORDS for w in option_word_counts)
            else:
                options_ok = True
            fits_total = total_words <= MAX_TOTAL_WORDS

            if not (prompt_ok and options_ok) and not fits_total:
                if not prompt_ok and ctype in CHOICE_LIST_TYPES and not options_ok:
                    report.error(
                        f"card {cid}: prompt is {prompt_words} words (limit {MAX_PROMPT_WORDS}) "
                        f"and has an option over {MAX_OPTION_WORDS} words — split into more "
                        "cards, or shorten so prompt+options together are "
                        f"{MAX_TOTAL_WORDS} words or fewer"
                    )
                elif not prompt_ok:
                    report.error(
                        f"card {cid}: prompt is {prompt_words} words — limit is "
                        f"{MAX_PROMPT_WORDS - 1}, or {MAX_TOTAL_WORDS} words total "
                        "including options. Split into more cards instead of padding one."
                    )
                else:
                    long_options = [
                        o for o, w in zip(option_list, option_word_counts) if w >= MAX_OPTION_WORDS
                    ]
                    report.error(
                        f"card {cid}: option(s) over {MAX_OPTION_WORDS - 1} words: "
                        f"{', '.join(long_options)} — limit is {MAX_OPTION_WORDS - 1} words "
                        f"per option, or {MAX_TOTAL_WORDS} words total including the prompt"
                    )

            # A soft, deliberately imprecise heuristic for "this prompt is
            # probably testing more than one fact" — true atomicity can't be
            # mechanically verified, so this nudges rather than blocks.
            # More than one "?" is the cheapest, least-false-positive-prone
            # signal available without actually understanding the content —
            # a prompt like "Match each term and its definition" (legitimate
            # for match_pairs) would false-positive on an "and"-based check,
            # so that idea was deliberately not implemented.
            if prompt.count("?") > 1:
                report.warn(f'card {cid}: prompt has more than one "?" — likely testing more than one fact, consider splitting into separate cards')

            # Exact-duplicate-after-normalizing catches accidental copy-paste
            # cards (a real, easy mistake with a scratch script appending
            # rows) — deliberately not fuzzy-matched, since near-duplicates
            # are often legitimate (e.g. the same statement asked true vs.
            # false in two different true_false cards). Keys on prompt +
            # options together, not prompt alone: several card types
            # (command_output's "What does this print?", code_fill's
            # "Complete the ___") legitimately reuse the exact same short
            # prompt across many cards whose real content lives in
            # `options` — comparing prompt alone flagged dozens of false
            # positives on real courses before this was caught.
            normalized = " ".join(prompt.lower().split()) + "||" + (c.get("options") or "").strip().lower()
            if normalized in prompt_seen_at:
                report.warn(
                    f'card {cid}: prompt+options are a near-exact duplicate of card {prompt_seen_at[normalized]}'
                )
            else:
                prompt_seen_at[normalized] = cid

        if c.get("audio") and ctype != "media_card":
            report.error(f'card {cid}: "audio" is set but type is "{ctype}" — audio only works on media_card')

        if role == "main":
            mains_by_id[cid] = c
        elif role == "exercise":
            if not (c.get("related_main_id") or "").strip():
                report.error(f"card {cid}: exercise card has no related_main_id")
            exercises.append(c)
        elif role == "preview":
            if not (c.get("related_main_id") or "").strip():
                report.error(f"card {cid}: preview card has no related_main_id")
            previews.append(c)

        if media_files is not None:
            for col in ("image", "audio"):
                fn = c.get(col)
                if fn and fn not in media_files:
                    report.error(f'card {cid}: {col} "{fn}" is not in the archive')

    # Cross-reference exercises -> mains, and count coverage.
    exercise_count_by_main = {}
    exercise_types_by_main = {}
    for e in exercises:
        rid = e.get("related_main_id")
        if rid and rid not in mains_by_id:
            report.error(
                f'card {e.get("id")}: related_main_id "{rid}" does not point to a main card'
            )
        else:
            exercise_count_by_main[rid] = exercise_count_by_main.get(rid, 0) + 1
            exercise_types_by_main.setdefault(rid, set()).add(e.get("type") or "multiple_choice")

    for p in previews:
        rid = p.get("related_main_id")
        if rid and rid not in mains_by_id:
            report.error(
                f'card {p.get("id")}: related_main_id "{rid}" does not point to a main card'
            )

    for mid in mains_by_id:
        n = exercise_count_by_main.get(mid, 0)
        if n == 0:
            report.warn(f"main card {mid} has zero practice cards")
        elif n < 5:
            report.warn(f"main card {mid} has only {n} practice card(s) — this project's guideline is 5-10")
        # A soft variety nudge, not an error — 5+ practice cards all sharing
        # one type usually means a card type was picked out of habit rather
        # than fit; occasionally a topic genuinely only fits one type well,
        # so this warns rather than blocks.
        elif n >= 5 and len(exercise_types_by_main.get(mid, set())) == 1:
            only_type = next(iter(exercise_types_by_main[mid]))
            report.warn(
                f'main card {mid}: all {n} practice cards are "{only_type}" — '
                "consider mixing in another type for variety"
            )

    # Course-wide type variety: catches a whole course leaning on 1-2 types
    # out of the 14 available, which the per-deck check above can miss if
    # each individual deck looks varied but the course as a whole doesn't.
    all_types_used = {c.get("type") or "multiple_choice" for c in cards}
    if len(cards) >= 20 and len(all_types_used) < 5:
        report.warn(
            f"this course only uses {len(all_types_used)} card type(s) "
            f"({', '.join(sorted(all_types_used))}) across {len(cards)} cards — "
            "14 types are available; consider mixing in more for variety"
        )

    # Typing (type_answer, numeric_answer, code_fill, command_output,
    # short_answer) is slower and more error-prone to grade than tapping —
    # capped at 10% of a course's cards so review stays quick (see
    # AUTHORING.md's "typing budget" section).
    if cards:
        typing_count = sum(1 for c in cards if (c.get("type") or "multiple_choice") in TYPING_TYPES)
        typing_ratio = typing_count / len(cards)
        if typing_ratio > MAX_TYPING_CARD_RATIO:
            report.warn(
                f"{typing_count}/{len(cards)} cards ({round(100 * typing_ratio)}%) require typing — "
                f"consider trimming below {round(100 * MAX_TYPING_CARD_RATIO)}% so review stays quick to tap through"
            )

    # Audio only ever lives on media_card (see AUTHORING.md's "Audio"
    # section) — a course introducing real terminology with zero media_card
    # cards means nothing in it has ever been narrated. This can't detect
    # "does every technical term specifically have audio" (that needs a
    # human judgment call on what counts as a new term), but a total-zero
    # count is a reliable, cheap signal that audio was skipped entirely.
    if len(cards) >= 20 and not any((c.get("type") or "") == "media_card" for c in cards):
        report.warn(
            "no media_card cards found in this course — only media_card carries audio, "
            "so nothing in this course has narration for a learner who prefers listening"
        )

    # An orphaned deck (no card at all references it) usually means a deck
    # was added to units.csv and then forgotten during card-writing, not a
    # deliberate empty deck — empty decks aren't a real use case here.
    for u in units:
        uid = u.get("id")
        if uid not in units_with_cards:
            report.warn(f'unit {uid} ("{u.get("title")}"): has no cards at all')

    # Explanations are optional per-card, but a course where almost none of
    # its cards have one is a course that never uses the one place a wrong
    # answer gets a chance to actually teach something. An aggregate warning
    # (not one per card) — with explanations this rare across every existing
    # course, a per-card version would be pure noise, not a useful nudge.
    if len(cards) >= 20 and cards_with_explanation / len(cards) < 0.15:
        pct = round(100 * cards_with_explanation / len(cards))
        report.warn(
            f"only {cards_with_explanation}/{len(cards)} cards ({pct}%) have an explanation — "
            "consider adding one wherever a wrong answer wouldn't be obvious why it's wrong"
        )

    if media_files is not None:
        for u in units:
            for col in ("image", "section_image"):
                fn = u.get(col)
                if fn and fn not in media_files:
                    report.error(f'unit {u.get("id")}: {col} "{fn}" is not in the archive')


def validate_zip(course_dir, meta, report):
    # Validates the actual committed <slug>.zip every course ships (see
    # README.md's "Delivery mechanism" note) — this is the real artifact
    # the app downloads and imports, so it gets the same card/media checks
    # as --source, not just a file-exists check.
    if not meta or not meta.get("file"):
        return
    zip_path = os.path.join(course_dir, meta["file"])
    if not zip_path.endswith(".zip") or not os.path.isfile(zip_path):
        return  # already reported missing by validate_meta_json — nothing more to check here

    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            media_files = {os.path.basename(n) for n in names}

            def read(fn):
                candidates = [n for n in names if os.path.basename(n) == fn]
                if not candidates:
                    return None
                return zf.read(candidates[0]).decode("utf-8-sig")

            units_text = read("units.csv")
            cards_text = read("cards.csv")
            if units_text is None:
                report.error("units.csv not found inside the zip")
            if cards_text is None:
                report.error("cards.csv not found inside the zip")
            if units_text is not None and cards_text is not None:
                units = read_csv_text(units_text)
                cards = read_csv_text(cards_text)
                report.info(f"{len(units)} units, {len(cards)} cards")
                validate_cards(units, cards, report, media_files=media_files)
    except zipfile.BadZipFile:
        report.error(f'"{meta["file"]}" is not a valid zip file')


def validate_source(course_dir, report, meta=None):
    """Validates course-drafts/<name>/source/{units,cards}.csv directly, if present —
    lets you check your working CSVs before rebuilding the zip."""
    source_dir = os.path.join(course_dir, "source")
    units_path = os.path.join(source_dir, "units.csv")
    cards_path = os.path.join(source_dir, "cards.csv")
    if not os.path.isfile(units_path) or not os.path.isfile(cards_path):
        return
    with open(units_path, encoding="utf-8-sig") as f:
        units = list(csv.DictReader(f))
    with open(cards_path, encoding="utf-8-sig") as f:
        cards = list(csv.DictReader(f))

    images_dir = os.path.join(source_dir, "images")
    media_dir = os.path.join(source_dir, "media")
    available = set()
    for d in (images_dir, media_dir):
        if os.path.isdir(d):
            available.update(os.listdir(d))

    validate_cards(units, cards, report, media_files=available)

    # meta.json's optional "toc" is hand-copied from units.csv's title column
    # (see README.md) — nothing keeps them in sync automatically, so this is
    # the one place that catches a course whose deck list changed without
    # its preview being updated to match.
    if meta and meta.get("toc") is not None:
        actual_titles = [u.get("title", "") for u in units]
        if meta["toc"] != actual_titles:
            report.warn(
                f'meta.json "toc" ({len(meta["toc"])} entries) does not match '
                f'source/units.csv\'s title column ({len(actual_titles)} entries) — '
                "the Course Library preview may be stale"
            )


def validate_course_folder(course_dir, check_source=False):
    name = os.path.basename(os.path.normpath(course_dir))
    report = Report(name)
    meta = validate_meta_json(course_dir, report)
    validate_zip(course_dir, meta, report)
    if check_source:
        validate_source(course_dir, report, meta=meta)
    return report, meta


def check_id_uniqueness(reports_and_metas):
    """Cross-course check, only meaningful with --all: two courses sharing
    an "id" would make lib/courseUpdates.ts's rename-fallback lookup
    ambiguous (which course does the id actually belong to?) — this is a
    hard error, not a warning, since it silently breaks update-checking for
    both courses in a way an author is unlikely to notice on their own."""
    seen = {}
    for report, meta in reports_and_metas:
        course_id = ((meta or {}).get("id") or "").strip()
        if not course_id:
            continue
        if course_id in seen:
            report.error(f'meta.json "id" ("{course_id}") is also used by "{seen[course_id]}" — ids must be unique across the repo')
        else:
            seen[course_id] = report.label


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course", nargs="?", help="path to a single course folder")
    parser.add_argument("--all", action="store_true", help="validate every course folder at the repo root")
    parser.add_argument("--source", action="store_true", help="also validate source/*.csv directly, not just the built zip")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.abspath(__file__))
    results = []

    if args.all:
        for entry in sorted(os.listdir(repo_root)):
            full = os.path.join(repo_root, entry)
            if os.path.isdir(full) and os.path.isfile(os.path.join(full, "meta.json")):
                results.append(validate_course_folder(full, check_source=args.source))
        check_id_uniqueness(results)
    elif args.course:
        results.append(validate_course_folder(args.course, check_source=args.source))
    else:
        parser.print_help()
        sys.exit(1)

    reports = [r for r, _meta in results]
    for r in reports:
        r.print()

    failed = [r for r in reports if not r.ok()]
    print(f"\n{len(reports)} course(s) checked, {len(failed)} failed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
