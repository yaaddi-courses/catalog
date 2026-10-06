"""The privacy page must stay in step with what the app really does (it is linked from the
Play/App Store listings): it has to mention every data-touching feature and the delete option."""
import re
import tempfile
from pathlib import Path

import build_site


def render() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        build_site.render_privacy_page(out)
        return (out / "privacy" / "index.html").read_text(encoding="utf-8")


def test_page_covers_every_data_touching_feature():
    html = render()
    for feature in ("Course Library", "Microphone", "Photos", "Notifications"):
        assert feature in html, feature
    assert "speech recognition" in html
    assert "never records, stores or receives the audio" in html


def test_page_explains_deletion_and_no_tracking():
    html = render()
    assert "Uninstall the app" in html
    assert "no third-party trackers" in html
    assert "support@yaaddi.com" in html


def test_page_has_a_current_last_updated_date_and_is_linked_from_nav():
    html = render()
    assert re.search(r"Last updated: [A-Z][a-z]+ \d{1,2}, 20\d\d", html)
    assert build_site.PRIVACY_UPDATED in html
    assert "../privacy/index.html" in html  # header nav link


def test_every_summary_card_and_table_row_is_rendered():
    html = render()
    assert html.count('class="privacy-card"') == len(build_site.PRIVACY_CARDS)
    assert html.count('class="privacy-pill"') == len(build_site.PRIVACY_FEATURES)
    assert html.count('<details class="privacy-details">') == len(build_site.PRIVACY_DETAILS)


def render_terms() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        build_site.render_terms_page(out)
        return (out / "terms" / "index.html").read_text(encoding="utf-8")


def test_terms_page_uses_the_same_design_as_privacy():
    html = render_terms()
    assert 'class="privacy-hero"' in html
    assert html.count('class="privacy-card"') == len(build_site.TERMS_CARDS)
    assert len(build_site.TERMS_CARDS) == len(build_site.PRIVACY_CARDS)
    assert html.count('<details class="privacy-details">') == len(build_site.TERMS_SECTIONS)
    assert "<summary>1. Educational use only</summary>" in html
    assert build_site.PRIVACY_UPDATED in html


def test_terms_page_keeps_consumer_rights_and_contact():
    html = render_terms()
    assert "rights you have as a consumer" in html
    assert "support@yaaddi.com" in html


# The app bundles the same two documents (app/src/i18n/locales/en/{terms,privacy}.json, shown by
# LegalScreen). This guard fails when the website text changes without the app copy following.
APP_LOCALES = Path(__file__).resolve().parents[2] / "app" / "src" / "i18n" / "locales" / "en"


def _plain(text: str) -> str:
    import html
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def test_app_bundled_documents_match_the_website():
    import json
    import pytest

    if not APP_LOCALES.is_dir():
        pytest.skip("app checkout not next to the catalog")
    for name, cards, sections in (
        ("privacy", build_site.PRIVACY_CARDS, build_site.PRIVACY_DETAILS),
        ("terms", build_site.TERMS_CARDS, build_site.TERMS_SECTIONS),
    ):
        app = json.loads((APP_LOCALES / f"{name}.json").read_text(encoding="utf-8"))
        assert app["updated"] == f"Last updated: {build_site.PRIVACY_UPDATED}", name
        assert [(c["title"], c["text"]) for c in app["cards"]] == [(_plain(t), _plain(x)) for _, t, x in cards], name
        assert [(s["title"], s["body"]) for s in app["sections"]] == [(_plain(t), _plain(b)) for t, b in sections], name
    features = json.loads((APP_LOCALES / "privacy.json").read_text(encoding="utf-8"))["features"]
    assert [f["name"] for f in features] == [_plain(f[0]) for f in build_site.PRIVACY_FEATURES]
