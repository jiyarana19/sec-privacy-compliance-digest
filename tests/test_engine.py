"""
Automated test suite for the digest engine.

Run with:
    pip install pytest --break-system-packages   # if not already installed
    pytest tests/ -v

These tests cover the logic that's easy to get subtly wrong: fuzzy
deduplication, cross-category merging via extracted identifiers,
idempotent storage, deadline extraction, and — importantly — that
untrusted RSS content can never inject raw HTML/JS into the dashboard
or the email digest.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from digest_engine import dedupe, scorer, storage, emailer, summarizer


def make_article(title, link, raw_summary, category, source="TestSource", hours_ago=0):
    return {
        "title": title,
        "link": link,
        "raw_summary": raw_summary,
        "published": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        "source": source,
        "category": category,
    }


# --------------------------------------------------------------- filtering
def test_filter_recent_excludes_old_articles():
    fresh = make_article("Fresh story", "https://a.com/1", "text", "security", hours_ago=1)
    stale = make_article("Old story", "https://a.com/2", "text", "security", hours_ago=48)
    result = dedupe.filter_recent([fresh, stale], hours=24)
    assert fresh in result
    assert stale not in result


# ------------------------------------------------------------ within-category dedupe
def test_within_category_duplicate_titles_merge():
    a = make_article("Critical zero-day hits Widget CMS", "https://a.com/1", "text", "security", source="Outlet A")
    b = make_article("Critical zero-day hits Widget CMS!", "https://a.com/1?utm=x", "text", "security", source="Outlet B")
    result = dedupe.deduplicate([a, b])
    assert len(result) == 1
    assert set(result[0]["also_reported_by"]) | {result[0]["source"]} == {"Outlet A", "Outlet B"}


def test_different_categories_do_not_fuzzy_merge_on_title_alone():
    a = make_article("New rule announced", "https://a.com/1", "no shared id here", "security")
    b = make_article("New rule announced", "https://b.com/2", "no shared id here either", "privacy")
    result = dedupe.deduplicate([a, b])
    # Same-ish title, different category, no shared identifier -> stays as two
    assert len(result) == 2


# ------------------------------------------------------------ cross-category dedupe
def test_cross_category_merge_via_shared_cve():
    sec = make_article(
        "Zero-day actively exploited", "https://a.com/1",
        "A critical flaw (CVE-2026-1234) is actively exploited.", "security", source="SecOutlet",
    )
    priv = make_article(
        "Regulators respond to data exposure", "https://b.com/2",
        "The incident tied to CVE-2026-1234 raises privacy concerns.", "privacy", source="PrivOutlet",
    )
    result = dedupe.deduplicate([sec, priv])
    assert len(result) == 1
    kept = result[0]
    assert "privacy" in kept["cross_categories"] or "security" in kept["cross_categories"]
    assert "CVE-2026-1234" in kept["identifiers"]


def test_identifier_not_lost_when_duplicate_copy_carries_it():
    # Regression test for the bug found during manual review: the canonical-link
    # short circuit previously dropped a duplicate's identifier before it could
    # be merged into the kept article.
    with_cve = make_article(
        "Widget CMS breach", "https://a.com/1?ref=x",
        "Tied to CVE-2026-9999.", "security", source="Outlet A",
    )
    without_cve = make_article(
        "Widget CMS breach", "https://a.com/1",
        "No identifier mentioned here.", "security", source="Outlet B",
    )
    result = dedupe.deduplicate([with_cve, without_cve])
    assert len(result) == 1
    assert "CVE-2026-9999" in result[0]["identifiers"]


# --------------------------------------------------------------------- scoring
@pytest.mark.parametrize("text,expected", [
    ("Critical zero-day actively exploited in the wild", "High"),
    ("New vulnerability patch released", "Medium"),
    ("Company publishes quarterly security newsletter", "Low"),
])
def test_priority_scoring(text, expected):
    article = make_article(text, "https://a.com/1", text, "security")
    assert scorer.score_priority(article) == expected


def test_watchlist_tagging_matches_whole_words_only():
    article = make_article("AWS outage affects customers", "https://a.com/1", "AWS had an issue", "security")
    matches = scorer.tag_watchlist(article, ["AWS", "GDPR"])
    assert matches == ["AWS"]


# ------------------------------------------------------------------- deadlines
@pytest.mark.parametrize("text,expected_date", [
    ("Companies must comply by April 27, 2027.", "2027-04-27"),
    ("Enforcement begins on June 1, 2026 for all covered entities.", "2026-06-01"),
    ("This is just a news update with no dates mentioned.", None),
])
def test_deadline_extraction(text, expected_date):
    assert scorer.extract_deadline(text) == expected_date


def test_deadline_survives_cross_category_merge():
    sec = make_article(
        "Widget CMS flaw disclosed", "https://a.com/1",
        "Tied to CVE-2026-5555, no compliance date mentioned.", "security",
    )
    compliance = make_article(
        "Regulator sets remediation window", "https://b.com/2",
        "Firms tied to CVE-2026-5555 must comply by May 1, 2027.", "compliance",
    )
    result = dedupe.deduplicate([sec, compliance])
    assert len(result) == 1
    assert result[0]["deadline"] == "2027-05-01"


# --------------------------------------------------------------------- storage
def test_save_digest_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    articles = [make_article("Story one", "https://a.com/1", "text", "security")]
    enriched = scorer.enrich(dedupe.deduplicate(articles), watchlist=[])
    enriched = summarizer.summarize_articles(enriched)

    storage.save_digest(enriched, path=db_path, run_date="2026-08-05")
    storage.save_digest(enriched, path=db_path, run_date="2026-08-05")  # run twice, same day

    rows = storage.get_digest("2026-08-05", path=db_path)
    assert len(rows) == 1  # not 2


def test_get_upcoming_deadlines_deduplicates_by_link(tmp_path):
    db_path = str(tmp_path / "test.db")
    article = make_article(
        "New compliance rule", "https://a.com/1",
        "Must comply by January 15, 2027.", "compliance",
    )
    enriched = scorer.enrich(dedupe.deduplicate([article]), watchlist=[])
    enriched = summarizer.summarize_articles(enriched)
    storage.save_digest(enriched, path=db_path, run_date="2026-08-05")

    deadlines = storage.get_upcoming_deadlines(path=db_path)
    assert len(deadlines) == 1
    assert deadlines[0]["deadline"] == "2027-01-15"


# ---------------------------------------------------------------------- safety
def test_email_html_escapes_malicious_feed_content():
    malicious = {
        "title": "<script>alert(1)</script>Fake headline",
        "link": "https://evil.com/1",
        "source": "Sketchy Source",
        "category": "security",
        "priority": "High",
        "summary": "<img src=x onerror=alert(1)>",
        "watchlist_matches": [],
        "why_it_matters": {"security": "<b>ignore this</b>"},
        "deadline": None,
    }
    output = emailer.build_html([malicious], "2026-08-05")
    assert "<script>alert(1)</script>" not in output
    assert "&lt;script&gt;" in output


def test_summarizer_fallback_works_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    article = make_article(
        "Ransomware group claims new victim", "https://a.com/1",
        "A ransomware gang has claimed a new victim in a fresh attack.", "security",
    )
    article["priority"] = scorer.score_priority(article)
    summarize = summarizer.get_summarizer()
    summary, why_it_matters = summarize(article)
    assert summary  # non-empty
    assert set(why_it_matters.keys()) == {"security", "privacy", "compliance"}


# ------------------------------------------------------- read/bookmark state
def test_mark_read_and_get_state_map(tmp_path):
    db_path = str(tmp_path / "test.db")
    storage.save_digest(
        [{"category": "security", "title": "t", "link": "https://a.com/1", "source": "S",
          "published": "2026-08-05", "priority": "High", "summary": "s"}],
        path=db_path, run_date="2026-08-05",
    )
    assert storage.get_state_map(["https://a.com/1"], path=db_path) == {}

    storage.mark_read("https://a.com/1", path=db_path)
    state = storage.get_state_map(["https://a.com/1"], path=db_path)
    assert state["https://a.com/1"] == {"read": True, "bookmarked": False}


def test_toggle_bookmark_flips_and_returns_new_value(tmp_path):
    db_path = str(tmp_path / "test.db")
    storage.save_digest(
        [{"category": "security", "title": "t", "link": "https://a.com/1", "source": "S",
          "published": "2026-08-05", "priority": "High", "summary": "s"}],
        path=db_path, run_date="2026-08-05",
    )
    assert storage.toggle_bookmark("https://a.com/1", path=db_path) is True
    assert storage.get_bookmarked(path=db_path)[0]["link"] == "https://a.com/1"
    assert storage.toggle_bookmark("https://a.com/1", path=db_path) is False
    assert storage.get_bookmarked(path=db_path) == []


def test_bookmarked_article_survives_being_absent_from_latest_run(tmp_path):
    """A bookmark should still resolve to something readable even if that
    link doesn't appear in the most recent digest run."""
    db_path = str(tmp_path / "test.db")
    storage.save_digest(
        [{"category": "privacy", "title": "Older story", "link": "https://a.com/old",
          "source": "S", "published": "2026-08-01", "priority": "Medium", "summary": "s"}],
        path=db_path, run_date="2026-08-01",
    )
    storage.toggle_bookmark("https://a.com/old", path=db_path)
    storage.save_digest(
        [{"category": "security", "title": "Newer, unrelated story", "link": "https://a.com/new",
          "source": "S", "published": "2026-08-05", "priority": "High", "summary": "s"}],
        path=db_path, run_date="2026-08-05",
    )
    saved = storage.get_bookmarked(path=db_path)
    assert len(saved) == 1
    assert saved[0]["title"] == "Older story"


# ------------------------------------------------------------------ PDF export
def test_pdf_export_produces_valid_pdf_bytes():
    from digest_engine.pdf_export import build_pdf
    articles = [
        {"category": "security", "priority": "High", "title": "Test headline",
         "source": "Source", "published": "2026-08-05", "summary": "Summary text.",
         "deadline": None, "link": "https://a.com/1"},
    ]
    pdf_bytes = build_pdf(articles, "2026-08-05")
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 500


def test_pdf_export_handles_unicode_and_empty_fields_without_crashing():
    from digest_engine.pdf_export import build_pdf
    tricky = [
        {"category": "privacy", "priority": "Medium",
         "title": "Company \u2018confirms\u2019 breach \u2014 users affected",
         "source": "", "published": "", "summary": "", "deadline": "2026-06-01",
         "link": "https://a.com/2"},
        {"category": "compliance", "priority": "Low", "title": "No link article",
         "source": "S", "published": "2026-08-05", "summary": "s", "deadline": None, "link": ""},
    ]
    pdf_bytes = build_pdf(tricky, "2026-08-05")  # should not raise
    assert pdf_bytes[:5] == b"%PDF-"


def test_pdf_export_paginates_large_digests():
    from digest_engine.pdf_export import build_pdf
    from pypdf import PdfReader
    import io
    articles = [
        {"category": ["security", "privacy", "compliance"][i % 3], "priority": "Medium",
         "title": f"Article {i} with a moderately long headline for wrapping purposes",
         "source": "Source", "published": "2026-08-05",
         "summary": "A summary long enough to occupy multiple lines in the rendered PDF output.",
         "deadline": None, "link": f"https://a.com/{i}"}
        for i in range(25)
    ]
    pdf_bytes = build_pdf(articles, "2026-08-05")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) > 1


# ------------------------------------------------------------- watchlist alerts
def test_watchlist_match_detectable_for_alert_banner(tmp_path):
    """The dashboard's alert banner filters on non-empty watchlist_matches —
    confirm that field actually gets populated end to end through the
    normal enrich pipeline, not just in scorer's own unit tests."""
    db_path = str(tmp_path / "test.db")
    article = make_article(
        "Acme Corp discloses new vulnerability", "https://a.com/1",
        "Acme Corp's product was found vulnerable.", "security",
    )
    enriched = scorer.enrich(dedupe.deduplicate([article]), watchlist=["Acme Corp"])
    enriched = summarizer.summarize_articles(enriched)
    storage.save_digest(enriched, path=db_path, run_date="2026-08-05")

    saved = storage.get_digest("2026-08-05", path=db_path)
    assert saved[0]["watchlist_matches"] == ["Acme Corp"]


# --------------------------------------------------------------- subscribers
def test_add_subscriber_normalizes_and_dedupes(tmp_path):
    db_path = str(tmp_path / "test.db")
    storage.add_subscriber("  Test@Example.com  ", path=db_path)
    storage.add_subscriber("test@example.com", path=db_path)  # same, different case/whitespace
    assert storage.get_subscribers(path=db_path) == ["test@example.com"]


def test_remove_subscriber(tmp_path):
    db_path = str(tmp_path / "test.db")
    storage.add_subscriber("a@x.com", path=db_path)
    storage.add_subscriber("b@x.com", path=db_path)
    storage.remove_subscriber("a@x.com", path=db_path)
    assert storage.get_subscribers(path=db_path) == ["b@x.com"]
