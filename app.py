from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import html as html_lib
from datetime import date

import yaml

from digest_engine import storage
from digest_engine.pdf_export import build_pdf
from generate_digest import run as run_digest

st.set_page_config(page_title="Security, Privacy & Compliance Digest", page_icon="🛡️", layout="wide")


def render_html(fragment: str):
    """Render a raw HTML fragment via st.markdown, safely.

    Streamlit's markdown renderer follows CommonMark, which has two traps for
    multi-line f-string HTML templates like the ones below:
      1. A blank line inside a raw-HTML block ends that block early — and an
         empty f-string substitution (e.g. no deadline for this article) can
         leave a line that's blank apart from whitespace.
      2. Once back in normal Markdown parsing, any line starting with 4+
         spaces is read as an indented code block — which Python's own
         function-body indentation puts on *every* line of these templates.
      Together: an empty {variable} on its own line silently turns everything
      after it into literal escaped text instead of rendered HTML (exactly
      what caused the <span> priority stamps to leak as visible tags).
      Stripping each line and dropping empty ones avoids both failure modes.
    """
    cleaned = "\n".join(line.strip() for line in fragment.strip().splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)

PRIORITY_STAMP = {"High": "stamp-high", "Medium": "stamp-medium", "Low": "stamp-low"}
CATEGORY_ICONS = {"security": "🛡️", "privacy": "🔒", "compliance": "📋"}
CATEGORY_PREFIX = {"security": "SEC", "privacy": "PRV", "compliance": "CMP"}
PERSONA_LABELS = {"security": "Security Analyst", "privacy": "Privacy Officer", "compliance": "Compliance Officer"}


# ------------------------------------------------------------------ styling
def inject_css():
    render_html("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
      --ink: #10161D;
      --paper: #F6F4EF;
      --panel: #FBFAF7;
      --steel-600: #3E4C5A;
      --steel-300: #B8C2CB;
      --line: #D8D3C7;
      --signal-high: #A32C21;
      --signal-medium: #9C6B14;
      --signal-low: #2E5E45;
      --accent-navy: #1B3A5C;
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: var(--paper); }

    .briefing-masthead { border-bottom: 1px solid var(--ink); padding-bottom: 14px; margin-bottom: 10px; }
    .briefing-eyebrow {
      font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 0.18em;
      color: var(--steel-600); text-transform: uppercase;
    }
    .briefing-title {
      font-family: 'Source Serif 4', serif; font-weight: 700; font-size: 34px;
      color: var(--ink); margin: 4px 0 6px 0; line-height: 1.15;
    }
    .briefing-meta { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--steel-600); }

    section[data-testid="stSidebar"] { background: var(--ink); }
    section[data-testid="stSidebar"] * { color: var(--paper) !important; }
    section[data-testid="stSidebar"] label { font-family: 'IBM Plex Mono', monospace !important; letter-spacing: 0.03em; }

    div[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-radius: 2px; padding: 10px 14px; }
    div[data-testid="stMetricLabel"] {
      font-family: 'IBM Plex Mono', monospace !important; text-transform: uppercase;
      font-size: 10.5px !important; letter-spacing: 0.08em; color: var(--steel-600) !important;
    }
    div[data-testid="stMetricValue"] { font-family: 'Source Serif 4', serif !important; color: var(--ink) !important; }

    h1, h3 { font-family: 'Source Serif 4', serif !important; color: var(--ink) !important; }
    h3 { border-bottom: 1px solid var(--line); padding-bottom: 6px; }

    .case-card { background: var(--panel); border: 1px solid var(--line); border-radius: 2px; padding: 14px 16px; margin-bottom: 4px; }
    .case-card-read { opacity: 0.5; }
    .case-card-bookmarked { border-left: 3px solid var(--accent-navy); }
    .case-card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
    .case-ref { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--steel-600); letter-spacing: 0.04em; }
    .case-header-stamps { display: flex; gap: 6px; align-items: center; }
    .stamp {
      display: inline-block; font-family: 'IBM Plex Mono', monospace; font-size: 10px; font-weight: 600;
      letter-spacing: 0.12em; text-transform: uppercase; padding: 2px 8px;
      border: 1.5px solid currentColor; border-radius: 2px; transform: rotate(-1.5deg);
    }
    .stamp-high { color: var(--signal-high); }
    .stamp-medium { color: var(--signal-medium); }
    .stamp-low { color: var(--signal-low); }
    .stamp-deadline { color: var(--accent-navy); transform: rotate(1.5deg); }

    .case-title { font-family: 'Inter', sans-serif; font-weight: 600; font-size: 15.5px; color: var(--ink); text-decoration: none; }
    .case-title:hover { text-decoration: underline; }
    .case-source { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--steel-600); margin-left: 8px; }
    .case-summary { font-size: 13.5px; color: var(--steel-600); margin: 8px 0; line-height: 1.5; }
    .case-why { font-size: 12.5px; color: var(--accent-navy); font-style: italic; margin: 0 0 8px 0; line-height: 1.4; }
    .case-tags span {
      font-family: 'IBM Plex Mono', monospace; font-size: 10.5px; border: 1px solid var(--line);
      border-radius: 2px; padding: 1px 6px; margin-right: 5px; color: var(--accent-navy);
    }
    .case-also { font-family: 'IBM Plex Mono', monospace; font-size: 10.5px; color: var(--steel-300); margin-top: 6px; }

    .stButton>button { border-radius: 2px; border: 1px solid var(--ink); font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; }
    </style>
    """)


def masthead(eyebrow, title, meta=""):
    meta_html = f'<div class="briefing-meta">{meta}</div>' if meta else ""
    render_html(f"""
    <div class="briefing-masthead">
      <div class="briefing-eyebrow">{eyebrow}</div>
      <div class="briefing-title">{title}</div>
      {meta_html}
    </div>
    """)


def render_case_card(a, ref, persona_key, show_deadline=True, state=None):
    state = state or {"read": False, "bookmarked": False}
    link_raw = a["link"]

    stamp_class = PRIORITY_STAMP.get(a["priority"], "stamp-low")
    title = html_lib.escape(str(a["title"]))
    source = html_lib.escape(str(a["source"]))
    summary = html_lib.escape(str(a["summary"]))
    link = html_lib.escape(str(link_raw), quote=True)
    tags_html = "".join(f"<span>{html_lib.escape(str(t))}</span>" for t in a["watchlist_matches"])

    why = a.get("why_it_matters") or {}
    why_text = why.get(persona_key, "") if isinstance(why, dict) else ""
    why_html = (
        f'<p class="case-why">Why it matters ({PERSONA_LABELS[persona_key]}): {html_lib.escape(why_text)}</p>'
        if why_text else ""
    )

    notes = []
    if a.get("also_reported_by"):
        notes.append(f'Also reported by: {html_lib.escape(", ".join(a["also_reported_by"]))}')
    if a.get("cross_categories"):
        notes.append(f'Also filed under: {html_lib.escape(", ".join(a["cross_categories"]))}')
    also_html = f'<div class="case-also">{" · ".join(notes)}</div>' if notes else ""

    deadline_html = ""
    if show_deadline and a.get("deadline"):
        deadline_html = f'<span class="stamp stamp-deadline">Deadline {html_lib.escape(str(a["deadline"]))}</span>'

    card_classes = "case-card"
    if state["read"]:
        card_classes += " case-card-read"
    if state["bookmarked"]:
        card_classes += " case-card-bookmarked"

    render_html(f"""
    <div class="{card_classes}">
      <div class="case-card-header">
        <span class="case-ref">{html_lib.escape(str(ref))}</span>
        <span class="case-header-stamps">
          {deadline_html}
          <span class="stamp {stamp_class}">{html_lib.escape(a['priority'])} priority</span>
        </span>
      </div>
      <div>
        <a href="{link}" target="_blank" class="case-title">{title}</a>
        <span class="case-source">{source}</span>
      </div>
      <p class="case-summary">{summary}</p>
      {why_html}
      <div class="case-tags">{tags_html}</div>
      {also_html}
    </div>
    """)

    # Compact action row right under the card — read/bookmark state is
    # global per-link (see storage.get_state_map), so toggling here affects
    # this article everywhere it appears, not just in this list.
    btn_col1, btn_col2, spacer = st.columns([1.3, 1.3, 5])
    with btn_col1:
        read_label = "\u2713 Read" if state["read"] else "Mark read"
        if st.button(read_label, key=f"read_{ref}_{link_raw}", use_container_width=True):
            storage.mark_read(link_raw, not state["read"])
            st.rerun()
    with btn_col2:
        bm_label = "\u2605 Saved" if state["bookmarked"] else "\u2606 Save"
        if st.button(bm_label, key=f"bm_{ref}_{link_raw}", use_container_width=True):
            storage.toggle_bookmark(link_raw)
            st.rerun()


def load_config():
    with open("config/feeds.yaml", "r") as f:
        return yaml.safe_load(f)


def save_config(config):
    with open("config/feeds.yaml", "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)


inject_css()

st.sidebar.markdown("### Digest Control")
page = st.sidebar.radio("Navigate", ["Dashboard", "Deadline Docket", "Saved", "Archive & Trends", "Settings"])

# ---------------------------------------------------------------- Dashboard
if page == "Dashboard":
    masthead("Daily Briefing", "Security, Privacy & Compliance Digest", "")

    dates = storage.get_available_dates()

    col_btn1, col_btn2, col_date, spacer = st.columns([1.3, 1.3, 1.8, 2.6])
    with col_btn1:
        if st.button("Run Digest Now", use_container_width=True):
            with st.spinner("Fetching feeds and summarizing..."):
                run_date, _ = run_digest(hours=24, send_email=False)
            st.success(f"Digest updated for {run_date}")
            st.rerun()

    if not dates:
        st.info("No briefing on file yet. Click **Run Digest Now** to pull today's coverage.")
        st.stop()

    with col_date:
        # A dropdown only earns its place once there's actually more than one
        # date to pick between — with a single date it's just clutter, so we
        # show it as a plain label instead.
        if len(dates) > 1:
            selected_date = st.selectbox("Digest date", dates, index=0, label_visibility="collapsed")
        else:
            selected_date = dates[0]
            st.caption(f"Briefing date: {selected_date}")

    with col_btn2:
        _pdf_articles = storage.get_digest(selected_date)
        if _pdf_articles:
            st.download_button(
                "\U0001F4C4 Export PDF", data=build_pdf(_pdf_articles, selected_date),
                file_name=f"digest_{selected_date}.pdf", mime="application/pdf",
                use_container_width=True,
            )

    persona_choice = st.radio("View as", list(PERSONA_LABELS.values()), horizontal=True)
    persona_key = [k for k, v in PERSONA_LABELS.items() if v == persona_choice][0]

    articles = storage.get_digest(selected_date)
    df = pd.DataFrame(articles)

    all_links = df["link"].tolist() if not df.empty else []
    state_map = storage.get_state_map(all_links)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Articles", len(df))
    m2.metric("High priority", int((df["priority"] == "High").sum()) if not df.empty else 0)
    m3.metric("Categories", df["category"].nunique() if not df.empty else 0)
    m4.metric("Sources", df["source"].nunique() if not df.empty else 0)
    m5.metric("Saved", sum(1 for s in state_map.values() if s["bookmarked"]))

    # Watchlist alerts — surfaced above the normal filtered view regardless
    # of the priority/category filters below, since a watchlist keyword hit
    # (e.g. your own company name) matters even if it landed as Low priority.
    if not df.empty:
        watchlist_hits = df[df["watchlist_matches"].apply(lambda m: len(m) > 0)]
        if not watchlist_hits.empty:
            with st.expander(f"\U0001F514 {len(watchlist_hits)} article(s) match your watchlist keywords", expanded=False):
                for idx, (_, a) in enumerate(watchlist_hits.iterrows(), start=1):
                    render_case_card(a, f"ALERT-{idx:03d}", "security", state=state_map.get(a["link"]))

    st.divider()

    f1, f2, f3 = st.columns([2, 2, 3])
    with f1:
        # Default to High + Medium only — the whole pitch of this digest is
        # triage-first, so Low-priority noise is an opt-in, not the default view.
        priority_filter = st.multiselect("Priority", ["High", "Medium", "Low"], default=["High", "Medium"])
    with f2:
        category_filter = st.multiselect(
            "Category", ["security", "privacy", "compliance"],
            default=["security", "privacy", "compliance"],
        )
    with f3:
        search = st.text_input("Search keyword", "")

    filtered = df[df["priority"].isin(priority_filter) & df["category"].isin(category_filter)] if not df.empty else df
    if search and not filtered.empty:
        filtered = filtered[
            filtered["title"].str.contains(search, case=False, na=False)
            | filtered["summary"].str.contains(search, case=False, na=False)
        ]

    if filtered.empty:
        st.warning("Nothing matches these filters. Widen the filters or clear the search.")

    for category in ["security", "privacy", "compliance"]:
        cat_items = filtered[filtered["category"] == category] if not filtered.empty else filtered
        if cat_items.empty:
            continue
        st.subheader(f"{CATEGORY_ICONS[category]} {category.capitalize()} ({len(cat_items)})")
        for idx, (_, a) in enumerate(cat_items.iterrows(), start=1):
            ref = f"{CATEGORY_PREFIX[category]}-{idx:03d}"
            render_case_card(a, ref, persona_key, state=state_map.get(a["link"]))

# ------------------------------------------------------------- Deadline Docket
elif page == "Deadline Docket":
    masthead("Compliance Calendar", "Deadline Docket", "")

    deadlines = storage.get_upcoming_deadlines()
    if not deadlines:
        st.info("No dated obligations detected in coverage yet — this fills in automatically as digests run.")
        st.stop()

    today_str = date.today().isoformat()
    upcoming = [d for d in deadlines if d["deadline"] >= today_str]
    past = [d for d in deadlines if d["deadline"] < today_str]

    _dd_state = storage.get_state_map([d["link"] for d in deadlines])

    st.subheader(f"Upcoming ({len(upcoming)})")
    if not upcoming:
        st.info("No upcoming deadlines detected in current coverage.")
    for d in upcoming:
        render_case_card(d, d["deadline"], "compliance", show_deadline=False, state=_dd_state.get(d["link"]))

    if past:
        with st.expander(f"Past deadlines ({len(past)})"):
            for d in past:
                render_case_card(d, d["deadline"], "compliance", show_deadline=False, state=_dd_state.get(d["link"]))

# ---------------------------------------------------------------------- Saved
elif page == "Saved":
    masthead("Reading List", "Saved Articles", "")

    saved = storage.get_bookmarked()
    if not saved:
        st.info("Nothing saved yet — click the \u2606 Save button on any article to add it here.")
        st.stop()

    saved_state = storage.get_state_map([a["link"] for a in saved])
    for idx, a in enumerate(saved, start=1):
        render_case_card(a, f"SAVED-{idx:03d}", "security", state=saved_state.get(a["link"]))


# ---------------------------------------------------------- Archive & Trends
elif page == "Archive & Trends":
    masthead("Records Room", "Archive & Trends", "")

    dates = storage.get_available_dates()
    if not dates:
        st.info("No history yet — run a digest first from the Dashboard tab.")
        st.stop()

    stats = storage.get_stats_by_date()
    if stats:
        stats_df = pd.DataFrame(stats, columns=["run_date", "category", "count"])
        pivot = stats_df.pivot(index="run_date", columns="category", values="count").fillna(0)
        st.line_chart(pivot)

    st.subheader("Browse a past digest")
    chosen = st.selectbox("Date", dates)
    hist = pd.DataFrame(storage.get_digest(chosen))
    if not hist.empty:
        st.dataframe(
            hist[["category", "priority", "title", "source", "published", "deadline"]],
            use_container_width=True, hide_index=True,
        )

# ---------------------------------------------------------------- Settings
elif page == "Settings":
    masthead("Configuration", "Settings", "")

    config = load_config()

    st.subheader("RSS sources")
    for category in ["security", "privacy", "compliance"]:
        with st.expander(f"{CATEGORY_ICONS[category]} {category.capitalize()} sources ({len(config.get(category, []))})"):
            sources = config.get(category, [])
            for i, src in enumerate(sources):
                c1, c2, c3 = st.columns([2, 4, 1])
                c1.write(src["name"])
                c2.write(src["url"])
                if c3.button("Remove", key=f"rm_{category}_{i}"):
                    sources.pop(i)
                    config[category] = sources
                    save_config(config)
                    st.rerun()
            new_name = st.text_input(f"New source name ({category})", key=f"name_{category}")
            new_url = st.text_input(f"New feed URL ({category})", key=f"url_{category}")
            if st.button(f"Add to {category}", key=f"add_{category}") and new_name and new_url:
                config.setdefault(category, []).append({"name": new_name, "url": new_url})
                save_config(config)
                st.rerun()

    st.subheader("Watchlist keywords")
    watchlist = config.get("watchlist", [])
    wl_text = st.text_area("One per line", "\n".join(watchlist), height=150)
    if st.button("Save watchlist"):
        config["watchlist"] = [w.strip() for w in wl_text.splitlines() if w.strip()]
        save_config(config)
        st.success("Watchlist updated.")

    st.subheader("Email delivery")
    subscribers = storage.get_subscribers()

    ec1, ec2 = st.columns([4, 1])
    with ec1:
        new_email = st.text_input("Your email", label_visibility="collapsed", placeholder="you@company.com")
    with ec2:
        if st.button("Connect Email", use_container_width=True) and new_email and "@" in new_email:
            storage.add_subscriber(new_email)
            st.rerun()

    if subscribers:
        for email in subscribers:
            r1, r2 = st.columns([5, 1])
            r1.write(email)
            if r2.button("Remove", key=f"unsub_{email}"):
                storage.remove_subscriber(email)
                st.rerun()

    if st.button("Send digest now"):
        dates = storage.get_available_dates()
        if not dates:
            st.error("Run a digest first — there's nothing to send yet.")
        elif not subscribers:
            st.error("Connect an email above first.")
        else:
            from digest_engine import emailer
            arts = storage.get_digest(dates[0])
            ok = emailer.send_email(arts, dates[0], recipients=subscribers)
            st.success("Sent!") if ok else st.error("Couldn't send — the app's sender account isn't configured yet.")
