"""Recency filtering, within-category deduplication, and cross-category
identifier-based merging.

Multiple outlets often cover the same story within hours of each other,
and a single incident (e.g. a breach) is frequently filed under more
than one feed category (security AND privacy). This module collapses
both kinds of duplication instead of showing the same story 2-3 times.
"""
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse

from digest_engine.scorer import extract_identifiers, extract_deadline


def filter_recent(articles, hours=24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [a for a in articles if a["published"] >= cutoff]


def _canonical_link(link):
    p = urlparse(link)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def _similar(a, b, threshold=0.85):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


def _dedupe_within_category(articles):
    """Fuzzy-match near-identical headlines within the same category.

    Identifiers must already be set on every article before this runs —
    when two near-duplicates merge, we union their identifiers so a CVE
    mentioned in only the discarded copy isn't lost (which would silently
    break the cross-category merge that runs next).
    """
    kept = []

    for art in articles:
        link_key = _canonical_link(art["link"])

        duplicate_of = None
        for k in kept:
            if k["category"] != art["category"]:
                continue
            if _canonical_link(k["link"]) == link_key or _similar(k["title"], art["title"]):
                duplicate_of = k
                break

        if duplicate_of:
            extra_sources = duplicate_of.setdefault("also_reported_by", [])
            if art["source"] not in extra_sources and art["source"] != duplicate_of["source"]:
                extra_sources.append(art["source"])
            duplicate_of["identifiers"] = sorted(
                set(duplicate_of.get("identifiers", [])) | set(art.get("identifiers", []))
            )
            # A deadline phrase might only appear in the duplicate's text
            # (e.g. one outlet's writeup mentions the compliance date, another
            # doesn't) — don't let the discarded copy silently take it with it.
            if not duplicate_of.get("deadline") and art.get("deadline"):
                duplicate_of["deadline"] = art["deadline"]
            continue

        art.setdefault("also_reported_by", [])
        kept.append(art)

    return kept


def _merge_cross_category(articles):
    """Merge entries that share an extracted identifier (currently CVE IDs)
    across *different* categories — the same incident is often filed under
    both Security and Privacy feeds with completely different headlines,
    so title similarity alone would never catch it.
    """
    skip = set()
    for i, a in enumerate(articles):
        if i in skip or not a["identifiers"]:
            continue
        for j in range(i + 1, len(articles)):
            if j in skip:
                continue
            b = articles[j]
            if b["category"] == a["category"]:
                continue
            if set(a["identifiers"]) & set(b["identifiers"]):
                if b["category"] not in a["cross_categories"]:
                    a["cross_categories"].append(b["category"])
                extra_sources = a.setdefault("also_reported_by", [])
                if b["source"] not in extra_sources and b["source"] != a["source"]:
                    extra_sources.append(b["source"])
                if not a.get("deadline") and b.get("deadline"):
                    a["deadline"] = b["deadline"]
                skip.add(j)

    return [a for i, a in enumerate(articles) if i not in skip]


def deduplicate(articles):
    articles = sorted(articles, key=lambda a: a["published"], reverse=True)
    for a in articles:
        text = f"{a['title']} {a.get('raw_summary', '')}"
        a.setdefault("identifiers", extract_identifiers(text))
        a.setdefault("deadline", extract_deadline(text))
        a.setdefault("cross_categories", [])
        a.setdefault("also_reported_by", [])
    articles = _dedupe_within_category(articles)
    articles = _merge_cross_category(articles)
    return articles
