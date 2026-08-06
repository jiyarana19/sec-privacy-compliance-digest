"""HTML email digest builder and SMTP delivery."""
import os
import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

PRIORITY_COLORS = {"High": "#d64545", "Medium": "#e0a72f", "Low": "#4a7c59"}

# The email digest is written for a general reader (not a chosen persona
# view like the dashboard), so "why it matters" falls back through roles
# in this order and shows the first one available.
EMAIL_PERSONA_PRIORITY = ("security", "compliance", "privacy")


def build_html(articles, run_date):
    by_category = {}
    for a in articles:
        by_category.setdefault(a["category"], []).append(a)

    sections = []
    for category in ("security", "privacy", "compliance"):
        items = by_category.get(category, [])
        if not items:
            continue
        rows = ""
        for a in items:
            color = PRIORITY_COLORS.get(a.get("priority", "Low"), "#888")
            title = html.escape(str(a.get("title", "")))
            source = html.escape(str(a.get("source", "")))
            summary = html.escape(str(a.get("summary", "")))
            link = html.escape(str(a.get("link", "")), quote=True)
            priority = html.escape(str(a.get("priority", "Low")))
            tags = "".join(
                f'<span style="background:#eef;border-radius:4px;padding:2px 6px;'
                f'font-size:11px;margin-right:4px;">{html.escape(str(t))}</span>'
                for t in a.get("watchlist_matches", [])
            )

            why = a.get("why_it_matters") or {}
            why_text = next((why.get(r) for r in EMAIL_PERSONA_PRIORITY if why.get(r)), "")
            why_html = (
                f'<p style="font-size:12.5px;color:#1B3A5C;font-style:italic;margin:4px 0;">'
                f'Why it matters: {html.escape(why_text)}</p>'
                if why_text else ""
            )
            deadline_html = (
                f'<p style="font-size:12px;color:#1B3A5C;font-weight:bold;margin:4px 0;">'
                f'Deadline: {html.escape(str(a["deadline"]))}</p>'
                if a.get("deadline") else ""
            )

            rows += f"""
            <div style="border-left:4px solid {color};padding:10px 14px;margin-bottom:10px;background:#fafafa;">
              <div style="font-size:11px;color:{color};font-weight:bold;text-transform:uppercase;">
                {priority} &middot; {source}
              </div>
              <a href="{link}" style="font-size:15px;font-weight:600;color:#1a1a2e;text-decoration:none;">
                {title}
              </a>
              <p style="font-size:13px;color:#333;margin:6px 0;">{summary}</p>
              {why_html}
              {deadline_html}
              <div>{tags}</div>
            </div>"""
        sections.append(f"""
          <h2 style="text-transform:capitalize;border-bottom:2px solid #333;padding-bottom:4px;">
            {html.escape(category)} ({len(items)})
          </h2>
          {rows}
        """)

    return f"""
    <html><body style="font-family:Arial,Helvetica,sans-serif;max-width:680px;margin:auto;">
      <h1 style="color:#1a1a2e;">Security, Privacy &amp; Compliance Digest</h1>
      <p style="color:#666;">{run_date}</p>
      {''.join(sections)}
      <p style="font-size:11px;color:#999;margin-top:30px;">
        Generated automatically. Adjust sources and watchlist in your dashboard settings.
      </p>
    </body></html>
    """


def send_email(articles, run_date, recipients=None):
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    recipients = recipients or os.environ.get("DIGEST_RECIPIENTS", "").split(",")
    recipients = [r.strip() for r in recipients if r.strip()]

    if not (user and password and recipients):
        print("[emailer] Missing SMTP_USER / SMTP_PASSWORD / DIGEST_RECIPIENTS — skipping email send.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Security, Privacy & Compliance Digest — {run_date}"
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(build_html(articles, run_date), "html"))

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, recipients, msg.as_string())

    print(f"[emailer] Digest sent to {recipients}")
    return True
