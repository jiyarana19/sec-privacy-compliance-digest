# Manual Test Plan

Run through this on the **live Hugging Face Space** before recording your
demo video — catching a broken button on camera is worse than catching it
now. Each row: do the action, confirm the expected result, tick it off.

Automated coverage for the underlying logic (dedup, scoring, deadlines,
idempotent storage, HTML-escaping) lives in `tests/test_engine.py` — run
`pytest tests/ -v` locally before you deploy. This checklist covers the
things only a human clicking through the UI can verify.

## 1. First load / empty state
| # | Action | Expected result |
|---|---|---|
| 1.1 | Open the live Space URL with no digest run yet | Dashboard shows "No briefing on file yet" message, not an error or blank page |
| 1.2 | Click **Run Digest Now** | Spinner appears, then a success message with today's date, page refreshes with data |

## 2. Dashboard core
| # | Action | Expected result |
|---|---|---|
| 2.1 | Load dashboard with data present | Metric strip (Articles / High priority / Categories / Sources) shows non-zero numbers |
| 2.2 | Check default Priority filter | Only **High** and **Medium** are pre-selected, **Low** is not |
| 2.3 | Select "Low" in the priority filter | Low-priority cards appear |
| 2.4 | Deselect all priorities | "Nothing matches these filters" message appears, no crash |
| 2.5 | Type a keyword in Search that matches nothing | Same "nothing matches" message, no crash |
| 2.6 | Type a keyword that matches a real title/summary | Only matching cards remain |
| 2.7 | Toggle "View as" between the three personas | The "Why it matters" line on each card changes text |
| 2.8 | Click an article title link | Opens the source article in a new tab |
| 2.9 | Run the digest twice in a row (click Run Digest Now, wait, click again) | Article count does **not** double — this was a real bug, worth explicitly re-checking on the live deployment |

## 3. Deadline Docket
| # | Action | Expected result |
|---|---|---|
| 3.1 | Open Deadline Docket with no dated items in current coverage | "No dated obligations detected" message, no crash |
| 3.2 | Open Deadline Docket after a digest with a compliance deadline has run | Item appears under "Upcoming" with a parsed date, not raw text like "next month" |
| 3.3 | Check a deadline that's already passed | Appears inside the collapsed "Past deadlines" expander, not mixed into Upcoming |

## 4. Archive & Trends
| # | Action | Expected result |
|---|---|---|
| 4.1 | Open Archive & Trends after 2+ digest runs on different dates | Line chart renders with a line per category |
| 4.2 | Select an older date from the dropdown | Table below updates to that date's articles |

## 5. Settings
| # | Action | Expected result |
|---|---|---|
| 5.1 | Add a new RSS source under any category | Appears in the list immediately, persists after page refresh |
| 5.2 | Remove a source | Disappears immediately |
| 5.3 | Edit the watchlist textarea and save | Success message shown; next digest run reflects new watchlist tags |
| 5.4 | Click "Send test digest email now" with no SMTP secrets configured | Clear error message ("check SMTP settings"), not a stack trace |

## 6. Cross-cutting / security
| # | Action | Expected result |
|---|---|---|
| 6.1 | Confirm no article card renders raw HTML from a feed (e.g. no unexpected bold/links inside a summary that shouldn't be there) | Summaries render as plain text only |
| 6.2 | Reload the page mid-session | No crash, state (digest data) persists since it's stored in SQLite, not session memory |

## Sign-off
Once every row above is checked, you're clear to record. If anything fails,
fix it and re-run **all** rows in that section, not just the one that broke —
a fix in Settings, for example, can affect what Dashboard renders next.
