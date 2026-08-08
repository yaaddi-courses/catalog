# Yaaddi Courses

Community course content for **Yaaddi**, a free spaced-repetition learning app. This
repo is a **course pack**: a plain-file catalog of ready-to-import courses, and
everything needed to build new ones. The courses here are open source, so anyone can
browse, edit, or contribute to them — the app itself is separate, closed-source
software. This repo doesn't depend on the app's own repository being cloned
alongside — everything you need to author, validate, and publish a course lives here.

There's no server, no account to run. A course is a folder; publishing it is a git push
— CI builds and attaches the installable file automatically (see "Delivery mechanism"
below), nothing to build or upload by hand.

## Available courses

| Course | Topic | Decks | Cards |
|---|---|---|---|
| [`python-basics/`](python-basics/) | Python fundamentals | 24 | 160 |
| [`concurrency-in-python/`](concurrency-in-python/) | Threading, multiprocessing, asyncio | 85 | 783 |

### Work in progress

Git, Docker and Containers, Kubernetes Fundamentals, Effective Vibecoding, and Testing
in Software Engineering each have a finalized deck list but aren't written yet — kept
out of the repo tree entirely (not even a stub folder) until they're actually done.

> **Delivery mechanism:** each course ships as a `<slug>.zip` (meta/units/cards.csv
> plus every referenced image/audio file) attached as a **GitHub Release asset**,
> tagged `<slug>-v<version>` — never committed to the repo tree. A multi-MB binary
> living in git history forever, re-diffed on every clone, isn't what git is for; a
> Release asset is exactly the GitHub-native way to publish a versioned binary without
> that cost, and it's what `.github/workflows/release-courses.yml` builds and uploads
> automatically on every push that changes a course's `source/` — only the course(s)
> that actually changed, not the whole catalog. `meta.json`'s `file`/`version` fields
> tell the app which asset to fetch (`src/lib/githubMarketplace.ts` in the app repo
> resolves them into the Release download URL).

## Repo layout

```
<repo-root>/
├── README.md                     (this file)
├── AUTHORING.md                  (how to write a course — content rules, card variety, etc.)
├── build_release_zip.py          (builds <slug>.zip from source/ — stdlib-only, same as validate_course.py)
├── .github/workflows/
│   ├── validate-courses.yml      (runs validate_course.py on every PR/push)
│   └── release-courses.yml       (builds + publishes a Release for every changed course)
├── python-basics/
│   ├── meta.json                 ← what the Course Library reads
│   ├── cover.jpg                 ← the course's cover image
│   └── source/                   ← the actual course content, human-editable
│       ├── meta.csv
│       ├── units.csv
│       ├── cards.csv
│       └── images/
└── concurrency-in-python/
    ├── meta.json
    ├── cover.png
    └── source/
        └── ...
```

(`<slug>.zip` isn't shown above — it's a CI-built artifact attached to a GitHub
Release, gitignored locally, never sitting in the repo tree.)

**One top-level folder per course, and only finished courses live at the repo root.**
The folder name is that course's stable id. A course that's still being written lives
under `.internal/wip-courses/<name>/` instead — gitignored, so it never appears in the
public repo tree — and only gets moved to the repo root once it's actually done.

### `meta.json`

```json
{
  "title": "Python",
  "description": "Learn modern Python from the ground up.",
  "image": "cover.png",
  "file": "python-basics.zip",
  "version": "1.1.0",
  "toc": ["Python Basics", "Control Flow", "Functions & Data Structures"],
  "tags": ["python", "beginner"],
  "changelog": [
    { "version": "1.0.0", "notes": "Initial release." },
    { "version": "1.1.0", "date": "2026-08-07", "notes": "Added a Type Hints unit." }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `title` | yes | Course title, shown in the Course Library list |
| `description` | no (defaults to empty) | Shown under the title |
| `image` | no | Filename of the cover image, **relative to this course's own folder** |
| `file` | yes | Filename of the built `.zip` — the asset name in the GitHub Release tagged `<slug>-v<version>` (see "Delivery mechanism" above), **not** a path in this repo |
| `version` | **yes** | Mirrors `meta.csv`'s own `version` — required now (not just for update-checks): it's also half of the Release tag CI builds/publishes to (`<slug>-v<version>`), so the app can locate the asset. Keep it in sync by hand whenever you bump `meta.csv`'s version. |
| `toc` | no | Deck/unit titles, in order — shown as a preview **before** a learner downloads the course. Without it, title/description/cover is the whole preview. Just copy the `title` column of your `source/units.csv`, in row order. |
| `tags` | no | Free-form labels (e.g. `"python"`, `"beginner"`) — used to filter the Course Library list. Not a curated/fixed set, use whatever's genuinely descriptive. |
| `changelog` | no | Array of `{ version, date?, notes }` — one entry per published version. When a learner's app detects an update, the entry whose `version` matches the new `version` is shown as "What's new." Add one new entry each time you bump `version`; never edit or remove a past entry. |

A folder at the repo root with no valid `meta.json` is just skipped (not treated as an
error) — so a plain README, a `LICENSE`, or a `.github/` folder at the root is fine.

### The course source itself

Three CSVs (`meta.csv`, `units.csv`, `cards.csv`) plus an `images/`/`media/` folder for
anything they reference — this is the same shape Yaaddi's in-app **Export** produces
and **Import** accepts, just not built into a package here. **Full column-by-column
reference, including the exact encoding each of the 13 card types expects for its
options/answers: [`AUTHORING.md`](AUTHORING.md).**

## Adding a new course

1. Pick a folder name (becomes the course's id) and create `<name>/source/` with
   `meta.csv`, `units.csv`, `cards.csv`, and any images/audio they reference. While
   it's incomplete, this lives under `.internal/wip-courses/<name>/`, not the repo
   root.
2. Read [`AUTHORING.md`](AUTHORING.md) for the content guidelines this project follows
   (deck structure, card-type variety, how many practice cards per concept, audio
   conventions, etc.) — courses accepted here should read like they were written by
   someone who actually wants you to learn the topic, not a content mill.
3. Pick or generate a cover image, save it as `<name>/cover.png` (or `.jpg`).
4. Write `<name>/meta.json` (see the table above).
5. **Run the validator**: `python validate_course.py <name> --source` (or
   `--all --source` to check every course at the repo root) — catches dangling
   references (a card pointing at a `unit_id` that doesn't exist, an exercise with no
   main card, a referenced `image`/`audio` file that isn't actually present), unknown
   card types, duplicate cards, decks with no cards, main cards with too few practice
   cards, and more — see [`AUTHORING.md`](AUTHORING.md#before-you-publish) for the full
   list. Zero dependencies beyond Python's standard library.
6. Set `meta.json`'s `file` to `<slug>.zip` and `version` to match `meta.csv`'s
   `version` (both required now — see the field table above).
7. Once the course is genuinely done, move its folder from `.internal/wip-courses/` to
   the repo root and open a PR.

**Two workflows run automatically, no manual build step:**
- `.github/workflows/validate-courses.yml` runs on every PR — step 5 above just lets
  you catch the same problems locally before pushing, rather than waiting on CI.
- `.github/workflows/release-courses.yml` runs on every push to `main` that changes a
  course's `source/` — builds `<slug>.zip` (`build_release_zip.py`, stdlib-only, same
  convention as the validator) and publishes it as a GitHub Release tagged
  `<slug>-v<version>`, **only for the course(s) that actually changed**, not the whole
  catalog. To build+check one locally before pushing: `python build_release_zip.py
  <name>`.

## Updating an existing course

Yaaddi's import already knows how to update a course **in place** without losing
anyone's review progress: re-importing content whose internal `meta.slug` matches a
course someone already has installed updates its content (new/changed/removed cards)
while keeping their spaced-repetition history for anything that didn't change. That
means you can freely fix typos, add decks, or expand a course later — just bump the
`version` in `meta.csv` (and `meta.json`'s own `version`, plus one new `changelog`
entry describing what changed) with the same internal slug and push. CI builds and
publishes the new Release automatically (`release-courses.yml`) — nothing to build or
upload by hand — and everyone who already has the course gets the update the next
time they check.

## License

Course content in this repo is licensed under the terms in [`LICENSE`](LICENSE)
(PolyForm Noncommercial 1.0.0) — independent of whatever license, if any, the Yaaddi
app's own source is under. If you're contributing a course built from a source with
its own license (a textbook's examples, a dataset, etc.), say so in that course's own
folder (e.g. an `ATTRIBUTION.md`) rather than assuming.
