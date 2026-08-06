"""CLI entry point: fetch, process, store, and optionally email the digest.

Usage:
    python generate_digest.py                 # last 24h, save only
    python generate_digest.py --email          # also send the email digest
    python generate_digest.py --hours 48       # wider lookback window
"""
import argparse
from dotenv import load_dotenv

load_dotenv()  # populates os.environ from a local .env file, if present

from digest_engine import feeds, dedupe, scorer, summarizer, storage, emailer


def run(hours=24, send_email=False, config_path="config/feeds.yaml"):
    config = feeds.load_feed_config(config_path)
    watchlist = config.get("watchlist", [])

    print("[run] Fetching feeds...")
    articles = feeds.fetch_all(config)
    print(f"[run] Fetched {len(articles)} raw articles")

    articles = dedupe.filter_recent(articles, hours=hours)
    articles = dedupe.deduplicate(articles)
    print(f"[run] {len(articles)} articles after filtering/dedupe")

    articles = scorer.enrich(articles, watchlist)
    articles = summarizer.summarize_articles(articles)

    run_date = storage.save_digest(articles)
    print(f"[run] Saved digest for {run_date}")

    if send_email:
        emailer.send_email(articles, run_date)

    return run_date, articles


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate security/privacy/compliance digest")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    parser.add_argument("--email", action="store_true", help="Send digest via email")
    parser.add_argument("--config", default="config/feeds.yaml")
    args = parser.parse_args()
    run(hours=args.hours, send_email=args.email, config_path=args.config)
