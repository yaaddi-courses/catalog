# Yaaddi Courses (catalog)

The **main connection point** between the [Yaaddi](https://github.com/yaaddi-courses)
app and the course catalog — the app's Course Library fetches this repo's
`catalog.json` as its single source of truth. Every actual course lives in
its **own repo** under the [yaaddi-courses](https://github.com/yaaddi-courses)
GitHub organization (one repo per course), not here — this repo only holds
the generated index, the shared tooling that builds it, and the docs. The
course content is open source; the app itself is separate, closed-source
software.

**Browse online:** https://yaaddi-courses.github.io/yaaddi-courses/ — a
searchable, filterable catalog with cover images, deck lists, and example
cards for every course, rebuilt automatically (see "Course catalog site"
below).

## Starting a new course

Click **"Use this template"** on
[yaaddi-courses/course-template](https://github.com/yaaddi-courses/course-template)
to create a new repo under the org, then follow that repo's own README and
[`AUTHORING.md`](https://github.com/yaaddi-courses/course-template/blob/main/AUTHORING.md)
for the full content-writing guide (deck structure, card-type variety, how
many practice cards per concept, word/prompt-length limits, and everything
`validate_course.py` checks).

**Once your course repo is ready and merged to `main`, the only remaining
step is tagging it with the `yaaddi-course` topic** (repo Settings → General
→ Topics, or `gh repo edit <owner>/<repo> --add-topic yaaddi-course`) — that's
what makes it show up here. No PR against this repo, no manual catalog edit.
This repo's own scheduled workflow (or a manual trigger — see below) scans
the org for every `yaaddi-course`-tagged repo and rebuilds `catalog.json`
from scratch.

## `catalog.json`

Every tagged course repo's `meta.json`, concatenated into one file — this
is what the Yaaddi app actually fetches to load the Course Library (one
request instead of one API call per course). **You never write this by
hand.** `python tools/build_catalog.py` regenerates it by querying GitHub
for every repo in the org tagged `yaaddi-course`, then fetching each one's
own `meta.json` directly — see that script's own doc comment for the exact
mechanism (and why it needs an authenticated token, unlike the raw-content
fetches it makes after that).

`.github/workflows/rebuild-catalog.yml` runs this on a schedule (every 6
hours) and supports `workflow_dispatch` for an on-demand run right after you
tag a new course — no need to wait for the schedule.

Each entry carries `repo` ("owner/repo", the course's own dedicated repo)
and `branch` (that repo's default branch) instead of the old monorepo's
`path` (a folder within one shared repo) — the app's own schema
(`src/lib/githubMarketplace.ts` in the Yaaddi app repo) accepts both shapes
permanently, since an already-installed app build can never be forced to
understand a new one.

## Repo layout

```
<repo-root>/
├── README.md                       (this file)
├── AUTHORING.md                    (pointer — canonical copy lives in course-template)
├── LICENSE                         (PolyForm Noncommercial 1.0.0)
├── catalog.json                    (auto-generated — see above, don't hand-edit)
├── tools/
│   ├── build_catalog.py            (org-wide scan → catalog.json)
│   ├── list_course_repos.py        (shared discovery step, used by pages.yml too)
│   ├── build_site.py               (the public catalog site generator)
│   └── site_assets/                (static assets for the site)
└── .github/workflows/
    ├── rebuild-catalog.yml         (scheduled + manual catalog.json rebuild)
    └── pages.yml                   (builds + deploys the public catalog site)
```

Course content itself — `meta.json`, the built `.zip`, `cover.*`,
`source/{meta,units,cards}.csv` + images/media — lives in each course's own
repo, not here. See
[yaaddi-courses/course-template](https://github.com/yaaddi-courses/course-template)
for that layout.

## Rebuild-catalog auth (for maintainers)

`rebuild-catalog.yml` and `pages.yml` both need a token that can list/read
every repo in the org — the automatic per-job `GITHUB_TOKEN` is scoped only
to this one repo and can't do that. Stored as the `ORG_CATALOG_PAT` repo
secret: a fine-grained personal access token scoped to every repo in
`yaaddi-courses`, with `Contents: read` + `Metadata: read` permissions.
Fine-grained PATs expire — renew it (Settings → Developer settings →
Personal access tokens) before it does, or the scheduled rebuild starts
failing with a 403.

## Course catalog site

`tools/build_site.py` renders a static browsable catalog — an index page
(cover images, descriptions, tag filter, search) plus one dedicated page
per course (full deck list, card-type mix, image coverage, a couple of real
example cards). Pure Python stdlib, writes plain static HTML/CSS/JS.

Since it needs each course's full `source/units.csv` + `source/cards.csv`
(not just `meta.json`), `pages.yml` shallow-clones every `yaaddi-course`-
tagged repo into a scratch directory first (via `tools/list_course_repos.py`,
no auth needed for cloning public repos), then runs `build_site.py
--courses-dir <scratch dir>` against that. It's chained to run right after
`rebuild-catalog.yml` completes, so the site always reflects the latest
catalog.

To preview locally against your own already-cloned course repos:

```bash
python tools/build_site.py --out _site --courses-dir /path/to/cloned/courses
python -m http.server -d _site 8000   # then open http://localhost:8000
```

One manual one-time setup step (can't be done from a workflow file): in the
repo's GitHub Settings → Pages, set **Source: GitHub Actions**.

## License

This repo's own tooling/docs are licensed under the terms in
[`LICENSE`](LICENSE) (PolyForm Noncommercial 1.0.0). Each course's own
content is licensed the same way, in that course's own repo — see
[yaaddi-courses/course-template](https://github.com/yaaddi-courses/course-template)'s
own `LICENSE`.
