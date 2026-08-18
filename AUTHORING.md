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

Fifteen card types are available. Each row below is a `cards.csv` line — see the "CSV
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
| `type` | no | one of the 15 types above; defaults to `multiple_choice` |
| `role` | yes | `main`, `exercise`, or `preview` |
| `related_main_id` | exercise/preview cards only | the main card's `id` this drills (exercise) or introduces (preview) — leave empty on main cards |
| `prompt` | yes | the question text (may contain commas — CSV-quote the field if so) |
| `options` | depends on `type` | see the card-types table above |
| `correct_index` | depends on `type` | see the card-types table above |
| `image` | no | filename, becomes a picture above the prompt (every type except `media_card`) |
| `audio` | `media_card` only | filename — this is the **only** column/type combination the app supports audio on |
| `explanation` | no | shown when the answer is wrong |

A malformed row (unknown `unit_id`, a `type_answer` with empty `options`, an
`exercise` with no `related_main_id`, etc.) fails the whole import with a clear,
per-card error naming the offending row — nothing partial gets written.
`validate_course.py --source` catches this before you even get as far as an import.
