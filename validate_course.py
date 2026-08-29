#!/usr/bin/env python3
"""
Validates a course folder against the rules this repo's README/AUTHORING.md
document, and that Yaaddi's own importer enforces — catches the mistakes a
CSV file can't catch on its own: dangling references, missing media, an
exercise with no main card, a too-long prompt, a duplicate card, an
orphaned deck with no cards, low explanation coverage, a main card whose
practice cards are all one type or itself true_false, a course leaning on
too few of the available card types (see KNOWN_TYPES), a course with too
much typing overall, a missing or
duplicate course id, an image (cover or card art) larger than
MAX_IMAGE_DIMENSION, and a course with no narrated (media_card) cards at
all — before you open a PR or import into the app.

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
import struct
import sys
import zipfile

KNOWN_TYPES = {
    "multiple_choice", "true_false", "order", "select_blank", "multi_select",
    "match_pairs", "image_choice", "type_answer", "code_fill", "media_card",
    "image_occlusion", "numeric_answer", "command_output", "short_answer",
    "preview_card", "categorize", "spot_error", "listening_card",
    "speech_recognition", "reading_passage", "cloze_passage",
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

# Card art is generated at 256x256 (generate_asset.py's default) and shown
# at small sizes throughout the app — anything larger is wasted bytes
# bundled into every course zip for no visible benefit.
MAX_IMAGE_DIMENSION = 256

# The course cover is a deliberate exception: it fills a wide 2.4:1
# marketplace banner slot (MarketplaceScreen.tsx's cardImage style), so it's
# intentionally generated at 1024x432, not square — see
# reference_image_tts_generator / project_cardale_cover_image_aspect_ratio
# in the app repo's own session memory for why. A flat 256x256 cap would
# flag every correctly-generated cover as an error.
MAX_COVER_DIMENSION = (1024, 432)


def _image_dimensions(path):
    """Reads width/height straight from a PNG or JPEG header, no dependency
    beyond the standard library. Returns None if the file isn't a
    recognized image or is too short to contain a valid header."""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                if len(head) < 24:
                    return None
                width, height = struct.unpack(">II", head[16:24])
                return width, height
            if head[:2] == b"\xff\xd8":
                # JPEG: scan markers for the first Start-Of-Frame segment,
                # which carries the actual pixel dimensions.
                f.seek(2)
                while True:
                    marker_prefix = f.read(1)
                    if not marker_prefix:
                        return None
                    if marker_prefix != b"\xff":
                        continue
                    marker = f.read(1)
                    while marker == b"\xff":
                        marker = f.read(1)
                    if not marker:
                        return None
                    marker_byte = marker[0]
                    if marker_byte in (0xD8, 0xD9) or 0xD0 <= marker_byte <= 0xD7:
                        continue
                    seg_len_bytes = f.read(2)
                    if len(seg_len_bytes) < 2:
                        return None
                    seg_len = struct.unpack(">H", seg_len_bytes)[0]
                    if 0xC0 <= marker_byte <= 0xCF and marker_byte not in (0xC4, 0xC8, 0xCC):
                        sof = f.read(5)
                        if len(sof) < 5:
                            return None
                        height, width = struct.unpack(">HH", sof[1:5])
                        return width, height
                    f.seek(seg_len - 2, io.SEEK_CUR)
            return None
    except OSError:
        return None


def _check_image_size(path, label, report, max_width=MAX_IMAGE_DIMENSION, max_height=None):
    """max_height defaults to max_width (a square cap); pass both explicitly
    for a non-square cap like the cover image's 1024x432 banner slot."""
    if max_height is None:
        max_height = max_width
    dims = _image_dimensions(path)
    if dims is None:
        return
    width, height = dims
    if width > max_width or height > max_height:
        report.error(
            f"{label} is {width}x{height}, larger than the "
            f"{max_width}x{max_height} limit — regenerate it at the right size"
        )


def _word_count(text):
    return len((text or "").split())


def _slugify(text):
    """Same normalization the app's own lib/slugify.ts uses: lowercase,
    non-alphanumerics collapsed to single hyphens, trimmed."""
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
    """True if course_id reads as a slugified version of reference_text (a
    title or folder name) — the heuristic behind the id-neutrality warning.
    An opaque id (UUID fragment, timestamp token) won't match; a
    slugified-title id will, since slugifying it again reproduces course_id."""
    reference_slug = _slugify(reference_text)
    if not reference_slug:
        return False
    normalized_id = course_id.strip().lower()
    return normalized_id == reference_slug or normalized_id == reference_slug.replace("-", "")


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
    # name). Hard error: every course in this repo has had one assigned
    # since T#154, so a missing id from here on is a real authoring mistake,
    # not a legacy gap to tolerate. Run `python ensure_course_ids.py` to
    # assign one. Uniqueness across courses is checked separately, in
    # `check_id_uniqueness` (only meaningful with --all).
    course_id = (meta.get("id") or "").strip()
    if not course_id:
        report.error(
            'meta.json has no "id" — course identity currently falls back to this folder\'s '
            'name, which breaks "check for updates" for existing installs if the folder is ever '
            "renamed. Run `python ensure_course_ids.py` to assign one."
        )
    elif _looks_like_slug(course_id, meta.get("title") or "") or _looks_like_slug(
        course_id, os.path.basename(course_dir)
    ):
        report.warn(
            f'meta.json "id" ("{course_id}") looks derived from the current title/folder name — '
            "ids must stay neutral and stable even after a retitle or rename, or \"check for "
            'updates\" silently breaks for existing installs. Prefer an opaque token (e.g. a UUID '
            "fragment) instead of a slugified name."
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
        else:
            _check_image_size(
                image_path,
                f'meta.json "image" ("{image}")',
                report,
                max_width=MAX_COVER_DIMENSION[0],
                max_height=MAX_COVER_DIMENSION[1],
            )

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
        if not prompt and ctype != "listening_card":
            report.error(f"card {cid}: empty prompt")
        elif ctype == "preview_card":
            # preview_card's "prompt" column holds teaching prose (the
            # `concept`), not a quiz question — the atomicity word-count
            # rule below is aimed at prompts a learner must parse under
            # time pressure and doesn't apply here.
            pass
        elif ctype == "reading_passage":
            # reading_passage's "prompt" column holds the passage itself —
            # a longer text, dialogue, or short story — which is deliberately
            # over the atomicity word cap by design, not a sign of a
            # bloated quiz question. The actual comprehension question is
            # options[0] (see the CSV format doc comment near KNOWN_TYPES),
            # which is checked for length below instead.
            options_raw = (c.get("options") or "").strip()
            option_list = [o for o in options_raw.split("|")] if options_raw else []
            question = option_list[0] if option_list else ""
            if _word_count(question) >= MAX_PROMPT_WORDS:
                report.error(
                    f"card {cid}: reading_passage's comprehension question "
                    f"(options[0]) is {_word_count(question)} words — limit is "
                    f"{MAX_PROMPT_WORDS - 1}."
                )
        elif ctype == "cloze_passage":
            # Same reasoning as reading_passage: the passage itself is
            # deliberately long. Unlike reading_passage there's no separate
            # short "question" text to check either — the whole point is
            # blanks in a longer passage — so this is a full exemption, not
            # a check on a different field.
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

            # A multiple_choice/multi_select card where EVERY listed option
            # is marked correct has no genuine wrong answer to discriminate
            # against — it can't actually be graded (a multi_select where
            # you must tap everything on screen isn't a real judgment call).
            # That "list all N members, nothing false among them" shape
            # belongs in a preview card (always-correct by design), not a
            # graded main/exercise card. Only applies to types that use
            # options as genuinely parallel choices — see CHOICE_LIST_TYPES.
            if ctype in ("multiple_choice", "multi_select") and len(option_list) > 1:
                correct_raw = (c.get("correct_index") or "").strip()
                if correct_raw:
                    try:
                        correct_indices = {int(x) for x in correct_raw.split("|") if x.strip() != ""}
                    except ValueError:
                        correct_indices = set()
                    if correct_indices and correct_indices == set(range(len(option_list))):
                        report.error(
                            f"card {cid}: every option is marked correct (correct_index "
                            f'"{correct_raw}" covers all {len(option_list)} options) — there is '
                            "no genuine wrong answer to grade against. Move this \"list all "
                            "of them\" content into a preview card instead, or add a real "
                            "distractor option."
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
            # speech_recognition/listening_card are exempt here too, same
            # reasoning as the in-pack identical-question check above:
            # repeating a production/listening prompt verbatim across
            # unrelated cards is genuine, intentional spaced repetition of
            # the same phrase, not a copy-paste accident.
            if ctype not in ("speech_recognition", "listening_card"):
                normalized = " ".join(prompt.lower().split()) + "||" + (c.get("options") or "").strip().lower()
                if normalized in prompt_seen_at:
                    report.warn(
                        f'card {cid}: prompt+options are a near-exact duplicate of card {prompt_seen_at[normalized]}'
                    )
                else:
                    prompt_seen_at[normalized] = cid

        if c.get("audio") and ctype not in ("media_card", "listening_card"):
            report.error(
                f'card {cid}: "audio" is set but type is "{ctype}" — audio only works on '
                "media_card or listening_card"
            )
        if ctype == "listening_card" and not c.get("audio"):
            report.error(f'card {cid}: listening_card needs "audio" set — it has no visible text.')

        if role == "main":
            # A main card is the one graded encounter that actually schedules
            # spaced repetition — true_false is a 50/50 guess, which lets a
            # learner "pass" it without knowing the material. Reserve
            # true_false for practice/exercise cards, where a guessable
            # answer is lower-stakes reinforcement, not the real test.
            if ctype == "true_false":
                report.error(
                    f'main card {cid}: type is "true_false" — a main card must not be '
                    "true_false (a 50/50 guess undermines grading it); use a different type "
                    "and reserve true_false for practice cards"
                )
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

    previews_by_main = {}
    for p in previews:
        rid = p.get("related_main_id")
        if rid and rid not in mains_by_id:
            report.error(
                f'card {p.get("id")}: related_main_id "{rid}" does not point to a main card'
            )
        elif rid:
            previews_by_main.setdefault(rid, []).append(p.get("id"))

    for mid in mains_by_id:
        n = exercise_count_by_main.get(mid, 0)
        # Strict per-pack rule: every main card needs a paired preview card
        # and at least 5 practice cards (see the "pack" requirements in
        # docs/CARD_AUTHORING.md) — this is a hard error, not a guideline.
        if mid not in previews_by_main:
            report.error(f"main card {mid} has no preview card — every pack needs exactly one")
        elif len(previews_by_main[mid]) > 1:
            report.error(
                f"main card {mid} has {len(previews_by_main[mid])} preview cards "
                f"({', '.join(previews_by_main[mid])}) — a pack needs exactly one"
            )
        if n < 3:
            report.error(f"main card {mid} has only {n} practice card(s) — a pack needs at least 3")
        # A soft variety nudge, not an error — 5+ practice cards all sharing
        # one type usually means a card type was picked out of habit rather
        # than fit; occasionally a topic genuinely only fits one type well,
        # so this warns rather than blocks.
        if n >= 5 and len(exercise_types_by_main.get(mid, set())) == 1:
            only_type = next(iter(exercise_types_by_main[mid]))
            report.warn(
                f'main card {mid}: all {n} practice cards are "{only_type}" — '
                "consider mixing in another type for variety"
            )

        # A pack's practice cards are supposed to "attack the same concept
        # from a different angle" (see AUTHORING.md) — asking the literal
        # identical question twice with only the wrong-answer set changed
        # (e.g. "Hello یعنی چی؟" three times, each with different
        # distractors) isn't a different angle, it's the same test with
        # cosmetic variation. Repetition of a *production* prompt
        # (speech_recognition/listening_card — genuinely re-saying/re-
        # hearing the same phrase) is fine and excluded here, as are
        # reading_passage and cloze_passage: their "prompt" is the shared
        # passage text itself — several genuinely different comprehension
        # questions (or different blank sets) about the same passage are
        # supposed to repeat it (what actually varies lives in options, not
        # prompt). The preview
        # card is part of this same scope too — a preview that's a verbatim
        # copy of its own main card (same type, same prompt) isn't a
        # preview at all, just the same question asked twice in a row.
        pack_ids = (
            {mid}
            | {e.get("id") for e in exercises if e.get("related_main_id") == mid}
            | set(previews_by_main.get(mid, []))
        )
        prompt_type_counts = {}
        for c in cards:
            if c.get("id") not in pack_ids:
                continue
            ctype = c.get("type") or "multiple_choice"
            if ctype in ("speech_recognition", "listening_card", "reading_passage", "cloze_passage"):
                continue
            prompt = (c.get("prompt") or "").strip()
            if not prompt:
                continue
            key = (ctype, prompt)
            prompt_type_counts[key] = prompt_type_counts.get(key, 0) + 1
        for (ctype, prompt), count in prompt_type_counts.items():
            if count > 1:
                report.error(
                    f'main card {mid}: {count} cards ask the identical "{ctype}" question '
                    f'"{prompt}" — vary the question itself, not just the wrong answers, '
                    "or use a different card type for that practice angle"
                )

    # Course-wide type variety: catches a whole course leaning on 1-2 types
    # out of the 16 available, which the per-deck check above can miss if
    # each individual deck looks varied but the course as a whole doesn't.
    all_types_used = {c.get("type") or "multiple_choice" for c in cards}
    if len(cards) >= 20 and len(all_types_used) < 5:
        report.warn(
            f"this course only uses {len(all_types_used)} card type(s) "
            f"({', '.join(sorted(all_types_used))}) across {len(cards)} cards — "
            f"{len(KNOWN_TYPES)} types are available; consider mixing in more for variety"
        )

    # Type BALANCE, distinct from type COUNT above: a course can use 8 of
    # the 16 types and still have 80% of its cards be multiple_choice — the
    # check above wouldn't catch that. preview_card is excluded here since
    # its count is structurally fixed (one per pack, not a stylistic
    # choice), which would otherwise mechanically distort the "share"
    # figure for every course. Threshold is deliberately loose (55%, not an
    # even 1/N split) — some skew toward the most learner-friendly types
    # (multiple_choice, true_false) is normal and fine; this only flags a
    # genuine over-reliance on one format.
    MAX_SINGLE_TYPE_SHARE = 0.55
    gradeable_cards = [c for c in cards if (c.get("type") or "multiple_choice") != "preview_card"]
    if len(gradeable_cards) >= 20:
        type_counts = {}
        for c in gradeable_cards:
            t = c.get("type") or "multiple_choice"
            type_counts[t] = type_counts.get(t, 0) + 1
        dominant_type, dominant_count = max(type_counts.items(), key=lambda kv: kv[1])
        dominant_share = dominant_count / len(gradeable_cards)
        if dominant_share > MAX_SINGLE_TYPE_SHARE:
            report.warn(
                f'"{dominant_type}" makes up {dominant_count}/{len(gradeable_cards)} '
                f"({round(100 * dominant_share)}%) of this course's gradeable cards — "
                f"consider rebalancing so no single type is over {round(100 * MAX_SINGLE_TYPE_SHARE)}%"
            )

    # Typing (type_answer, numeric_answer, code_fill, command_output,
    # short_answer) is slower and more error-prone to grade than tapping —
    # capped at 10% of a course's cards so review stays quick (see
    # AUTHORING.md's "typing budget" section).
    if cards:
        def _requires_typing(c):
            card_type = c.get("type") or "multiple_choice"
            if card_type in TYPING_TYPES:
                return True
            # listening_card only requires typing for its own
            # response_type: "type" variant (not "select"/"order") — see
            # this file's KNOWN_TYPES doc comment and the app's own
            # src/domain/cardTypeMix.ts, which makes the identical
            # content-aware distinction.
            if card_type == "listening_card":
                response_type = (c.get("options") or "").split("|", 1)[0].strip()
                return response_type == "type"
            return False

        typing_count = sum(1 for c in cards if _requires_typing(c))
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
    if len(cards) >= 20 and not any(
        (c.get("type") or "") in ("media_card", "listening_card") for c in cards
    ):
        report.warn(
            "no media_card or listening_card cards found in this course — nothing in it "
            "has any real recorded audio (a teachesLanguage course's own auto-played TTS "
            "doesn't count as authored narration)"
        )

    # An orphaned deck (no card at all references it) usually means a deck
    # was added to units.csv and then forgotten during card-writing, not a
    # deliberate empty deck — empty decks aren't a real use case here.
    for u in units:
        uid = u.get("id")
        if uid not in units_with_cards:
            report.warn(f'unit {uid} ("{u.get("title")}"): has no cards at all')
        if not (u.get("image") or "").strip():
            report.error(f'unit {uid} ("{u.get("title")}"): has no "image" set — every deck needs one')

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
            # Both the bare basename (flat files like "unit1.png") and the
            # full in-zip path (subfolder-qualified refs like
            # "cards/card_12.png", matching the raw CSV value exactly, per
            # csvZipImport.ts's own root-then-images/-then-media/ lookup)
            # need to be recognized as "in the archive".
            media_files = {os.path.basename(n) for n in names} | set(names)

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

            glossary_text = read("glossary.csv")
            if glossary_text is not None:
                validate_glossary_rows(read_csv_text(glossary_text), report)
    except zipfile.BadZipFile:
        report.error(f'"{meta["file"]}" is not a valid zip file')


def validate_glossary(source_dir, report):
    """Checks source/glossary.csv, if the course has one — see docs/GLOSSARY.md
    in the app repo for the feature this feeds (tap-to-define technical terms,
    one shared definition per term instead of duplicating it into every card).
    Entirely optional: a course with no jargon-heavy content can ship none."""
    glossary_path = os.path.join(source_dir, "glossary.csv")
    if not os.path.isfile(glossary_path):
        return
    with open(glossary_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    validate_glossary_rows(rows, report)


def validate_glossary_rows(rows, report):
    seen_terms = {}
    for i, row in enumerate(rows, start=1):
        term = (row.get("term") or "").strip()
        definition = (row.get("definition") or "").strip()
        link = (row.get("link") or "").strip()
        if not term:
            report.error(f"glossary.csv row {i}: \"term\" is required.")
            continue
        if not definition:
            report.error(f'glossary.csv row {i} ("{term}"): "definition" is required.')
        key = term.lower()
        if key in seen_terms:
            report.error(
                f'glossary.csv row {i}: term "{term}" is a duplicate of row '
                f"{seen_terms[key]} — every term should appear once."
            )
        else:
            seen_terms[key] = i
        if link and not (link.startswith("http://") or link.startswith("https://")):
            report.warn(
                f'glossary.csv row {i} ("{term}"): "link" doesn\'t look like a URL '
                f'("{link}") — should be a full http(s):// address or left blank.'
            )
        # A learner reads the definition standalone, same self-containment
        # bar as a card — a definition that's just the term restated with a
        # capital letter isn't actually explaining anything.
        if definition and definition.rstrip(".").lower() == term.lower():
            report.warn(
                f'glossary.csv row {i} ("{term}"): definition just restates the term '
                "— write a real explanation."
            )


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
        if not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            rel_root = os.path.relpath(root, d)
            for fn in files:
                available.add(fn)
                if rel_root != ".":
                    # e.g. "cards/card_12.png" for a file organized in a
                    # subfolder (card-level images live under images/cards/
                    # to stay separate from deck-level images/unit*.png) —
                    # a bare os.listdir() only saw the top-level "cards"
                    # directory name, never the files inside it.
                    available.add((rel_root + "/" + fn).replace(os.sep, "/"))
                # "cover" images (course-cover.png etc.) are the source copy
                # behind meta.json's own "image" field, checked separately
                # above against MAX_COVER_DIMENSION — they intentionally
                # aren't square and would false-positive here.
                if d is images_dir and "cover" not in fn.lower():
                    _check_image_size(
                        os.path.join(root, fn),
                        f"source/images/{os.path.relpath(os.path.join(root, fn), images_dir).replace(os.sep, '/')}",
                        report,
                    )

    validate_cards(units, cards, report, media_files=available)

    validate_glossary(source_dir, report)

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


def check_catalog_freshness(repo_root):
    """catalog.json (tools/build_catalog.py) is the single-file course index
    the app fetches for a fast Course Library load — see that script's own
    doc comment. CI regenerates and auto-commits it on every push to main,
    but that auto-commit can't push on a pull_request from a fork
    (GITHUB_TOKEN is read-only there), so a fork PR that adds/edits a
    course would otherwise merge with a silently stale catalog.json and no
    warning. This regenerates it in-memory and diffs against what's
    actually committed, catching that case at PR-review time instead."""
    report = Report("catalog.json")
    tools_dir = os.path.join(repo_root, "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import build_catalog  # noqa: E402 (deliberately imported late — needs sys.path set first)

    committed_path = os.path.join(repo_root, "catalog.json")
    if not os.path.isfile(committed_path):
        report.error(
            "catalog.json is missing from the repo root — run `python tools/build_catalog.py` "
            "and commit the result (CI does this automatically on push to main, but not on a fork PR)"
        )
        return report

    try:
        committed = json.loads(open(committed_path, encoding="utf-8").read())
    except json.JSONDecodeError as e:
        report.error(f"catalog.json is not valid JSON: {e}")
        return report

    fresh = build_catalog.build_catalog(build_catalog.Path(repo_root))
    if committed != fresh:
        report.error(
            "catalog.json is out of date with the actual course folders — run "
            "`python tools/build_catalog.py` and commit the result (CI does this automatically "
            "on push to main, but not on a fork PR)"
        )
    return report


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

    catalog_report = None
    if args.all:
        for entry in sorted(os.listdir(repo_root)):
            full = os.path.join(repo_root, entry)
            if os.path.isdir(full) and os.path.isfile(os.path.join(full, "meta.json")):
                results.append(validate_course_folder(full, check_source=args.source))
        check_id_uniqueness(results)
        catalog_report = check_catalog_freshness(repo_root)
    elif args.course:
        results.append(validate_course_folder(args.course, check_source=args.source))
    else:
        parser.print_help()
        sys.exit(1)

    reports = [r for r, _meta in results]
    if catalog_report is not None:
        reports.append(catalog_report)
    for r in reports:
        r.print()

    failed = [r for r in reports if not r.ok()]
    print(f"\n{len(reports)} course(s) checked, {len(failed)} failed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
