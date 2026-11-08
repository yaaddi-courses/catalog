"""Adds "Learn more" article support to a course's build_course_zip.py and validate_course.py (idempotent).

One-shot migration helper for course repos made from an older course-template. Both files are
patched in memory first and written only when both patches succeed, so a failure never leaves a
half-patched pair.

usage: python tools/add_article_support.py <course dir> [<course dir> ...]
"""
import os
import sys


def sub(text, old, new):
    if old not in text:
        raise SystemExit(f"expected text not found: {old[:70]!r}")
    return text.replace(old, new, 1)


BUILD_READ = '''    glossary_path = os.path.join(source_dir, "glossary.csv")
    glossary_text = None
    if os.path.isfile(glossary_path):
        with open(glossary_path, encoding="utf-8-sig") as f:
            glossary_text = f.read()
'''
BUILD_READ_NEW = BUILD_READ + '''
    # "Learn more" articles (optional): source/articles/<slug>.md ship inside the zip as articles/<slug>.md.
    articles_dir = os.path.join(source_dir, "articles")
    articles = {}
    if os.path.isdir(articles_dir):
        for name in sorted(os.listdir(articles_dir)):
            if name.endswith(".md"):
                with open(os.path.join(articles_dir, name), encoding="utf-8-sig") as f:
                    articles[name] = f.read()
'''
BUILD_WRITE = '''        if glossary_text is not None:
            zf.writestr("glossary.csv", glossary_text)
'''
BUILD_WRITE_NEW = BUILD_WRITE + '''        for name, text in articles.items():
            zf.writestr("articles/" + name, text)
'''
BUILD_NOTE = '''    glossary_note = " + glossary.csv" if glossary_text is not None else ""
'''
BUILD_NOTE_NEW = BUILD_NOTE + '''    if articles:
        glossary_note += f" + {len(articles)} article(s)"
'''

VALIDATE_ARTICLE_FN = '''
ARTICLE_REF = re.compile(r"^[a-z0-9][a-z0-9-]*(#[a-z0-9][a-z0-9-]*)?$")
ANCHOR_IN_ARTICLE = re.compile(r"\\{#([a-z0-9-]+)\\}")


def read_article_anchors(articles_dir):
    """slug -> set of {#anchor} names, for every source/articles/<slug>.md."""
    anchors = {}
    if articles_dir and os.path.isdir(articles_dir):
        for name in sorted(os.listdir(articles_dir)):
            if name.endswith(".md"):
                with open(os.path.join(articles_dir, name), encoding="utf-8-sig") as f:
                    anchors[name[:-3]] = set(ANCHOR_IN_ARTICLE.findall(f.read()))
    return anchors


def validate_article_ref(row_no, term, reference, anchors, report):
    """A glossary row's optional `article` ("slug" or "slug#anchor") must name a real article and heading."""
    if not reference:
        return
    if not ARTICLE_REF.match(reference):
        report.error(
            f'glossary.csv row {row_no} ("{term}"): article "{reference}" must look like "slug" or "slug#anchor" '
            "(lowercase letters, digits and hyphens)"
        )
        return
    if anchors is None:
        return
    slug, _, anchor = reference.partition("#")
    if slug not in anchors:
        report.error(f'glossary.csv row {row_no} ("{term}"): article "{slug}" has no source/articles/{slug}.md')
    elif anchor and anchor not in anchors[slug]:
        report.error(
            f'glossary.csv row {row_no} ("{term}"): articles/{slug}.md has no heading with {{#{anchor}}}'
        )

'''


# Exact lines this script inserts: their presence (not any mention of "articles_dir") means
# the file is already patched.
BUILD_MARKER = 'zf.writestr("articles/" + name, text)'
VALIDATE_MARKER = "def validate_article_ref("


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def patch_build(text):
    """The patched build_course_zip.py text, or None when it is already patched."""
    if BUILD_MARKER in text:
        return None
    text = sub(text, BUILD_READ, BUILD_READ_NEW)
    text = sub(text, BUILD_WRITE, BUILD_WRITE_NEW)
    return sub(text, BUILD_NOTE, BUILD_NOTE_NEW)


def patch_validate(text):
    """The patched validate_course.py text, or None when it is already patched."""
    if VALIDATE_MARKER in text:
        return None
    text = sub(text, "\ndef validate_glossary_rows(rows, report, card_ids=None):", VALIDATE_ARTICLE_FN + "\ndef validate_glossary_rows(rows, report, card_ids=None, article_anchors=None):")
    text = sub(
        text,
        '        link = (row.get("link") or "").strip()\n        # Which card actually teaches',
        '        link = (row.get("link") or "").strip()\n        validate_article_ref(i, term, (row.get("article") or "").strip(), article_anchors, report)\n        # Which card actually teaches',
    )
    # source-dir path: pass the anchors read from source/articles
    text = sub(
        text,
        "    validate_glossary_rows(rows, report, card_ids)\n",
        '    validate_glossary_rows(\n        rows, report, card_ids, read_article_anchors(os.path.join(source_dir, "articles"))\n    )\n',
    )
    # zip path: anchors from the zip's articles/*.md
    text = sub(
        text,
        "                validate_glossary_rows(read_csv_text(glossary_text), report, card_ids)\n",
        '''                zip_anchors = {}
                for entry in zf.namelist():
                    if entry.startswith("articles/") and entry.endswith(".md"):
                        body = zf.read(entry).decode("utf-8-sig")
                        zip_anchors[entry[len("articles/"):-3]] = set(ANCHOR_IN_ARTICLE.findall(body))
                validate_glossary_rows(read_csv_text(glossary_text), report, card_ids, zip_anchors)
''',
    )
    return text


def patch_course(course):
    """Patch both files of one course; returns (build patched, validate patched). Raises
    SystemExit, writing nothing, when either file lacks the expected text."""
    build_path = os.path.join(course, "build_course_zip.py")
    validate_path = os.path.join(course, "validate_course.py")
    new_build = patch_build(read_text(build_path))
    new_validate = patch_validate(read_text(validate_path))
    if new_build is not None:
        write_text(build_path, new_build)
    if new_validate is not None:
        write_text(validate_path, new_validate)
    return new_build is not None, new_validate is not None


if __name__ == "__main__":
    for course in sys.argv[1:]:
        b, v = patch_course(course)
        print(course, "build" if b else "build(already)", "validate" if v else "validate(already)")
