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
    assert "Delete all my data" in html
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
