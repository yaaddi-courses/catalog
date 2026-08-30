#!/usr/bin/env python3
"""Generates a base-language-framed language course's units.csv/cards.csv
from a simple vocabulary spreadsheet, following the exact pedagogy this
repo settled on for "English for Farsi Speakers" (see AUTHORING.md's
"Generating a language course from a vocabulary list" section and the
flashcard-course-creator skill's base-language-framing rules):

  - Every pack introduces exactly one new target-language item, in the
    order the input CSV lists it — that row order *is* the ledger.
  - Distractors for the "meaning" multiple_choice cards are always drawn
    from *already-emitted* rows' base-language glosses, never a raw
    target-language word — this sidesteps the whole class of "options
    mix scripts" bug by construction (a base-language gloss is always
    base-language, so an options list built only from glosses is always
    single-script).
  - `true_false` is used only for the preview card, never main/practice.
  - Every pack includes a `listening_card` production rep (audio-only
    comprehension — research on language-app design consistently flags
    listening practice as a distinct skill spaced-repetition-of-text-alone
    doesn't exercise; see AUTHORING.md's generator section for sources).
    Real audio has to be recorded/synthesized separately — this script
    only lays out the card and a `tts_manifest.csv` of what needs voicing,
    it does not call a TTS engine itself (this repo's own audio policy,
    see the app's CLAUDE.md, requires a real TTS pass, never a placeholder).
  - A row that supplies `example_sentence` gets sentence-practice cards —
    arrange it (`order`), say the whole thing aloud (`speech_recognition`),
    fill the new word back in from a blank (`select_blank`, only when it's
    short enough to be a legal option), and — every other sentence, when
    `example_gloss` is also given — PRODUCE the whole sentence unprompted
    from its meaning (`type_answer`): Duolingo's single most-used exercise
    across a whole course, and the one thing none of the other formats
    actually test (they test recognizing/hearing/arranging a sentence
    someone else wrote, not producing one from scratch). Emitted right
    after that row's own main/preview, ahead of every other practice card
    in the pack. This isn't an occasional bonus: supply a sentence on as
    many rows as you can, starting from the first one — real usage is the
    actual goal, not "can recognize this word in isolation," and isolated-
    word drilling for its own sake is exactly what the
    flashcard-course-creator skill's "don't teach isolated words forever"
    rule warns against. Deliberately author-supplied, not auto-composed:
    stitching two random taught words together does not reliably produce a
    grammatical sentence, and a language course shipping a broken example
    sentence is a real correctness bug, not a style nit.
  - Every 3rd row also gets a `type_answer` card — type the target word
    from its base-language meaning alone (spelling recall, no options to
    recognize from). Every row would push a course over
    validate_course.py's 10% typing-card budget; every 3rd keeps real
    spelling practice without turning review into a keyboard exercise.
  - No new card types — every pack uses `true_false`, `multiple_choice`,
    `match_pairs`, `listening_card`, `order`/`select_blank` (only when
    `example_sentence` is given), `type_answer`, and `speech_recognition`,
    all of which already exist in the Yaaddi app.

Input CSV columns: deck, target_word, target_type, base_gloss,
                    example_sentence (optional), example_gloss (optional)
  - deck              the deck/unit this item belongs to — rows are
                      grouped into one unit per distinct value, in
                      first-seen order
  - target_word       the word/phrase being taught (e.g. "Hello")
  - target_type       "word" or "phrase" — currently just documentation;
                      both are handled identically today
  - base_gloss        the short base-language meaning (e.g. "سلام") — kept
                      to one or two words so it fits this repo's
                      option-length budget (validate_course.py's
                      MAX_OPTION_WORDS)
  - example_sentence  fill this in for as many rows as you can, starting
                      from the very first one — one or more genuine
                      target-language sentences built ONLY from this row's
                      word and words from EARLIER rows (author's
                      responsibility to keep it real and ledger-safe). This
                      is what actually teaches usable language — leaving it
                      blank means that row is only ever tested as an
                      isolated word, so treat a row with no
                      example_sentence as the exception, not the default;
                      use real names/places where a sentence needs one
                      (e.g. an actual name for "My name is ___", an actual
                      city for "I'm from ___").
                        Two delimiter levels: "|" splits one sentence into
                      chips (a taught PHRASE stays one piece — "Hello,|My
                      name is", never split into "Hello,", "My", "name",
                      "is"), and ";;" splits MULTIPLE sentences from one
                      row — the substitution-drill mechanism (teach "You
                      are" against every adjective already taught: "You
                      are|Happy;;You are|Sad;;You are|Thirsty" from one
                      row). Only the FIRST sentence gets the full practice
                      treatment (arrange/speak/fill-in-blank/translate) —
                      every sentence after that only gets an `order` rep,
                      so a row listing several substitutions doesn't
                      multiply its whole pack size by however many it lists.
  - example_gloss     the sentence's base-language translation, used in the
                      practice card's explanation and as the prompt for the
                      "translate this sentence" card. Same ";;" convention
                      as example_sentence when there's more than one — must
                      have the same number of ";;"-separated entries (or
                      fewer; missing trailing ones are treated as blank).
                      Ignored entirely if example_sentence is blank.

Usage:
    python tools/generate_language_course.py <vocab.csv> <course-folder> \\
        [--seed 0] [--generate-images]

--generate-images additionally generates one 256x256 deck-cover image per
unit via this machine's local FLUX.1-schnell server (see the generate-image
skill / the "Image generator and tts" project), written to
source/images/deck<N>.png and filled into units.csv's own `image` column.
Off by default — needs that server running locally, and each image takes
roughly 1-2 minutes, one at a time (never concurrently). Safe to re-run: a
deck whose image file already exists on disk is skipped, not regenerated.

Writes <course-folder>/source/units.csv, source/cards.csv, and
source/tts_manifest.csv (overwriting any existing files there) — run
build_course_zip.py and validate_course.py --source afterwards, same as any
hand-authored course. Before that, record/synthesize every row in
tts_manifest.csv into source/media/<audio filename> — this repo's own TTS
tooling (see the app's CLAUDE.md's "narration/pronunciation audio" note) can
batch this the same way the original hand-authored course's audio was made.

Pure Python stdlib, matching this repo's other tools — --generate-images
talks to the local FLUX server over plain HTTP via urllib, no extra
dependency (e.g. `requests`) added just for this.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Local FLUX.1-schnell image server (see the `generate-image` skill / the
# "Image generator and tts" project's API_USAGE.md) — used only when
# --generate-images is passed. Never called concurrently: each request
# takes 1-2 minutes at 256x256 and the server has no request queue of its
# own, so cover images are generated one unit at a time, in sequence.
FLUX_HEALTH_URL = "http://127.0.0.1:8881/health"
FLUX_GENERATE_URL = "http://127.0.0.1:8881/generate"
FLUX_TIMEOUT_SECONDS = 300

# How many base-language glosses (beyond the row's own correct one) are
# drawn as distractors for each "meaning" multiple_choice card — capped at
# whatever's actually available so early rows (few prior items) still work.
DISTRACTOR_COUNT = 2
# How many prior items get pulled into each pack's match_pairs reinforcement
# card, alongside the row's own new item.
REINFORCE_COUNT = 2
# Mirrors validate_course.py's MAX_OPTION_WORDS (3) — an option must have
# fewer words than this. A multi-word target_word/base_gloss (e.g. "Call an
# ambulance") is perfectly fine as a PROMPT, but must never be used as an
# option in a multiple_choice card — checked before every such use so a
# genuinely wordy phrase falls back to speech_recognition instead of
# producing a hard-error at validate time.
MAX_OPTION_WORDS = 3
# Mirrors validate_course.py's MAX_TOTAL_WORDS (10) — prompt + options
# together must fit this, the escape hatch for a card whose prompt alone
# runs over MAX_PROMPT_WORDS. Used to gate the "translate this sentence"
# card off when a row's own example_gloss + generated prompt template are
# long enough (e.g. a two-sentence combo) to blow the budget outright.
MAX_TOTAL_WORDS = 10


def _fits_as_option(text: str) -> bool:
    return len(text.split()) < MAX_OPTION_WORDS


def _fits_as_card(prompt: str, options: str = "") -> bool:
    return len(prompt.split()) + len(options.split()) <= MAX_TOTAL_WORDS


class VocabRow:
    def __init__(
        self,
        deck: str,
        target_word: str,
        target_type: str,
        base_gloss: str,
        example_sentence: str = "",
        example_gloss: str = "",
    ):
        self.deck = deck
        self.target_word = target_word
        self.target_type = target_type
        self.base_gloss = base_gloss
        self.example_sentence = example_sentence
        self.example_gloss = example_gloss


def read_vocab(path: Path) -> list[VocabRow]:
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for i, row in enumerate(reader, start=2):
            deck = (row.get("deck") or "").strip()
            target_word = (row.get("target_word") or "").strip()
            target_type = (row.get("target_type") or "word").strip().lower()
            base_gloss = (row.get("base_gloss") or "").strip()
            example_sentence = (row.get("example_sentence") or "").strip()
            example_gloss = (row.get("example_gloss") or "").strip()
            if not deck or not target_word or not base_gloss:
                raise ValueError(
                    f"row {i}: deck, target_word, and base_gloss are all required"
                )
            rows.append(
                VocabRow(deck, target_word, target_type, base_gloss, example_sentence, example_gloss)
            )
    if not rows:
        raise ValueError("vocabulary CSV has no data rows")
    return rows


def build_units_csv(rows: list[VocabRow]) -> list[dict]:
    decks: list[str] = []
    for row in rows:
        if row.deck not in decks:
            decks.append(row.deck)
    return [
        {"id": str(i + 1), "title": deck, "description": "", "image": ""} for i, deck in enumerate(decks)
    ]


def deck_cover_prompt(deck_title: str) -> str:
    """A reasonable default prompt for a deck's cover art, built from just
    its title. Follows the generate-image skill's own guidance for
    icon/flashcard-style art: clean minimal background, bright vibrant
    colors, playful/simple design, one clear focal subject. A human author
    can always regenerate a specific deck's cover with a more specific
    prompt afterward — this exists so the script's output is complete out
    of the box, not to be the final word.

    Deliberately phrased as "an icon symbolizing X" rather than quoting the
    deck title as if it were a caption/poster headline — an earlier version
    of this prompt did exactly that ("representing the theme 'X'") and FLUX
    frequently rendered the quoted title as garbled, misspelled on-image
    text anyway despite an explicit "no text" instruction (a real, observed
    failure across several decks of the first course this generated).
    Repeating the no-text instruction with concrete synonyms (labels, signs,
    banners, captions) and steering away from scene types that naturally
    invite signage (storefronts, departure boards, menus) measurably cuts
    down how often the model still tries to add text.
    """
    return (
        f"A single simple flat-vector icon illustration symbolizing {deck_title.lower()}, "
        f"for a language-learning app. Minimalist icon design, one clear object or "
        f"character as the focal subject, clean flat background, bright cheerful colors, "
        f"playful simple shapes. Do not depict any storefronts, signage, menus, "
        f"departure boards, or posters. Absolutely no text, no words, no letters, no "
        f"numbers, no captions, no titles, no labels, no readable signs, no banners, "
        f"no logos anywhere in the image — a pure icon-style illustration only."
    )


def _flux_server_ready() -> bool:
    try:
        with urllib.request.urlopen(FLUX_HEALTH_URL, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return bool(data.get("model_loaded"))
    except (urllib.error.URLError, OSError, ValueError):
        return False


def generate_deck_cover(deck_title: str, output_path: Path) -> None:
    """Generates one 256x256 deck-cover image via the local FLUX server and
    saves it to `output_path`. Raises RuntimeError with an actionable
    message if the server isn't running — never silently skips, since a
    caller that asked for images wants to know why one is missing."""
    if not _flux_server_ready():
        raise RuntimeError(
            "Image server not reachable at "
            f"{FLUX_HEALTH_URL} (or not finished loading its model). Start it with:\n"
            r'  & "D:\MRM\01 Mine\Mine R1\Plan\Apps\Image generator and tts\scripts\start_servers.ps1" -Servers flux'
            "\nthen retry with --generate-images."
        )
    payload = json.dumps(
        {
            "prompt": deck_cover_prompt(deck_title),
            "output_path": str(output_path),
            "width": 256,
            "height": 256,
            "num_inference_steps": 4,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        FLUX_GENERATE_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=FLUX_TIMEOUT_SECONDS) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not Path(result.get("output_path", output_path)).exists():
        raise RuntimeError(f"Image server reported success but wrote no file for deck '{deck_title}'")


def generate_deck_covers(decks: list[str], images_dir: Path) -> dict[str, str]:
    """Generates one deck-cover image per deck, one at a time (never
    concurrently — see this module's FLUX_* constants), skipping any deck
    whose image file already exists so re-running a partially-completed
    generation doesn't burn 1-2 minutes per deck redoing finished work."""
    images_dir.mkdir(parents=True, exist_ok=True)
    filenames: dict[str, str] = {}
    for i, deck in enumerate(decks):
        filename = f"deck{i + 1}.png"
        filenames[deck] = filename
        path = images_dir / filename
        if path.exists():
            print(f"  [{i + 1}/{len(decks)}] {deck}: already exists, skipping")
            continue
        print(f"  [{i + 1}/{len(decks)}] {deck}: generating (~1-2 min)...")
        started = time.monotonic()
        generate_deck_cover(deck, path)
        print(f"    done in {time.monotonic() - started:.0f}s")
    return filenames


def meaning_question(target_word: str) -> str:
    # A target phrase that already ends in "?" (e.g. "What time is it?")
    # already carries the question mark that matters — stacking a second,
    # Farsi one right after it ("What time is it? یعنی چی؟") reads as a
    # punctuation mistake, not two independent questions. The English target
    # and the Farsi question go on separate lines, never side by side on
    # one — see AUTHORING.md's "Bilingual text goes on separate lines"
    # section for why (LinkedText can only align a whole line one way; a
    # line has to be single-script for that to mean anything).
    suffix = "یعنی چی" if target_word.rstrip().endswith("?") else "یعنی چی؟"
    return f"{target_word}\n{suffix}"


def true_false_prompt(target_word: str, gloss: str) -> str:
    return f"{target_word}\nیعنی «{gloss}»، درست یا غلط؟"


def build_cards_csv(
    rows: list[VocabRow], rng: random.Random, course_slug: str = "course"
) -> tuple[list[dict], list[dict]]:
    """Returns (cards, tts_manifest) — the manifest is one row per audio
    file this course's listening_card cards need, {audio, text}, meant to
    be handed to this repo's TTS batch tooling afterward (see this
    module's own doc comment)."""
    deck_id_by_name: dict[str, str] = {}
    for i, row in enumerate(rows):
        if row.deck not in deck_id_by_name:
            deck_id_by_name[row.deck] = str(len(deck_id_by_name) + 1)

    cards: list[dict] = []
    tts_manifest: list[dict] = []
    next_id = 1

    def emit(**fields) -> str:
        nonlocal next_id
        cid = str(next_id)
        next_id += 1
        row = {
            "id": cid,
            "unit_id": "",
            "type": "multiple_choice",
            "role": "main",
            "related_main_id": "",
            "prompt": "",
            "options": "",
            "correct_index": "",
            "image": "",
            "audio": "",
            "video": "",
            "explanation": "",
        }
        row.update(fields)
        cards.append(row)
        return cid

    # Counts only rows that actually have an example_sentence — throttling
    # the "translate this sentence" card off THIS instead of `i` (the raw
    # row index) means the throttle stays every-other-SENTENCE regardless
    # of how many sentence-less rows come between them.
    sentence_rows_seen = 0

    for i, row in enumerate(rows):
        unit_id = deck_id_by_name[row.deck]
        prior = rows[:i]

        # 1. Main. A "X یعنی چی؟" multiple_choice needs at least one real
        # distractor gloss to be a genuine question — for the first row or
        # two, before any prior item exists to safely draw one from, fall
        # back to speech_recognition (pure production, no options at all)
        # instead of padding a 1-option "choice" that Yaaddi's own schema
        # wouldn't even accept. Distractors are always base-language
        # glosses drawn only from already-emitted rows, never a raw
        # target-language word — this is what makes script-mixing in the
        # options list structurally impossible here.
        distractor_pool = [
            r.base_gloss for r in prior if r.base_gloss != row.base_gloss and _fits_as_option(r.base_gloss)
        ]
        has_real_choice = len(distractor_pool) >= 1 and _fits_as_option(row.base_gloss)
        if has_real_choice:
            distractors = rng.sample(distractor_pool, k=min(DISTRACTOR_COUNT, len(distractor_pool)))
            options = [row.base_gloss] + distractors
            main_id = emit(
                unit_id=unit_id,
                type="multiple_choice",
                role="main",
                prompt=meaning_question(row.target_word),
                options="|".join(options),
                correct_index="0",
                explanation=f"{row.target_word}\nیعنی {row.base_gloss}.",
            )
        else:
            distractors = []
            main_id = emit(
                unit_id=unit_id,
                type="speech_recognition",
                role="main",
                prompt=row.target_word,
                explanation=f"آن را بگویید:\n{row.target_word}",
            )

        # 2. Preview — an obvious true/false statement, the only place
        # true_false is ever used.
        emit(
            unit_id=unit_id,
            type="true_false",
            role="preview",
            related_main_id=main_id,
            prompt=true_false_prompt(row.target_word, row.base_gloss),
            correct_index="true",
            explanation=f"{row.target_word}\nیعنی {row.base_gloss}.",
        )
        # The app only cares about related_main_id, not row order, but the
        # CSV reads more naturally with the preview row before its main
        # row — swap the two just-appended entries (main, then preview)
        # into (preview, then main) without touching their ids.
        cards[-2], cards[-1] = cards[-1], cards[-2]

        # 3. Practice — real sentence usage, as early in the pack as the
        # word's own meaning is established, not saved for "every so
        # often." A course that only ever quizzes isolated word meanings
        # never gets the learner to an actual usable utterance — this is
        # what actually earns the "for a real conversation" claim. Emitted
        # whenever the row supplies one (author-provided — see this
        # module's doc comment on why sentences aren't auto-composed):
        # arrange it, say the whole thing aloud (not just the isolated
        # word), and — when the new word itself is short enough to be a
        # legal option — fill it back into the sentence from a blank.
        if row.example_sentence:
            # ";;"-separated list, not just one — a substitution-drill row
            # (e.g. teaching "You are" against every adjective taught so
            # far: "You are happy", "You are sad", "You are thirsty") needs
            # several sentences out of ONE row, not one. See this module's
            # doc comment on why this is the actual generative mechanism,
            # not example_sentence's occasional single bonus sentence.
            sentences = [s.split("|") for s in row.example_sentence.split(";;")]
            glosses = row.example_gloss.split(";;") if row.example_gloss else []
            glosses += [""] * (len(sentences) - len(glosses))

            for sentence_index, (sentence_words, sentence_gloss) in enumerate(zip(sentences, glosses)):
                explanation = "این جمله را با کلماتی که تاکنون یاد گرفته‌اید می‌سازید."
                if sentence_gloss:
                    explanation += f" معنای آن: {sentence_gloss}"
                # A pack with several substitutions (";;") emits one order
                # card per sentence — none may share its literal prompt
                # text with another in the same pack, or validate_course.py's
                # "identical question in a pack" check fires (it compares
                # type+prompt only, not options, so two order cards
                # differing only in which sentence they arrange still read
                # as the same question asked twice). Cycles through a small
                # set of natural phrasings rather than just two, since a
                # pack can list more than two substitutions (e.g. teaching
                # "o'clock" against three different numbers).
                order_prompts = [
                    "جمله را به ترتیب درست بچین.",
                    "این جمله را هم به ترتیب درست بچین.",
                    "این جمله را نیز به ترتیب درست بچین.",
                    "این جمله‌ی بعدی را هم به ترتیب درست بچین.",
                ]
                order_prompt = order_prompts[sentence_index % len(order_prompts)]
                emit(
                    unit_id=unit_id,
                    type="order",
                    role="exercise",
                    related_main_id=main_id,
                    prompt=order_prompt,
                    options="|".join(sentence_words),
                    explanation=explanation,
                )
                # Every substitution beyond the first only gets the arrange-
                # it rep — giving all four treatments (order/speech/fill-in/
                # translate) to every single substitution would blow up
                # pack size the moment a row lists several (a "You are"
                # row substituting through 3 prior adjectives would emit 12
                # cards on its own otherwise).
                if sentence_index > 0:
                    continue
                emit(
                    unit_id=unit_id,
                    type="speech_recognition",
                    role="exercise",
                    related_main_id=main_id,
                    prompt=" ".join(sentence_words),
                    explanation=f"این جمله را با صدای بلند بخوانید:\n{' '.join(sentence_words)}",
                )
                if row.target_word in sentence_words and _fits_as_option(row.target_word):
                    blank_index = sentence_words.index(row.target_word)
                    blanked = list(sentence_words)
                    blanked[blank_index] = "___"
                    blank_distractor_pool = [
                        r.target_word
                        for r in prior
                        if r.target_word != row.target_word and _fits_as_option(r.target_word)
                    ]
                    if len(blank_distractor_pool) >= 1:
                        blank_distractors = rng.sample(
                            blank_distractor_pool, k=min(DISTRACTOR_COUNT, len(blank_distractor_pool))
                        )
                        blank_options = [row.target_word] + blank_distractors
                        rng.shuffle(blank_options)
                        emit(
                            unit_id=unit_id,
                            type="select_blank",
                            role="exercise",
                            related_main_id=main_id,
                            prompt=" ".join(blanked),
                            options="|".join(blank_options),
                            correct_index=str(blank_options.index(row.target_word)),
                            explanation=explanation,
                        )
            # Duolingo's single most-used exercise across a whole course is
            # "translate this sentence" — given the meaning, produce the
            # WHOLE sentence, not just recognize or arrange it. Every card
            # type above tests recognizing/hearing/arranging the sentence;
            # none tests actually producing it unprompted, which is the
            # real target skill. Scoped to the row's FIRST (primary)
            # sentence only, matching the "full treatment" cards above —
            # substitutions 2+ already only get the lighter arrange-it rep.
            # Needs a gloss for that first sentence specifically (not just
            # example_sentence) since the gloss is the only cue that
            # doesn't just hand back the English answer. Throttled to every
            # other sentence, not every one — like the word-level
            # type_answer card, this counts toward validate_course.py's 10%
            # typing-card budget, and combined with that card it would
            # otherwise blow well past it.
            primary_gloss = glosses[0]
            primary_sentence = " ".join(sentences[0])
            translate_prompt = f"«{primary_gloss}» را به انگلیسی بنویسید."
            if (
                primary_gloss
                and sentence_rows_seen % 2 == 0
                and _fits_as_card(translate_prompt, primary_sentence)
            ):
                emit(
                    unit_id=unit_id,
                    type="type_answer",
                    role="exercise",
                    related_main_id=main_id,
                    prompt=translate_prompt,
                    options=primary_sentence,
                    explanation=primary_sentence,
                )
            sentence_rows_seen += 1

        # 4. Practice — never repeat the main card's own "X یعنی چی؟"
        # question verbatim (validate_course.py hard-errors on exactly that
        # — the identical prompt with only the distractor set changed isn't
        # a different angle). Once at least 2 prior target-language items
        # exist, ask the *reverse* direction instead: "which word means
        # <gloss>?" with same-script (all target-language) options — a
        # genuinely different question, not a cosmetic variant. Below that
        # threshold, fall back to a second speech_recognition rep, same as
        # the zero-prior-item case.
        reverse_pool = [
            r.target_word for r in prior if r.target_word != row.target_word and _fits_as_option(r.target_word)
        ]
        row_word_fits_as_option = _fits_as_option(row.target_word)
        if len(reverse_pool) >= 2 and row_word_fits_as_option:
            reverse_distractors = rng.sample(reverse_pool, k=min(DISTRACTOR_COUNT, len(reverse_pool)))
            reverse_options = [row.target_word] + reverse_distractors
            rng.shuffle(reverse_options)
            # Same "don't stack a redundant question mark" fix as
            # meaning_question — a gloss that's itself a question (e.g.
            # "ساعت چنده؟") already supplies the mark this template would
            # otherwise duplicate right after the closing quote.
            reverse_suffix = "" if row.base_gloss.rstrip().endswith("؟") else "؟"
            emit(
                unit_id=unit_id,
                type="multiple_choice",
                role="exercise",
                related_main_id=main_id,
                prompt=f"کدام گزینه به معنای «{row.base_gloss}» است{reverse_suffix}",
                options="|".join(reverse_options),
                correct_index=str(reverse_options.index(row.target_word)),
                explanation=f"{row.target_word}\nیعنی {row.base_gloss}.",
            )
        elif has_real_choice:
            emit(
                unit_id=unit_id,
                type="speech_recognition",
                role="exercise",
                related_main_id=main_id,
                prompt=row.target_word,
                explanation=f"دوباره تمرین کنید:\n{row.target_word}",
            )
        else:
            # No prior item exists yet to build a real multiple_choice or
            # match_pairs from (this only ever happens for the very first
            # row of the whole course) — one more speech_recognition rep is
            # the only content-safe option, at the cost of a soft
            # "near-duplicate" warning from validate_course.py that a human
            # author would normally avoid; a course this small at the very
            # start has no better alternative without inventing content.
            # Deliberately just ONE extra rep, not two: this row is always
            # index 0, which always also gets the type_answer card below (a
            # genuinely different angle) — piling on a second identical
            # speech_recognition rep on top of that just makes the pack
            # repeat the same tap-and-speak action for no added value.
            emit(
                unit_id=unit_id,
                type="speech_recognition",
                role="exercise",
                related_main_id=main_id,
                prompt=row.target_word,
                explanation=f"دوباره تمرین کنید:\n{row.target_word}",
            )

        # 5. Practice — match_pairs reinforcing this item alongside 1-2
        # prior ones (skipped for the very first row, nothing to reinforce
        # yet).
        reinforce_pool = prior
        reinforce_sample = rng.sample(reinforce_pool, k=min(REINFORCE_COUNT, len(reinforce_pool)))
        pair_rows = [row] + reinforce_sample
        if len(pair_rows) >= 2:
            pairs = "|".join(f"{r.target_word}↔{r.base_gloss}" for r in pair_rows)
            emit(
                unit_id=unit_id,
                type="match_pairs",
                role="exercise",
                related_main_id=main_id,
                prompt="هر عبارت را به معنای فارسی آن وصل کنید.",
                options=pairs,
                explanation="هر عبارت را با معنای فارسی آن جفت کنید.",
            )

        # 6. Practice — production via speech_recognition.
        emit(
            unit_id=unit_id,
            type="speech_recognition",
            role="exercise",
            related_main_id=main_id,
            prompt=row.target_word,
            explanation=f"آن را بگویید:\n{row.target_word}",
        )

        # 7. Practice — spelling recall: given the base-language meaning,
        # type the target word. Distinct from listening_card's "type what
        # you heard" (dictation, no meaning involved) — this instead tests
        # recall-and-spelling from the gloss alone, no audio, no options to
        # recognize from. type_answer is normally reserved for code/
        # commands (case-sensitive, exact-match grading isn't fair to a
        # definition with multiple valid phrasings), but a language
        # course's own target word is exactly the one case where typing IS
        # the skill being tested — see docs/CARD_AUTHORING.md's
        # teachesLanguage typing-card exception. Grading is case-insensitive
        # (typeAnswerCard.tsx normalizes both sides), so capitalization
        # doesn't trip up a genuinely correct answer. Only every other row,
        # not every pack — validate_course.py warns once typing cards pass
        # 10% of a course, and one per pack alone would already blow past
        # that; every 3rd row keeps real spelling practice without turning
        # every single review into a keyboard exercise.
        if i % 3 == 0:
            emit(
                unit_id=unit_id,
                type="type_answer",
                role="exercise",
                related_main_id=main_id,
                prompt=f"«{row.base_gloss}» به انگلیسی چیست؟ آن را تایپ کنید.",
                options=row.target_word,
                explanation=f"{row.target_word}\nیعنی {row.base_gloss}.",
            )

        # 8. Practice — listening comprehension. Reuses the exact same
        # reverse_pool distractors as step 3 when there are enough (a
        # genuine "which word did you hear" choice); falls back to typing
        # the word heard once at least one real item exists to distinguish
        # it from silence. Skipped only for the very first row, where
        # neither is meaningful yet.
        audio_file = f"{course_slug}_{main_id}.mp3"
        if len(reverse_pool) >= 2:
            listen_options = [row.target_word] + rng.sample(
                reverse_pool, k=min(DISTRACTOR_COUNT, len(reverse_pool))
            )
            rng.shuffle(listen_options)
            emit(
                unit_id=unit_id,
                type="listening_card",
                role="exercise",
                related_main_id=main_id,
                options="select|" + "|".join(listen_options),
                correct_index=str(listen_options.index(row.target_word)),
                audio=audio_file,
                explanation=f"عبارتی که شنیدید:\n{row.target_word}\n({row.base_gloss})",
            )
            tts_manifest.append({"audio": audio_file, "text": row.target_word})
        elif has_real_choice:
            emit(
                unit_id=unit_id,
                type="listening_card",
                role="exercise",
                related_main_id=main_id,
                options=f"type|{row.target_word}",
                audio=audio_file,
                explanation=f"عبارتی که شنیدید:\n{row.target_word}\n({row.base_gloss})",
            )
            tts_manifest.append({"audio": audio_file, "text": row.target_word})

    return cards, tts_manifest


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate(
    vocab_path: Path, course_dir: Path, seed: int = 0, generate_images: bool = False
) -> None:
    rows = read_vocab(vocab_path)
    rng = random.Random(seed)

    units = build_units_csv(rows)
    source_dir = course_dir / "source"
    if generate_images:
        deck_titles = [unit["title"] for unit in units]
        print(f"Generating {len(deck_titles)} deck cover image(s) via the local FLUX server...")
        images = generate_deck_covers(deck_titles, source_dir / "images")
        for unit in units:
            unit["image"] = images.get(unit["title"], "")
    cards, tts_manifest = build_cards_csv(rows, rng, course_slug=course_dir.name)

    source_dir.mkdir(parents=True, exist_ok=True)
    write_csv(source_dir / "units.csv", ["id", "title", "description", "image"], units)
    write_csv(
        source_dir / "cards.csv",
        [
            "id", "unit_id", "type", "role", "related_main_id", "prompt",
            "options", "correct_index", "image", "audio", "video", "explanation",
        ],
        cards,
    )
    write_csv(source_dir / "tts_manifest.csv", ["audio", "text"], tts_manifest)
    print(
        f"Wrote {len(units)} unit(s) and {len(cards)} card(s) to {source_dir} "
        f"({len(tts_manifest)} audio file(s) still needed — see tts_manifest.csv)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vocab_csv", help="Path to the vocabulary CSV (deck, target_word, target_type, base_gloss)")
    parser.add_argument("course_folder", help="Course folder to write source/units.csv and source/cards.csv into")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for distractor/reinforcement sampling (default 0, for reproducible output)")
    parser.add_argument(
        "--generate-images",
        action="store_true",
        help=(
            "Generate one 256x256 deck-cover image per unit via the local FLUX "
            "image server (see the generate-image skill) and write source/images/. "
            "Off by default: needs that server running locally and takes ~1-2 "
            "minutes per deck. Re-running with this flag skips any deck whose "
            "image file already exists."
        ),
    )
    args = parser.parse_args()

    try:
        generate(
            Path(args.vocab_csv),
            Path(args.course_folder),
            seed=args.seed,
            generate_images=args.generate_images,
        )
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
