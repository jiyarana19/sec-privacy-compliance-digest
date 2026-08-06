"""Feed configuration loading and RSS fetching."""
import yaml
import feedparser
from datetime import datetime, timezone
from dateutil import parser as dateparser


def load_feed_config(path="config/feeds.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _parse_date(entry):
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                parsed = dateparser.parse(val)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except Exception:
                continue
    return datetime.now(timezone.utc)


def fetch_category(category, sources):
    """Fetch every RSS source configured for a category."""
    articles = []
    for src in sources:
        try:
            parsed = feedparser.parse(src["url"])
        except Exception as e:
            print(f"[feeds] failed to fetch {src['name']}: {e}")
            continue
        for entry in parsed.entries:
            articles.append({
                "title": (entry.get("title") or "").strip(),
                "link": (entry.get("link") or "").strip(),
                "raw_summary": (entry.get("summary") or entry.get("description") or "").strip(),
                "published": _parse_date(entry),
                "source": src["name"],
                "category": category,
            })
    return articles


def fetch_all(config):
    """Fetch security, privacy, and compliance feeds in one pass."""
    all_articles = []
    for category in ("security", "privacy", "compliance"):
        sources = config.get(category, [])
        all_articles.extend(fetch_category(category, sources))
    return all_articles
