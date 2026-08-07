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
| **Summarize** | AI-generated 2-sentence neutral summary, plus three role-specific **"why it matters"** notes (Security Analyst / Privacy Officer / Compliance Officer) — switchable in the dashboard. Uses OpenAI, Anthropic, or Gemini (whichever key is set), and falls back to extractive summaries and templated persona notes if none are configured |
| **Alert** | Articles matching your watchlist surface in a dedicated alert banner at the top of the dashboard, regardless of the priority filter — so a keyword hit never gets hidden by a "Low priority" filter |
| **Deliver** | Live filterable dashboard, one-click **PDF export**, and an HTML email digest |
| **Track** | Mark articles read/unread and bookmark ("Save") them for later — a dedicated **Saved** page collects everything you've bookmarked across every past digest |
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
  filtering, plus an optional email digest for people who don't log in
  (see the note on email setup below).
- **Read/bookmark tracking** — mark articles read so a re-visit isn't a
  wall of the same cards, and save anything worth revisiting to a
  dedicated Saved page.
- **One-click PDF export** — download the current filtered view as a
  clean report, useful for sharing in a meeting without a login.
- **Works without any API key** — the AI summarizer has a built-in
  extractive fallback (including templated persona notes), so the app is
  fully functional out of the box and upgrades automatically once you add
  an `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`.

## Architecture

```
config/feeds.yaml        → sources per category + watchlist keywords
digest_engine/
  feeds.py                → RSS fetching
  dedupe.py                → recency filter + fuzzy deduplication
  scorer.py                → priority scoring + watchlist tagging
  summarizer.py             → AI summaries (OpenAI / Anthropic / Gemini / fallback)
  storage.py                → SQLite persistence, archive queries, read/bookmark state, subscribers
  emailer.py                → HTML digest + SMTP delivery
  pdf_export.py              → one-click PDF report generation
generate_digest.py        → CLI orchestrator (fetch → ... → store → email)
app.py                     → Streamlit dashboard (Dashboard / Deadline Docket / Saved / Archive & Trends / Settings)
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
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY` | Enables real AI summaries (checked in that order) | No — falls back to extractive summaries |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_HOST`, `SMTP_PORT` | The **sending** account for email delivery | No — dashboard and PDF export work fully without it |

**Who receives the email** is managed separately from the sending account —
anyone using the dashboard can type their email into **Settings → Email
delivery → Connect Email**, no config file or redeploy needed. This is
stored in `subscribers` in the SQLite database and is additive to (or a
replacement for) the older `DIGEST_RECIPIENTS` env variable approach.

> **Current status of this deployment:** email delivery is built and
> tested, but the sending account (`SMTP_USER`/`SMTP_PASSWORD`) has **not
> been configured** for the live demo — it wasn't required for this
> submission. The dashboard, PDF export, and every other feature work
> fully without it. To enable it, generate a Gmail
> [App Password](https://myaccount.google.com/apppasswords) and add the
> four SMTP variables above under the hosting platform's environment
> variables — takes about five minutes, no code changes needed.

## Deployment

### Option A — Render (used for the live demo of this project)
1. New Web Service → connect this GitHub repo. Render auto-detects the
   build/start commands from `render.yaml` in this repo.
2. Instance type: **Free**.
3. Add `GEMINI_API_KEY` (or `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`) under
   **Environment** for real AI summaries. SMTP variables are optional —
   see the note above.
4. Deploy — you get a public URL like
   `https://your-service.onrender.com`.

> Free tier spins down after ~15 minutes idle and takes 30–60s to wake
> back up on the next visit — open the app a couple of minutes before a
> demo so it's warm.

### Option B — Hugging Face Spaces
Note: Spaces' free tier only covers the **Static** SDK, which can't run
a Python/Streamlit backend — Gradio and Docker Spaces (which can) require
a paid plan on some accounts. Render (above) is the tested, fully-free
path for this project; use HF Spaces only if your account has Docker/
Gradio access.

### Option C — Streamlit Community Cloud
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
- Per-user custom watchlists (currently one shared watchlist per deployment)
- Swap SQLite for a hosted database (Supabase/Postgres/Turso) for true
  persistence across redeploys — see the architecture note above
