"""AI summarization with persona-aware "why it matters" notes, and a
graceful, dependency-free fallback when no API key is set.

Every article gets one neutral summary plus three role-specific notes
(security / privacy / compliance) — the same story lands differently
for a SOC analyst chasing exposure than for a compliance officer
tracking a filing deadline, and surfacing that distinction is the
clearest signal that this digest is curated, not just aggregated.
"""
import os
import re
import json
import html

PERSONA_TEMPLATES = {
    "security": {
        "high": "Treat as urgent — check whether this affects your stack and prioritize patching or containment.",
        "medium": "Worth a look if you're tracking newly disclosed issues in your environment.",
        "low": "Background awareness; no immediate action expected.",
    },
    "privacy": {
        "high": "Assess whether this affects data-handling obligations or requires a breach review.",
        "medium": "Worth monitoring for downstream policy or notification implications.",
        "low": "General privacy-landscape awareness; low urgency.",
    },
    "compliance": {
        "high": "Confirm whether this triggers a reporting, remediation, or filing deadline.",
        "medium": "Worth tracking for upcoming obligations tied to this development.",
        "low": "Useful context for ongoing monitoring; no immediate obligation flagged.",
    },
}


def _strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _fallback_summary(article):
    text = _strip_html(article.get("raw_summary", ""))
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = " ".join(sentences[:2])[:280]
    return summary or article["title"]


def _fallback_why_it_matters(article):
    priority_key = article.get("priority", "Low").lower()
    return {
        role: PERSONA_TEMPLATES[role].get(priority_key, PERSONA_TEMPLATES[role]["low"])
        for role in ("security", "privacy", "compliance")
    }


def _prompt_for(article):
    return (
        "You are writing for a security/privacy/compliance news digest. "
        "Respond with STRICT JSON only — no markdown fences, no prose outside the JSON — "
        "in exactly this shape:\n"
        '{"summary": "<2 short neutral sentences>", '
        '"why_it_matters": {'
        '"security": "<1 sentence: what a security analyst should do or know>", '
        '"privacy": "<1 sentence: what a privacy officer should do or know>", '
        '"compliance": "<1 sentence: what a compliance officer should do or know>"}}\n\n'
        f"Title: {article['title']}\n"
        f"Source text: {_strip_html(article.get('raw_summary', ''))[:1200]}"
    )


def _parse_llm_response(raw, article):
    text = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
        summary = (data.get("summary") or "").strip() or _fallback_summary(article)
        why_raw = data.get("why_it_matters") or {}
        fallback_why = _fallback_why_it_matters(article)
        why_it_matters = {
            role: (why_raw.get(role) or "").strip() or fallback_why[role]
            for role in ("security", "privacy", "compliance")
        }
        return summary, why_it_matters
    except Exception:
        return (text[:280] or _fallback_summary(article)), _fallback_why_it_matters(article)


def _call_openai(article, client, model="gpt-4o-mini"):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": _prompt_for(article)}],
        max_tokens=220,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def _call_anthropic(article, client, model="claude-sonnet-4-6"):
    resp = client.messages.create(
        model=model,
        max_tokens=260,
        messages=[{"role": "user", "content": _prompt_for(article)}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def _call_gemini(article, client, model="gemini-2.0-flash"):
    resp = client.models.generate_content(model=model, contents=_prompt_for(article))
    return resp.text.strip()


def get_summarizer():
    """Return a summarize(article) -> (summary, why_it_matters_dict) function
    based on available API keys. Checked in order: OpenAI, Anthropic, Gemini,
    then the dependency-free fallback."""
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            return lambda article: _parse_llm_response(_call_openai(article, client), article)
        except Exception as e:
            print(f"[summarizer] OpenAI init failed, falling back: {e}")

    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            return lambda article: _parse_llm_response(_call_anthropic(article, client), article)
        except Exception as e:
            print(f"[summarizer] Anthropic init failed, falling back: {e}")

    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            return lambda article: _parse_llm_response(_call_gemini(article, client), article)
        except Exception as e:
            print(f"[summarizer] Gemini init failed, falling back: {e}")

    print("[summarizer] No LLM API key found — using extractive fallback summaries.")
    return lambda article: (_fallback_summary(article), _fallback_why_it_matters(article))


def summarize_articles(articles):
    """Requires articles to already have 'priority' set (scorer.enrich must
    run first) so the fallback why-it-matters can key off severity."""
    summarize = get_summarizer()
    for a in articles:
        try:
            summary, why_it_matters = summarize(a)
        except Exception as e:
            print(f"[summarizer] failed for '{a['title']}': {e}")
            summary, why_it_matters = _fallback_summary(a), _fallback_why_it_matters(a)
        a["summary"] = summary
        a["why_it_matters"] = why_it_matters
    return articles
