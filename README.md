# Yaaddi Courses

Community course content for **Yaaddi**, a free spaced-repetition learning app. This
repo is a **course pack**: a plain-file catalog of ready-to-import courses, and
everything needed to build new ones. The courses here are open source, so anyone can
browse, edit, or contribute to them — the app itself is separate, closed-source
software. This repo doesn't depend on the app's own repository being cloned
alongside — everything you need to author, validate, and publish a course lives here.

There's no server, no account to run. A course is a folder; publishing it is a git push
(after building its `.zip` locally — see "Delivery mechanism" below).

**Browse online:** https://mohammad-reza-mahdiani.github.io/yaaddi/ — a searchable,
filterable catalog with cover images, deck lists, and example cards for every course
below, rebuilt automatically by `.github/workflows/pages.yml` any time course content
changes (see "Course catalog site" further down).

## Available courses

| Course | Topic | Decks | Cards |
|---|---|---|---|
| [`git/`](git/) | Version control | 39 | 236 |
| [`docker-and-containers/`](docker-and-containers/) | Containers, Dockerfiles, Compose | 44 | 180 |
| [`kubernetes-fundamentals/`](kubernetes-fundamentals/) | Clusters, pods, networking, storage | 41 | 244 |
| [`concurrency-in-python/`](concurrency-in-python/) | Threading, multiprocessing, asyncio | 85 | 787 |
| [`python-basics/`](python-basics/) | Python fundamentals | 24 | 196 |
| [`effective-vibecoding/`](effective-vibecoding/) | Directing an AI coding agent well | 27 | 167 |
| [`testing-in-software-engineering/`](testing-in-software-engineering/) | Test types, TDD, coverage, CI | 32 | 194 |
| [`software-architecture/`](software-architecture/) | Architecture styles and trade-offs | 40 | 177 |
| [`sdlc/`](sdlc/) | The software development lifecycle | 34 | 143 |
| [`managing-software-projects/`](managing-software-projects/) | Running a real software project | 35 | 147 |
| [`emotional-intelligence/`](emotional-intelligence/) | Self-awareness and interpersonal skills | 40 | 172 |
| [`opentelemetry/`](opentelemetry/) | Traces, metrics, logs, and the Collector | 38 | 228 |
| [`harness/`](harness/) | Unified CI/CD pipelines and delivery | 34 | 204 |

> **Delivery mechanism:** each course ships as a `<slug>.zip` (meta/units/cards.csv
> plus every referenced image/audio file), **committed to the repo tree** right next
> to `meta.json`. Build it with `python build_course_zip.py <name>` after any change
> to `source/`, then commit the resulting `<name>/<slug>.zip` along with your other
> changes.
>
> A GitHub Release asset was tried first instead (avoids the git-history cost of a
> multi-MB binary) and reverted — Release assets don't send
> `Access-Control-Allow-Origin`, so the app's web build gets a CORS error on every
> download attempt (confirmed against this exact repo, not just docs).
> `raw.githubusercontent.com` — what a committed, co-located file is served from —
> does support CORS. There's no backend to route around that gap without standing up
> server infrastructure this project otherwise avoids, so a committed file is the only
> option that works on every platform (web included). `concurrency-in-python.zip`
> currently runs ~10MB; that's an accepted trade-off, not an oversight.

## Repo layout

```
<repo-root>/
├── README.md                     (this file)
├── AUTHORING.md                  (how to write a course — content rules, card variety, etc.)
├── build_course_zip.py           (builds <slug>.zip from source/ — stdlib-only, same as validate_course.py)
├── catalog.json                  (auto-generated — see below, don't hand-edit)
├── .github/workflows/
│   └── validate-courses.yml      (runs validate_course.py on every PR/push)
├── python-basics/
│   ├── meta.json                 ← what the Course Library reads
│   ├── python-basics.zip         ← built + committed — what Install actually downloads
│   ├── cover.jpg                 ← the course's cover image
│   └── source/                   ← the actual course content, human-editable
│       ├── meta.csv
│       ├── units.csv
│       ├── cards.csv
│       └── images/
└── concurrency-in-python/
    ├── meta.json
    ├── concurrency-in-python.zip
    ├── cover.png
    └── source/
        └── ...
```

Some courses also have a local, **gitignored** `source/build/` — the script(s) that originally generated that course's `cards.csv` or its narration audio. Never part of the delivery pipeline (nothing reads it at import or validate time) and never committed, matching `.internal/`'s "raw authoring tooling doesn't belong in the public tree" rule. Not every course has one; skip it if you're authoring `source/*.csv` by hand.

**One top-level folder per course, and only finished courses live at the repo root.**
A course that's still being written lives under `.internal/wip-courses/<name>/` instead
— gitignored, so it never appears in the public repo tree — and only gets moved to the
repo root once it's actually done.

The folder name is **not** the course's real identity, just where its files currently
live — see `meta.json`'s `id` field below.

### `meta.json`

```json
{
  "id": "python-basics",
  "title": "Python",
  "description": "Learn modern Python from the ground up.",
  "image": "cover.png",
  "file": "python-basics.zip",
  "version": "1.1.0",
  "toc": ["Python Basics", "Control Flow", "Functions & Data Structures"],
  "tags": ["python", "beginner"],
  "language": "en",
  "changelog": [
    { "version": "1.0.0", "notes": "Initial release." },
    { "version": "1.1.0", "date": "2026-08-07", "notes": "Added a Type Hints unit." }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | strongly recommended | This course's **stable identity** — never changed once published. Without it, the app falls back to using this course's *folder name* as its identity, which breaks "check for updates" for everyone who already installed it the moment this folder is ever renamed. `python validate_course.py` warns if it's missing; `python ensure_course_ids.py` assigns one automatically (defaulting to the current folder name — a safe, zero-breakage default), and the `validate-courses` GitHub Action runs that for you and commits the result on every PR, so you rarely need to set this by hand. Once assigned, **never change it** for an existing course — a changed id looks like a brand-new course to anyone who already installed the old one. |
| `title` | yes | Course title, shown in the Course Library list |
| `description` | no (defaults to empty) | Shown under the title |
| `image` | no | Filename of the cover image, **relative to this course's own folder** |
| `file` | yes | Filename of the built `.zip`, **committed in this course's own folder** (see "Delivery mechanism" above) |
| `version` | no | Mirrors `meta.csv`'s own `version` — lets a learner's app detect an update without downloading the whole course. Keep it in sync by hand whenever you bump `meta.csv`'s version. |
| `toc` | no | Deck/unit titles, in order — shown as a preview **before** a learner downloads the course. Without it, title/description/cover is the whole preview. Just copy the `title` column of your `source/units.csv`, in row order. |
| `tags` | no | Free-form labels (e.g. `"python"`, `"beginner"`) — used to filter the Course Library list. Not a curated/fixed set, use whatever's genuinely descriptive. |
| `language` | no (defaults to `en`) | This course's own content language (e.g. `en`, `fa`) — mirrors `source/meta.csv`'s own `language` column. The Course Library ranks a course whose `language` matches the app's current interface language above the rest, so set this to whatever language the course's cards are actually written in. |
| `titleTranslations` | no | Per-interface-language override of `title`, e.g. `{ "fa": "..." }` — mirrors `source/meta.csv`'s `title_fa`/`title_<code>` columns. Shown instead of `title` when the app's interface language has a matching entry. |
| `descriptionTranslations` | no | Per-interface-language override of `description` — same rule as `titleTranslations`. |
| `changelog` | no | Array of `{ version, date?, notes }` — one entry per published version. When a learner's app detects an update, the entry whose `version` matches the new `version` is shown as "What's new." Add one new entry each time you bump `version`; never edit or remove a past entry. |

A folder at the repo root with no valid `meta.json` is just skipped (not treated as an
error) — so a plain README, a `LICENSE`, or a `.github/` folder at the root is fine.

### `catalog.json`

Every course's `meta.json` concatenated into one file — this is what the Yaaddi app
actually fetches to load the Course Library (one request instead of a directory
listing plus one request per course, which matters once this repo has hundreds or
thousands of courses in it). **You never write this by hand.** `python
tools/build_catalog.py` regenerates it from whatever's currently at the repo root, and
`validate-courses.yml` does that automatically and commits the result on every push to
`main` — same pattern as `id` auto-assignment above. `validate_course.py --all` checks
it's actually in sync (a hard error if it's stale), which mainly matters for a PR from
a fork, where CI can't push the auto-commit back (`GITHUB_TOKEN` is read-only there) —
run `python tools/build_catalog.py` locally in that case before opening the PR.

### The course source itself

Three CSVs (`meta.csv`, `units.csv`, `cards.csv`) plus an `images/`/`media/` folder for
anything they reference — this is the same shape Yaaddi's in-app **Export** produces
and **Import** accepts, just not built into a package here. **Full column-by-column
reference, including the exact encoding each of the 14 card types expects for its
options/answers: [`AUTHORING.md`](AUTHORING.md).**

## Adding a new course

1. Pick a folder name and create `<name>/source/` with `meta.csv`, `units.csv`,
   `cards.csv`, and any images/audio they reference. While it's incomplete, this lives
   under `.internal/wip-courses/<name>/`, not the repo root. (The folder name is just
   where the files live, not the course's real identity — see `meta.json`'s `id` field
   below; you don't need to get the folder name "right" up front.)
2. Read [`AUTHORING.md`](AUTHORING.md) for the content guidelines this project follows
   (deck structure, card-type variety, how many practice cards per concept, audio
   conventions, etc.) — courses accepted here should read like they were written by
   someone who actually wants you to learn the topic, not a content mill.
3. Pick or generate a cover image, save it as `<name>/cover.png` (or `.jpg`).
4. Write `<name>/meta.json` (see the table above). You can leave out `id` — the
   `validate-courses` GitHub Action assigns one automatically once you open a PR; or
   run `python ensure_course_ids.py <name>` yourself to set it locally first.
5. **Run the validator**: `python validate_course.py <name> --source` (or
   `--all --source` to check every course at the repo root) — catches dangling
   references (a card pointing at a `unit_id` that doesn't exist, an exercise with no
   main card, a referenced `image`/`audio` file that isn't actually present), unknown
   card types, duplicate cards, decks with no cards, main cards with too few practice
   cards, and more — see [`AUTHORING.md`](AUTHORING.md#before-you-publish) for the full
   list. Zero dependencies beyond Python's standard library.
6. **Build the zip**: `python build_course_zip.py <name>` — reads `source/`, writes
   `<name>/<slug>.zip`. Set `meta.json`'s `file` to that filename.
7. `git add <name>/` (the zip included — it's not gitignored) and once the course is
   genuinely done, move its folder from `.internal/wip-courses/` to the repo root and
   open a PR.

**`.github/workflows/validate-courses.yml` runs automatically on every PR** — step 5
above just lets you catch the same problems locally before pushing, rather than
waiting on CI. There's no build-automation workflow — the zip is a normal committed
file you build and `git add` yourself, same as any other change.

## Updating an existing course

Yaaddi's import already knows how to update a course **in place** without losing
anyone's review progress: re-importing content whose internal `meta.slug` matches a
course someone already has installed updates its content (new/changed/removed cards)
while keeping their spaced-repetition history for anything that didn't change. That
means you can freely fix typos, add decks, or expand a course later — just bump the
`version` in `meta.csv` (and `meta.json`'s own `version`, plus one new `changelog`
entry describing what changed), **rebuild the zip** (`python build_course_zip.py
<name>`), and push. Everyone who already has the course gets the update the next time
they check.

## Course catalog site

`tools/build_site.py` renders a static browsable catalog — an index page (cover
images, descriptions, tag filter, search) plus one dedicated page per course (full
deck list, card-type mix, image coverage, a couple of real example cards). It's pure
Python stdlib, reads only `meta.json` + `source/units.csv` + `source/cards.csv` (never
the app itself, never a live API), and writes plain static HTML/CSS/JS — no build
tooling, no framework, nothing to install beyond `python3`.

**It rebuilds and redeploys automatically.** `.github/workflows/pages.yml` runs the
generator and publishes the result via GitHub Pages any time a push to `main` touches
a course's `meta.json`, `source/cards.csv`, `source/units.csv`, cover image, or the
site tooling itself — the generated HTML is never committed to the repo, it's a
throwaway CI artifact rebuilt fresh every time. **Nothing needs updating by hand when
a course changes** — write the content, bump the version, push; the site catches up on
its own.

To preview locally before pushing:

```bash
python tools/build_site.py --out _site
python -m http.server -d _site 8000   # then open http://localhost:8000
```

One manual one-time setup step (can't be done from a workflow file): in the repo's
GitHub Settings → Pages, set **Source: GitHub Actions**.

This is deliberately a separate, read-only mechanism from the app's own in-app Course
Library (which fetches `meta.json`/the `.zip` directly from this repo via the GitHub
API at install time) — the site never touches or reformats those files, so it can't
break that flow. If a future in-app "browse without installing" feature wants a single
cached catalog index instead of live API calls, `tools/build_site.py`'s course-data
extraction is the natural thing to reuse or share a format with; that's not built yet.

## License

Course content in this repo is licensed under the terms in [`LICENSE`](LICENSE)
(PolyForm Noncommercial 1.0.0) — independent of whatever license, if any, the Yaaddi
app's own source is under. If you're contributing a course built from a source with
its own license (a textbook's examples, a dataset, etc.), say so in that course's own
folder (e.g. an `ATTRIBUTION.md`) rather than assuming.
