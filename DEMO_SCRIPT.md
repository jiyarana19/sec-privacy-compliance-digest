# Demo Video Script — Security, Privacy & Compliance Digest

**Target length:** 90–120 seconds. Record your screen on the live Hugging
Face Space URL, not localhost — Sakshi should see the same thing a stranger
clicking your link would see.

Before recording: click **Run Digest Now** once so the dashboard already has
data, then reload the page so your recording starts on a populated screen
instead of an empty state.

---

### 0:00–0:10 — Cold open on the problem

*(Show the empty/loading dashboard for one second, then cut to populated view)*

> "Security, privacy, and compliance teams are drowning in feeds — the same
> story reported five different ways, no sense of what's actually urgent.
> This is an AI digest that fixes that."

### 0:10–0:30 — The masthead and the "why it matters" difference

*(Point at the case-file cards, then the "View as" toggle)*

> "Every story gets a priority stamp and a reference code — like a case file,
> not just a headline. And here's the part that makes it more than a
> summarizer: switch this to Compliance Officer..."

*(Click the "View as" toggle from Security Analyst → Compliance Officer)*

> "...and the 'why it matters' note changes. Same story, different guidance,
> because a SOC analyst and a compliance officer need different things from
> the same headline."

### 0:30–0:50 — Dedup and cross-category merge

*(Scroll to a card showing "Also reported by" or "Also filed under")*

> "It also collapses duplicate coverage — the same CVE reported by three
> outlets becomes one card, and if a breach story gets filed under both
> Security and Privacy feeds, it merges those too instead of showing it
> twice."

### 0:50–1:05 — Deadline Docket

*(Click "Deadline Docket" in the sidebar)*

> "Compliance stories often bury a hard date in the text — 'must comply by
> April 27' — so this pulls that out automatically into its own calendar
> view, sorted by urgency."

### 1:05–1:25 — Filtering and search

*(Back on Dashboard, demonstrate the priority filter defaulting to High+Medium, then type a search term)*

> "By default you're only seeing High and Medium priority — Low-priority
> noise is opt-in, not the default, because the whole point is triage."

### 1:25–1:40 — Settings (sources + watchlist)

*(Open Settings, show adding/removing an RSS source, show the watchlist textarea)*

> "Sources and watchlist keywords are fully editable from the dashboard —
> no code changes needed to point this at a different set of feeds."

### 1:40–1:55 — Close

*(Return to the Dashboard main view)*

> "It runs as a live Streamlit app, ships with a GitHub Actions workflow for
> daily automated runs and email delivery, and has an automated test suite
> covering the dedup and scoring logic. Repo and live link are below."

---

### Things to say out loud (credibility, not just features)
Briefly mention **one honest limitation** — this reads as more professional
than only listing wins:
> "Right now cross-category matching relies on shared identifiers like CVE
> IDs, so a duplicate story with no CVE mentioned could still show up twice
> — that's the next thing I'd improve."

### Recording checklist
- [ ] Recording the **live Space URL**, not localhost
- [ ] Dashboard has data before you hit record (ran the digest once already)
- [ ] Mic audio isn't clipping (test one sentence first)
- [ ] Screen resolution readable at 1080p — zoom browser to ~110% if text is small
- [ ] Uploaded to YouTube as **Unlisted** (not Private — Private links won't open for reviewers without being added individually)
