---
title: Security Privacy Compliance Digest
emoji: 🛡️
colorFrom: blue
colorTo: gray
sdk: streamlit
sdk_version: "1.36.0"
app_file: app.py
pinned: false
---

# 🛡️ Intelligent AI Digest for Security, Privacy & Compliance Feeds

An AI-curated dashboard that monitors security, privacy, and compliance
news across the web, removes duplicate coverage, ranks stories by
actual severity, and delivers a clean daily digest — as a live web
dashboard and by email.

Built for security, legal, and compliance teams who don't have time to
read 40 RSS feeds a day but can't afford to miss the one story that matters.

---

## Why this exists

Security, privacy, and compliance teams already have too many inputs:
CVE feeds, regulator press releases, breach reports, and legal
newsletters, spread across dozens of sources. The result is either
information overload or missed signal. This tool exists to solve three
specific problems:

1. **Signal vs. noise** — not every headline deserves the same attention.
   A critical, actively-exploited zero-day and a routine patch
   announcement should not look the same in an inbox.
2. **Duplicate coverage** — the same story often gets reported by 3–5
   outlets within hours. Reading it three times wastes time.
3. **One digest, three disciplines** — security, privacy, and compliance
   are usually tracked separately even though they constantly overlap
   (e.g. a breach is simultaneously a security incident, a privacy
   event, and a compliance/reporting obligation).

## What it does

| Stage | What happens |
|---|---|
| **Fetch** | Pulls RSS feeds across three tracks: Security, Privacy, Compliance (fully configurable in `config/feeds.yaml`) |
| **Filter** | Keeps only articles from the last 24 hours (configurable window) |
| **Deduplicate** | Fuzzy-matches near-identical headlines *within* a category, and merges stories that share an extracted identifier (currently CVE IDs) *across* categories — the same breach is often filed under both Security and Privacy feeds with completely different headlines |
| **Score** | Rule-based priority tagging — **High / Medium / Low** — based on severity language (e.g. "actively exploited", "data breach", "enforcement action") |
| **Extract deadlines** | Pulls hard dates out of prose (e.g. "must comply by April 27, 2027") into a structured field, surfaced in the dedicated **Deadline Docket** view |
| **Tag** | Flags articles matching a custom watchlist (e.g. `AWS`, `GDPR`, `HIPAA`, `ransomware`) so you can track what's relevant to *your* stack |
| **Summarize** | AI-generated 2-sentence neutral summary, plus three role-specific **"why it matters"** notes (Security Analyst / Privacy Officer / Compliance Officer) — switchable in the dashboard. Falls back to extractive summaries and templated persona notes if no API key is configured |
| **Deliver** | Live filterable dashboard **and** an HTML email digest |
| **Archive** | Every run is stored in SQLite (idempotent per day — re-running never duplicates rows) so you can browse history and see volume trends over time |

## What makes this different from a plain RSS-to-email bot

- **Prioritization**, not just aggregation — the dashboard defaults to
  High + Medium only; Low-priority items are an opt-in filter, not the
  first thing you see.
- **Cross-source *and* cross-category deduplication** — one CVE reported
  by three outlets, or filed under both Security and Privacy feeds with
  different headlines, becomes one card, not three.
- **Role-aware "why it matters"** — the same story reads differently for
  a SOC analyst chasing exposure than for a compliance officer tracking
  a filing deadline. Switch the "View as" toggle and every card's guidance
  updates.
- **Deadline extraction** — compliance items with a hard date get pulled
  into a dedicated Deadline Docket instead of staying buried in prose.
- **Personalization** — a watchlist lets each team highlight what's
  relevant to their environment.
- **Two delivery surfaces** — a live dashboard for daily browsing and
  filtering, plus an email digest for people who don't log in.
- **Works without any API key** — the AI summarizer has a built-in
  extractive fallback (including templated persona notes), so the app is
  fully functional out of the box and upgrades automatically once you add
  an `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

## Architecture

```
config/feeds.yaml        → sources per category + watchlist keywords
digest_engine/
  feeds.py                → RSS fetching
  dedupe.py                → recency filter + fuzzy deduplication
  scorer.py                → priority scoring + watchlist tagging
  summarizer.py             → AI summaries (OpenAI / Anthropic / fallback)
  storage.py                → SQLite persistence + archive queries
  emailer.py                → HTML digest + SMTP delivery
generate_digest.py        → CLI orchestrator (fetch → ... → store → email)
app.py                     → Streamlit dashboard (Dashboard / Archive & Trends / Settings)
.github/workflows/         → scheduled daily run + email via GitHub Actions
```

## Getting started locally

```bash
git clone <your-repo-url>
cd sec-privacy-compliance-digest
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp .env.example .env     # fill in API keys / SMTP settings if you want them
streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`).
Click **Run Digest Now** on first launch to populate the dashboard.

Running the CLI directly (useful for scheduled/automated runs):

```bash
python generate_digest.py --hours 24 --email
```

## Configuration

All feeds and the watchlist live in `config/feeds.yaml` — no code
changes needed to add/remove a source. You can also manage sources
and the watchlist from the **Settings** tab in the dashboard itself.

| Variable | Purpose | Required? |
|---|---|---|
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | Enables real AI summaries | No — falls back to extractive summaries |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`, `DIGEST_RECIPIENTS` | Enables email delivery | No — dashboard works without it |

## Deployment

### Option A — Hugging Face Spaces (recommended for a live demo)
1. Create a new Space → SDK: **Streamlit**.
2. Push this repo's contents to the Space's git remote (Spaces are git
   repos). Hugging Face will scaffold a `README.md` with required YAML
   frontmatter (`sdk: streamlit`, `app_file: app.py`) — keep that
   frontmatter and append this file's content below it.
3. Add `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / SMTP variables under
   **Space settings → Repository secrets** if you want AI summaries
   or email.
4. The Space builds automatically and gives you a public URL —
   this is your live demo link.

### Option B — Streamlit Community Cloud
1. Push this repo to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io), deploy from
   the repo, set `app.py` as the entry point.
3. Add secrets under **App settings → Secrets** using the same keys
   as `.env.example`.

### Automated daily runs + email
`.github/workflows/daily_digest.yml` runs the digest once a day via
GitHub Actions, sends the email, and commits the updated `digest.db`
back to the repo. Add the same secrets under
**Repo settings → Secrets and variables → Actions**.

> **Note on persistence:** SQLite is great for a portfolio/demo project,
> but a hosted platform's filesystem may reset on redeploy. For a
> production deployment, swap `digest_engine/storage.py` for a hosted
> database (e.g. Supabase/Postgres or Turso) — the function signatures
> are designed to make that a drop-in change.

## Roadmap ideas
- Slack/Teams delivery alongside email
- LLM-assisted priority scoring layered on top of the rule-based scorer
- Per-user saved watchlists and digest preferences
- "Mark as reviewed" workflow for compliance audit trails
