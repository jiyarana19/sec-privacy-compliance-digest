"""Rule-based priority scoring, watchlist tagging, identifier extraction,
and deadline extraction.

Kept rule-based (not LLM-based) on purpose: it's free, instant, fully
explainable to a compliance/security reviewer, and doesn't depend on
an API key being configured.
"""
import re
from datetime import datetime
from dateutil import parser as dateparser

HIGH_KEYWORDS = [
    "zero-day", "zero day", "actively exploited", "critical vulnerability",
    "ransomware", "data breach", "breach", "emergency patch", "critical flaw",
    "in the wild", "rce", "remote code execution", "enforcement action",
    "record fine", "criminal charges",
]

MEDIUM_KEYWORDS = [
    "vulnerability", "patch", "update", "warning", "advisory", "fine",
    "penalty", "lawsuit", "investigation", "settlement", "new regulation",
    "proposed rule", "audit",
]

# Cross-category dedup relies on shared identifiers like CVE IDs — a breach
# story filed under both "security" and "privacy" feeds will carry the same
# CVE even if the headlines are worded completely differently.
CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)

# Compliance items often carry a hard date buried in prose ("effective
# April 27, 2027", "must comply by 6/1/2026", "deadline is April 22, 2026",
# "Enforcement begins on June 1, 2026"). re.IGNORECASE matters here more than
# it might look — these cue phrases very often open a sentence ("Enforcement
# begins...") and would otherwise never match their lowercase pattern. The
# connector group also has to tolerate ordinary phrasing ("deadline is",
# "effective as of"), not just a single "on"/"of"/":".
DEADLINE_CUES = re.compile(
    r"(?:deadline|effective|due (?:date|by)|compliance date|enforcement begins|"
    r"must comply by|takes effect|by)"
    r"\s*(?:is|are|set for|scheduled for|as of|on|of|:)?\s*"
    r"([A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)


def score_priority(article):
    text = f"{article['title']} {article.get('raw_summary', '')}".lower()
    if any(k in text for k in HIGH_KEYWORDS):
        return "High"
    if any(k in text for k in MEDIUM_KEYWORDS):
        return "Medium"
    return "Low"


def tag_watchlist(article, watchlist):
    text = f"{article['title']} {article.get('raw_summary', '')}"
    matches = []
    for term in watchlist:
        if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
            matches.append(term)
    return matches


def extract_identifiers(text):
    """Extract stable identifiers (currently CVE IDs) used for
    cross-category and cross-source deduplication."""
    return sorted({m.upper() for m in CVE_PATTERN.findall(text or "")})


def extract_deadline(text):
    """Return an ISO date string (YYYY-MM-DD) if a compliance-style
    deadline phrase is found and parses cleanly, else None. Returning
    None (not the raw string) keeps the field reliably sortable —
    unparsed date-like text is treated as no deadline rather than a
    fuzzy one.
    """
    m = DEADLINE_CUES.search(text or "")
    if not m:
        return None
    raw = m.group(1)
    try:
        parsed = dateparser.parse(raw, fuzzy=True, default=datetime(datetime.now().year, 1, 1))
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return None


def enrich(articles, watchlist):
    for a in articles:
        text = f"{a['title']} {a.get('raw_summary', '')}"
        a["priority"] = score_priority(a)
        a["watchlist_matches"] = tag_watchlist(a, watchlist)
        a.setdefault("identifiers", extract_identifiers(text))
        # setdefault (not overwrite) so a deadline already carried forward
        # from a merged duplicate in dedupe.py — found in text that didn't
        # survive as the kept article's own title/summary — isn't lost.
        a.setdefault("deadline", None)
        if not a["deadline"]:
            a["deadline"] = extract_deadline(text)
    return articles
