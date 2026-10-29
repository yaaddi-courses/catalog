# Writing a course

This guide moved. Course content no longer lives in this repo — each course is
its own repo under the [yaaddi-courses](https://github.com/yaaddi-courses)
org, created from the
[course-template](https://github.com/yaaddi-courses/course-template) repo —
so the canonical, kept-up-to-date copy of this guide lives there too:

**[yaaddi-courses/course-template/AUTHORING.md](https://github.com/yaaddi-courses/course-template/blob/main/AUTHORING.md)**

See this repo's own [README.md](README.md) for how a new course repo gets
picked up into the catalog.

## Learn more articles (the app reads and shows them since 2026-10-28)

A glossary row has a short definition. Its **Learn more article** is a longer lesson, written like a chapter of a self-learning book, with a worked example. Several related terms share one article. When the learner taps a term, the app opens the article **scrolled to the section where that term is explained**.

**Where the files live**

```
<course>/
  source/
    glossary.csv            term, definition, link, introduced_by_card_id, article
    articles/               <- the dedicated folder: one .md file per article
      quantization.md
      pruning.md
```

The folder ships in the course zip as `articles/` (the course's `build_course_zip.py` copies it; a course whose tools predate this runs `python tools/add_article_support.py <course folder>` once to add it to its `build_course_zip.py` and `validate_course.py`). In the app a tapped term shows a "Read the full explanation" button that opens the article and scrolls to the `{#anchor}` named in the glossary row; `validate_course.py` fails a row whose `slug#anchor` does not exist. Each course has its own `articles/` and its own glossary, because the same word can mean different things in different courses. Nothing is shared between courses. A course without an `articles/` folder has not opted in yet and the article checks stay silent; a course with the folder must give every term an article.

**Linking a term to its article.** `glossary.csv` gets an `article` column: `slug` (the file name without `.md`) or `slug#anchor`. The anchor is required when the article covers more than one term, because it is the scroll target.

```
term,definition,link,introduced_by_card_id,article
Quantization,"Storing a model's numbers with fewer bits...",https://...,134,quantization#quantization
Quantization scale,"The factor that converts...",https://...,1694,quantization#scale
```

**The article file**

```markdown
# Quantization: storing a model with fewer bits

**Covers:** Quantization, Quantization scale, Calibration data

## What problem does this solve? {#quantization}
...
## How the rounding works, step by step {#scale}
...
## Choosing the scale: calibration {#calibration}
...
## Key points
- ...
```

- The first line is a `# Title`. The second block is `**Covers:**` with the glossary terms the article teaches (3 to 8, spelled as in the glossary).
- An anchor is `{#name}` at the end of a `##` heading: lowercase letters, digits and hyphens. Give each covered term the section that explains it.
- Sections, in this order: what problem it solves, the core idea, a worked example the reader can follow by hand, why it can go wrong or a common mistake, then `## Key points` (3 to 5 bullets). Tables and short code blocks are welcome.
- Length: about 600 to 900 words (the check warns outside 500 to 1000).

**Tone: a self-learning book.** Someone who has done the course so far must finish the article able to explain the term in their own words. Plain, friendly, professional. Explain every word you use that the course has not taught yet. Do not say "obviously", "simply" or "of course". Every number and claim must be correct and checkable; run every example calculation or code block. Do not repeat the glossary definition: the article starts where the definition stops.

**Keep it dry inside the course.** One home per term. Do not copy a paragraph or an example between articles; say it once and let the other article name the term (the learner can tap it). Reuse nothing from another course.

**Checks (`review-course`, `python run.py run --course <course> --only-checks <names>`):** `article_present`, `article_covers_terms`, `article_length`, `article_structure`, `article_forward_reference` (no term from a later deck), `article_dry` (no repetition), `article_code_valid` (Python examples parse; set `run_code = true` to run them, only for courses you wrote because it executes the code), `article_size_budget` (default 300 KB zipped), and the model-judged `article_tone_llm` (a newcomer would understand it). See `review-course/docs/CHECKS.md`.

## Updating a published course: ids and versions (written 2026-10-28, app task X128)

When a learner updates a course, the app matches the new file to what is installed **by the `id` of each deck and card** (the `source_local_id`). Everything about keeping or losing progress follows from that:

| What you change | What happens to a learner's progress |
|---|---|
| Edit the wording of a card, keep its `id` | Kept. The schedule, streak and history stay on that card. |
| Change what a card **means** (a different answer, a different concept) but keep its `id` | Kept, and wrong: the old answers now describe a different question. Give a meaning-changing card a **new id** instead. |
| Add a card or a deck | New and unlearned. |
| Remove a card (its `id` is gone from the file) | The card, its schedule and its history are deleted. The app warns how many cards with progress would be lost. |
| Remove a deck | The same, for every card in it. |
| Renumber or regenerate ids (for example re-running `ensure_course_ids.py` without keeping the old ones) | Every card looks removed and re-added: **all progress is lost**. Never do this to a published course. |
| Change only `version` | An update is offered whenever the string differs from the installed one. It is a plain string compare, not semver, so `1.10.0` versus `1.9.0` is simply "different". Always bump it upward and add a `changelog` line to `meta.json`. |

So: **an `id` never changes once the course is published**, and the review tool should be pointed at the ids before a release. A new course can use any ids it likes until it is published.
