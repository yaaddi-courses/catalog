# Writing a course

Guidelines for anyone building a course for this repo. The goal is a course that
actually teaches the topic — comprehensively, in the right order, with enough practice
that the material sticks — not a quick quiz.

## Structure

- **One deck (unit) per sub-topic.** Break the subject down into focused pieces rather
  than a handful of huge decks.
- **Be comprehensive.** Cover the topic from the absolute basics through to advanced,
  complete coverage. There's no card-count ceiling to aim under — thoroughness matters
  more than brevity. A large, complete course is better than a small, tidy one that
  stops halfway through the subject.
- **Order matters.** Put foundational decks before the ones that depend on them, and
  never use a term or concept in a practice card before its main card has actually
  taught it.
- **Deck titles are clean.** No "Deck 1:", no numbering — `units.csv`'s `title` column
  should read like a real heading (e.g. "Concurrency Models Comparison"), not
  bookkeeping. Section headers (grouping labels) are fine to keep as their plain name.

## Cards

- **Every distinct concept gets its own main (master) card.** If a deck genuinely
  covers more than one idea (e.g. "why plain `return` doesn't cross a thread boundary"
  *and* "how exceptions propagate from a thread" are two separate ideas even in the
  same deck), give each its own main card — don't force multiple concepts onto one
  card just to keep the deck's card count low.
- **Each main card gets 5–10 practice (exercise) cards.** These reinforce that one
  concept from a few different angles — not just a single follow-up question.
- **Keep cards atomic and bite-sized — hard limits, not a suggestion.** One fact or
  concept per card — never two claims bundled into one prompt, even if they're
  related. **A prompt must be under 10 words**, and **each option on a
  multiple-choice-style card (`multiple_choice`, `multi_select`, `image_choice`,
  `select_blank`) must be under 3 words** (`validate_course.py`, see "Before you
  publish" below, rejects a card over either limit). The one exception: if the
  prompt and all its options together add up to 10 words or fewer, that also
  passes, even if one option alone runs to 3+ words — a short prompt can "spend"
  its budget on the options. If a card genuinely can't fit a fact into that shape,
  **don't cram it in** — split it into more cards (another main card, or more
  practice cards) instead. If you're writing "and" to join two things a learner
  needs to know separately, that's usually a sign the card should split into two.

  *Before (two concepts, one over-long card):*
  > "A daemon thread is automatically killed when the main program exits, and a
  > non-daemon thread will keep the program alive until it finishes on its own."

  *After (split into two atomic, short cards):*
  > Card A — prompt: "What happens to a daemon thread at exit?" — options:
  > "Killed automatically" / "Keeps running" / "Throws error"
  > Card B — prompt: "Does a non-daemon thread keep the program alive?" — options:
  > "Yes" / "No" / "Only sometimes"

  The more granular the cards, the more precisely a learner's actual gaps show up, and
  the more efficiently spaced repetition can schedule reviews around them.
- **Use real scenarios.** Concrete, practical situations a learner would actually run
  into beat abstract definitions on their own.
- **Vary the card type — and lean into whichever ones actually fit your topic.** A
  course that leans on one or two types the whole way through is a worse learning
  experience than one that mixes them deliberately. If your topic involves real code,
  commands, or syntax (a programming language, a CLI tool, config file format, etc.),
  **use `code_fill`** — it's built specifically for that and is easy to under-use if you
  default to safer multiple-choice-style cards out of habit. `validate_course.py`
  warns if a whole main card's practice cards are all one type, or if a course only
  uses a handful of the 14 available types overall.
- **Keep typing rare — under 10% of a course's cards.** `type_answer`, `code_fill`,
  `numeric_answer`, `command_output`, and `short_answer` all require typing on a
  keyboard, which is slower and more error-prone than tapping. `validate_course.py`
  warns when a course crosses that 10% line — treat it as a real signal to convert
  some of those cards to a tap-based type (`select_blank`, `multiple_choice`) where the
  question still works without typing.
- **Write like a person who wants you to learn this, not a spec sheet.** Descriptions
  and prompts should read naturally — the way you'd actually explain something to a
  friend — not "This course provides comprehensive coverage of...". Real examples and
  a little personality beat dry, robotic phrasing; learning should feel closer to
  something you'd actually enjoy than to homework, without sacrificing clarity for a
  joke.

## Preview cards

A third role, `preview`, sits in front of a main card's very first attempt — a
one-time "here's the concept" beat before the graded version appears. It's a
teaching step, not a test — tapping the right answer always "succeeds" and it
never re-appears once that main card has been learned (a later review of it
skips straight to the graded card, no preview). Link it to its main card
exactly like an exercise, via `related_main_id`.

A preview doesn't have to be the plain "concept text + one 'Got it' button"
shape (`type=preview_card`). It can instead be formatted like a real
interactive card — `multiple_choice`, `true_false`, or `select_blank` are the
usual fits — as long as the correct answer is **self-evident**: one clearly-
right option, or every other option obviously false. This is still a teaching
moment, not a quiz, so keep it gentle and unambiguous; it's not the place for
genuine distractors. Either shape is fine, pick whichever presents the concept
more naturally:

```
id,unit_id,type,role,related_main_id,prompt,options,correct_index,image,audio,explanation
12,3,preview_card,preview,10,"A daemon thread is killed automatically when the main program exits.","Got it",,,,
13,4,true_false,preview,11,"A daemon thread dies when the main program exits.",,true,,,
```

When a preview is authored as `multiple_choice`/`true_false`/`select_blank`,
it must obey the same rules as any other card of that type — the `<10`-word
prompt / `<3`-word option limits from "Card-writing rules" apply, and
`validate_course.py` enforces them. A plain `preview_card` row is exempt from
that word-count check (its `prompt` is teaching prose, not a quiz question),
which is why that shape is still the simpler default for a concept too dense
to compress into a 10-word question.

Keep a preview to exactly the one atomic idea its main card is about to test —
if you find yourself explaining two things, that's two main cards (and two
previews), not one long preview. Previews are excluded from spaced repetition
and from a deck's completion percentage — they're a one-time on-ramp, not
graded content, so a course doesn't strictly need one for every main card. That
said, when retrofitting or authoring a course, pairing every main card with
its own preview is the recommended default — it's simpler and more consistent
than deciding case-by-case which concepts "need" one.

## Card types reference

Twenty-one card types are available. Each row below is a `cards.csv` line — see the "CSV
format" section further down for the full column list.

| type | what the learner sees | how to encode it in `cards.csv` |
|---|---|---|
| `multiple_choice` (default if `type` is left blank) | A question with several options, tap one | `options` = pipe-delimited choices (`"Paris\|London\|Berlin"`); `correct_index` = 0-based index of the right one |
| `true_false` | A statement, tap True or False | `prompt` = the statement; `correct_index` = literally `true` or `false` |
| `select_blank` | A sentence with a blank, tap the right word from a few choices (no keyboard) | `prompt` contains `___`; `options` = pipe-delimited choices; `correct_index` = index of the right one |
| `multi_select` | A question, tap every option that applies (checkboxes) | `options` = pipe-delimited choices; `correct_index` = pipe-delimited list of every correct index, e.g. `"0\|2\|3"` |
| `order` | A jumbled list, tap items in the correct order | `options` = the items **already in correct order** (the app shuffles them for display) |
| `match_pairs` | Two columns, tap a left item then its matching right item | each `options` entry is one pair written as `left↔right` |
| `image_choice` | An icon grid, tap the right one | each `options` entry is `label:iconName` (an [Ionicons](https://icons.expo.fyi/Index/Ionicons) glyph name) |
| `type_answer` | A question, type the answer on the keyboard | `options` = accepted answer, or pipe-delimited if more than one spelling is acceptable; matching is case/whitespace-insensitive. Last resort — a phone keyboard mid-lesson is friction; prefer `select_blank` for "fill in the blank" |
| `code_fill` | A syntax-highlighted code/command snippet with a blank, type what goes there | `options[0]` = the code snippet containing a `___` blank; `options[1+]` = accepted answers. **Case-sensitive** (code is), unlike `type_answer` |
| `media_card` | Image + audio + a multiple-choice question — the only type with sound | `options`/`correct_index` work like `multiple_choice`; the `audio` column (filename) is exclusive to this type — see "Audio" below |
| `image_occlusion` | A diagram with one region masked, type what's hidden there ("Hide One, Guess One" — the rest of the diagram stays visible for context) | `image` = the diagram (**required**); each `options` entry is `"x,y,w,h:label"` (coordinates as **fractions of the image, 0-1**, not pixels); `correct_index` = which region *this row* asks about. All rows for one diagram share the same `options`/`image` — one row per region, same shape as a main card's practice-card siblings. Great for anatomy, circuit diagrams, architecture/network diagrams — anything with real spatial structure |
| `numeric_answer` | A question, type a number on the numeric keyboard | `options[0]` = correct value; `options[1]` = tolerance (default 0, exact match); `options[2]` = optional unit shown next to the input (not graded). Use for measurements/calculations where `type_answer`'s exact-string match is too strict |
| `command_output` | A command/snippet (syntax-highlighted), type what it prints | `options[0]` = the command; `options[1]` = its expected output (may contain newlines — quote the field). **Case-sensitive**, unlike `type_answer`. Different skill from `code_fill` — this is "run it, predict the result," not "fill in the blank" |
| `short_answer` | A question, type a short answer (a flag, command name, or keyword) | `options` = accepted answer, or pipe-delimited if more than one spelling is acceptable; **case-sensitive**, like `code_fill`. Each accepted answer must be **24 characters or fewer** — this type is for a keystroke or two, not a phrase; use `type_answer` if the real answer is longer |
| `preview_card` | A one-time "here's the concept" intro shown right before a main card's first attempt — plain teaching text, tap the single button to continue | `prompt` = the concept, stated plainly (not as a question); `options[0]` = the button label (e.g. `"Got it"`). Only valid with `role` = `preview` — see "Preview cards" below |
| `categorize` | A list of items, tap each one into the bucket it belongs in | each `options` entry is one item written as `item↔bucket` (2-4 distinct bucket names across the whole item list, ≥3 items) — many-to-few, unlike `match_pairs`' strict 1:1 pairing |
| `spot_error` | A code/command line broken into pieces, tap the one that's wrong | `options` = the line's pipe-delimited segments/tokens; `correct_index` = which segment is broken |
| `listening_card` | Audio plays (no visible text at all — this is a listening exercise), answer by typing, tapping an option, or arranging words | `options[0]` = `response_type` (`type`/`select`/`order`); for `type`, `options[1]` = the accepted answer (case/whitespace-insensitive, like `type_answer`); for `select`, `options[1+]` = pipe-delimited choices and `correct_index` = the right one; for `order`, `options[1+]` = the words **already in correct order**. The `audio` column (filename) is required, same convention as `media_card`'s. Only counts toward the typing budget below when `response_type` is `type` |
| `speech_recognition` | A phrase to read aloud — passes automatically once on-device speech recognition hears a match (the app's normal skip button is always available as a fallback) | `prompt` = the phrase. Only makes sense in a `teaches_language: true` course (see below) — the phrase is spoken as a pronunciation model, then the learner reproduces it |
| `reading_passage` | A longer passage (paragraph, dialogue, or short story) in its own box, then a separate comprehension question with multiple-choice answers | `prompt` = the passage (a properly-quoted CSV field may contain real newlines — author it multi-line directly). `options[0]` = the comprehension question; `options[1+]` = the answer choices; `correct_index` refers to that choice sub-list (0 = `options[1]`, not `options[0]`). Several cards may share the identical `prompt` with a different question each time — build a real pack of one main + several exercises about the same passage |
| `cloze_passage` | The same kind of longer passage, but with several words blanked out, filled in via either per-blank multiple choice or one shared tap-to-build word bank — no typed blanks | `prompt` = the passage with `{{1}}`, `{{2}}`, … numbered blank placeholders, in order. `options[0]` = mode: `choice` or `word_bank`. For `choice`: `options[1+]` = one entry per blank, each blank's own options joined by `~` (e.g. `"weather~bill~menu"`); `correct_index` = one `\|`-delimited index per blank (e.g. `"0\|1"`). For `word_bank`: `options[1]` = the shared word pool joined by `~` (may include distractors never used); `options[2]` = the correct fill sequence, also `~`-joined; `correct_index` unused. `~` is used instead of `\|` for the inner lists because `\|` already splits the outer `options` column |

Every type also accepts an optional `explanation` column, shown when the answer is
wrong, and an optional `image` column (a filename, becomes a picture shown above the
prompt — not supported on `media_card`, which uses its own image handling instead).

## Multimedia

- Add a cover image per deck (`units.csv`'s `image` column) and, where it actually
  helps understanding, images inside individual cards (`cards.csv`'s `image` column —
  every card type except `media_card` supports it; `media_card` uses its own
  `imageUri`/`audio` fields instead).
- **Only `media_card` carries audio** in the current schema. If a card is introducing a
  new term for the first time and audio would help (e.g. pronunciation, or a spoken
  walkthrough), author that specific card as a `media_card` rather than adding audio
  anywhere else — no other card type has an audio field at all.
- Never ship placeholder images or audio. If you can't produce a real asset for
  something, leave it out rather than faking it. For narration/pronunciation audio,
  a local text-to-speech model (e.g. Kokoro) is the recommended way to produce a real
  clip with no cloud API and no third-party voice-licensing question — the exact
  tooling isn't part of this repo, so use whatever local TTS setup you have.

## Before you publish

First, run `python validate_course.py <your-course-folder> --source` (from the repo
root) — it catches structural mistakes automatically: dangling `unit_id`/
`related_main_id` references, an `image`/`audio` filename that isn't actually present
in `source/images/`/`source/media/`, an unknown card type, a duplicate card, a deck
with no cards at all, a main card with too few practice cards, a prompt of 10+ words
(or a choice-list option of 3+ words) that doesn't fit within a 10-word prompt+options
total, a main card whose practice cards are all the same single type, a whole
course leaning on fewer than 5 of the 15 available card types, more than 10% of the
course's cards requiring typing, low explanation coverage across the course, and a
course with zero `media_card` cards at all (meaning nothing in it is narrated for a
learner who prefers listening). Zero dependencies.

Then read through the finished course as if you were a complete beginner encountering
the material for the first time — this is the part no script can do for you:

- Is every practice card actually answerable from what its main card (and earlier
  decks) already taught?
- Are explanations clear on their own, without assuming context the course hasn't
  given yet?
- Does anything feel confusing, tedious, or like busywork rather than learning?

Fix what fails that check before opening a PR. Once this repo's delivery mechanism is
settled, also do one real import-and-click-through in the app itself before merging —
a card that's structurally valid but pedagogically useless still passes the validator.

## CSV format

Three CSV files, plus an `images/`/`media/` folder for anything they reference — see
this repo's [`README.md`](README.md) for exactly where each file goes inside a course
folder. IDs everywhere are small human-friendly integers, not UUIDs.

### `meta.csv` — one row

| column | required | meaning |
|---|---|---|
| `slug` | yes | lowercase-hyphenated unique id, e.g. `my-first-course` |
| `title` | yes | display name |
| `description` | no | one sentence, shown on the course's browse card |
| `version` | yes | e.g. `1.0.0` — bump it whenever you republish updated content |
| `author` | no | your name |
| `color` | no | hex color, e.g. `#58CC02` |
| `icon` | no | an [Ionicons](https://icons.expo.fyi/Index/Ionicons) glyph name |
| `image` | no | cover image filename (this is separate from — and simpler than — the `cover.png`/`meta.json` pair the Course Library reads; see this repo's `README.md`) |
| `language` | no | the course's own content language (e.g. `en`, `fa`) — drives card-content text direction in the app, independent of the app's own interface language. Defaults to `en`. |
| `teaches_language` | no | `true` only when this course teaches `language` itself as a spoken/written skill (a "Learn English" course) — **not** just because its content happens to be written in that language (a Farsi course about, say, personal finance stays `false`). Set to `true` to get automatic text-to-speech playback of each card and to unlock the language-course typing-card exception below. Defaults to `false`. |
| `title_fa` | no | Farsi override of `title`, shown when the app's interface language is Farsi (falls back to `title` otherwise). Extend with `title_<code>` for another interface language. |
| `description_fa` | no | Farsi override of `description` — same rule as `title_fa`. |

### `units.csv` — one row per deck

| column | required | meaning |
|---|---|---|
| `id` | yes | integer, unique within this file |
| `title` | yes | deck title — no "Deck 1:" numbering, see above |
| `description` | no | shown in the app's course editor |
| `min_level` | no | currently unused by the app's unlock logic (decks unlock strictly in the order they appear in this file, once the previous one is fully learned) — safe to leave as `1` |
| `section` | no | consecutive rows sharing the same value group under one section header on the Learn map |
| `image` | no | deck cover image filename |
| `section_image` | no | cover image for the section header — only takes effect on the row that *starts* a section |
| `section_color` | no | hex color for the section header — same "only the row that starts the section" rule |

### `cards.csv` — one row per card

Columns: `id,unit_id,type,role,related_main_id,prompt,options,correct_index,image,audio,explanation`

| column | required | meaning |
|---|---|---|
| `id` | yes | integer, unique within this file |
| `unit_id` | yes | matches an `id` in `units.csv` |
| `type` | no | one of the 19 types above; defaults to `multiple_choice` |
| `role` | yes | `main`, `exercise`, or `preview` |
| `related_main_id` | exercise/preview cards only | the main card's `id` this drills (exercise) or introduces (preview) — leave empty on main cards |
| `prompt` | yes | the question text (may contain commas — CSV-quote the field if so) |
| `options` | depends on `type` | see the card-types table above |
| `correct_index` | depends on `type` | see the card-types table above |
| `image` | no | filename, becomes a picture above the prompt (every type except `media_card`) |
| `audio` | `media_card`/`listening_card` only | filename — see the card-types table above for each type's own audio semantics |
| `explanation` | no | shown when the answer is wrong |

A malformed row (unknown `unit_id`, a `type_answer` with empty `options`, an
`exercise` with no `related_main_id`, etc.) fails the whole import with a clear,
per-card error naming the offending row — nothing partial gets written.
`validate_course.py --source` catches this before you even get as far as an import.

## Generating a language course from a vocabulary list

For a "teach language A to language B speakers" course (e.g. English for
Farsi Speakers), hand-authoring every pack is slow and error-prone —
`tools/generate_language_course.py` builds `source/units.csv` and
`source/cards.csv` automatically from a plain vocabulary spreadsheet,
following the exact base-language-framing pedagogy this repo settled on
(one new item per pack, `true_false` reserved for preview only, distractors
always drawn from already-taught items, no script-mixing in an options list).

Input CSV columns: `deck,target_word,target_type,base_gloss,example_sentence,example_gloss`
— one row per word/phrase, **in the exact order it should be introduced**
(row order is the ledger every later pack's distractors and reinforcement
draw from). The last two columns are optional:

```
deck,target_word,target_type,base_gloss,example_sentence,example_gloss
Greetings,Hello,word,سلام,,
Greetings,Please,word,لطفاً,,
Greetings,Thank you,phrase,متشکرم,"Hello,|Thank you","سلام، متشکرم"
Numbers,One,word,یک,,
Numbers,Two,word,دو,,
```

`example_sentence` is pipe-delimited chips (same convention as every other
options column here) — supply one whenever a row's item can combine with
already-taught items into a genuine sentence, and that row's pack gets an
extra `order` practice card building it. This is deliberately **author-
supplied, not auto-composed**: gluing two random taught words together
does not reliably produce a grammatical sentence, and the
flashcard-course-creator skill's "don't teach isolated words forever" rule
(a sentence-building pack every 4-6 items) is a correctness requirement,
not something worth risking on a wrong auto-generated sentence. Leave both
columns blank on rows that don't fit one — not every item needs to.

```bash
python tools/generate_language_course.py my-vocab.csv <course-folder>
```

This writes `<course-folder>/source/units.csv` (one unit per distinct
`deck` value, first-seen order), `source/cards.csv` (a full preview + main
+ 4-6 practice pack per row, now including a `listening_card` rep and, when
supplied, a sentence-building `order` card), and `source/tts_manifest.csv`
(one row per audio file the `listening_card` cards reference, `audio,text`)
— then continue exactly like a hand-authored course: write `source/meta.csv`
yourself (the generator doesn't know the course's title/color/
`target_language`/etc.), add deck cover images and set `units.csv`'s
`image` column, **record/synthesize every row in `tts_manifest.csv` into
`source/media/<audio>`** (this repo's own TTS tooling — see the app's
CLAUDE.md's narration/pronunciation-audio note — same as how the original
hand-authored course's audio was made; never ship a placeholder), run
`build_course_zip.py`, and `validate_course.py --source`.

The generated packs deliberately reuse only card types that already exist
(`true_false`, `multiple_choice`, `match_pairs`, `listening_card`, `order`,
`type_answer`, `speech_recognition`) — no new card type is needed to scale
this pattern to a new language pair. `tools/test_generate_language_course.py`
checks the ledger/script/role invariants the pedagogy depends on; run it
after changing the generator.

### Why a type_answer card, every 3rd row

`type_answer` is normally reserved for code/commands (see this doc's own
"typing budget" rules) — a term or definition shouldn't demand exact
keyboard input when there's often more than one valid phrasing. A
teachesLanguage course's own target word is the deliberate exception:
typing the word IS the skill being tested (spelling recall from the
meaning alone, no options to recognize it from), and grading is
case-insensitive so capitalization never trips up a right answer. It's
throttled to every 3rd row, not every pack, because one per pack alone
would already push a course over the 10% typing-card budget
`validate_course.py` warns on.

### Why a listening_card rep, every pack

Language-learning research (Duolingo's own published work on spaced
repetition and half-life regression, and reviews of app-based vocabulary
practice more broadly) consistently treats listening comprehension as a
distinct skill that reading/production drills alone don't exercise — an
app whose only "audio" is `speech_recognition`'s pronunciation check never
tests whether the learner can understand the target language *heard*, only
whether they can *say* it. That's the whole reason `listening_card` exists
in this app's card-type set — the generator now actually uses it instead
of leaving it a type nothing outputs.

### Why a "translate this sentence" card, every other sentence

Surveying Duolingo's actual exercise taxonomy (not just its early-lesson
structure) turned up one exercise type used constantly across a whole
course that this generator had no equivalent for: given the sentence's
*meaning*, produce the whole sentence — not recognize it in a list, not
hear it and transcribe it, not rearrange it from chips someone else
already picked. Every other sentence-practice format this generator emits
(`order`, `select_blank`, `listening_card`) tests recognizing/hearing/
arranging a sentence that's already been laid out for the learner; none of
them tests actually producing one unprompted, which is the real target
skill a course like this is for. Implemented as a `type_answer` scored
against the row's full `example_sentence`, prompted from `example_gloss`
(the only cue that doesn't just hand back the English answer — a row with
`example_sentence` but no `example_gloss` doesn't get this card). Every
other sentence, not every one: combined with the word-level `type_answer`
card above, doing this for every sentence would push a course well past
the 10% typing-card budget. Also skipped outright when the prompt template
plus a long `example_gloss` (a two-sentence combo, say) would blow the
9-word prompt cap on its own — `_fits_as_card` checks this before emitting,
the same defensive pattern `_fits_as_option` already applies to options.
