"""
NotebookLM-style source analyser.

Given any text chunk (abstract, excerpt, pasted notes), the LLM returns:
  - A structured TagSet (5 categories)
  - A plain-English summary (2–3 sentences, non-technical)
  - 3–5 key concepts (noun phrases)
  - One notable quote / sentence from the text
"""
import json
import logging
import re
import time

import httpx

from api.models.source import Source, SourceIngest, TagSet
from services.llm import get_llm

log = logging.getLogger("tagging")

# ── arXiv / DOI / URL detection ─────────────────────────────────────────────

_ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
_ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")
_DOI = re.compile(r"10\.\d{4,}/\S+")


def _detect_type(content: str) -> str:
    c = content.strip()
    if _ARXIV_ID.match(c):
        return "arxiv_id"
    if _ARXIV_URL.search(c):
        return "arxiv_url"
    if _DOI.search(c):
        return "doi"
    if c.startswith("http"):
        return "url"
    return "text"


async def _fetch_arxiv(arxiv_id: str) -> dict:
    """Fetch title + abstract from arXiv API."""
    clean = arxiv_id.strip().split("v")[0]
    url = f"https://export.arxiv.org/abs/{clean}"
    log.debug("Fetching arXiv abstract | id=%s", clean)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    html = resp.text
    # Extract title
    title_m = re.search(r'<h1 class="title[^"]*">\s*<span[^>]*>[^<]*</span>\s*(.*?)</h1>', html, re.S)
    title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else clean
    # Extract abstract
    abs_m = re.search(r'<blockquote class="abstract[^"]*">\s*<span[^>]*>[^<]*</span>\s*(.*?)</blockquote>', html, re.S)
    abstract = re.sub(r"<[^>]+>", " ", abs_m.group(1)).strip() if abs_m else ""
    # Extract authors
    authors_m = re.search(r'<div class="authors">(.*?)</div>', html, re.S)
    authors_raw = re.sub(r"<[^>]+>", "", authors_m.group(1)) if authors_m else ""
    authors = [a.strip() for a in authors_raw.replace("Authors:", "").split(",") if a.strip()][:6]
    # Year from ID
    year = int("20" + clean[:2]) if clean[:2].isdigit() else None
    return {
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "year": year,
        "url": f"https://arxiv.org/abs/{clean}",
    }


_ANALYSIS_SYSTEM = """
You are a research librarian who helps non-specialist users understand academic content.

Given a text excerpt, return ONLY a valid JSON object with these exact keys:

{
  "title": "concise descriptive title (if not already known)",
  "summary": "2-3 plain sentences, no jargon, explaining the main idea to a curious non-expert",
  "key_concepts": ["noun phrase 1", "noun phrase 2", "noun phrase 3"],
  "notable_quote": "one memorable sentence copied verbatim from the text (or empty string)",
  "tags": {
    "topics":       ["broad subject areas, e.g. machine learning, ecology"],
    "methods":      ["techniques used, e.g. transformer, regression analysis"],
    "concepts":     ["key ideas, e.g. attention mechanism, gene expression"],
    "domain":       ["application field, e.g. NLP, climate science, medicine"],
    "problem_type": ["what it solves, e.g. classification, prediction, discovery"]
  }
}

Rules:
- Tags must be lowercase, 1-4 words each
- Each category: 2-5 tags maximum
- Summary must be readable by a high-school student
- Return ONLY the JSON, no markdown fences, no extra text
"""


async def analyse_source(
    ingest: SourceIngest,
    llm_provider: str | None = None,
) -> Source:
    """Full pipeline: detect type → fetch if needed → LLM analysis → Source."""
    import uuid
    t0 = time.perf_counter()

    content = ingest.content.strip()
    ctype = _detect_type(content)
    log.info("analyse_source | type=%s content_len=%d hint=%s", ctype, len(content), ingest.hint)

    # ── Resolve to text ──────────────────────────────────────────────────
    title = ingest.title or ""
    authors: list[str] = []
    year: int | None = None
    url: str | None = None
    raw_text = content

    if ctype in ("arxiv_id", "arxiv_url"):
        arxiv_id = _ARXIV_URL.search(content)
        arxiv_id = arxiv_id.group(1) if arxiv_id else content.strip()
        log.debug("Resolving arXiv ID: %s", arxiv_id)
        try:
            fetched = await _fetch_arxiv(arxiv_id)
            title = title or fetched["title"]
            raw_text = fetched["abstract"]
            authors = fetched["authors"]
            year = fetched["year"]
            url = fetched["url"]
            log.info("arXiv resolved | title=%r abstract_len=%d", title[:80], len(raw_text))
        except Exception as exc:
            log.warning("arXiv fetch failed (%s), using raw content", exc)

    # ── LLM analysis ─────────────────────────────────────────────────────
    user_msg = f"Title (if known): {title or 'unknown'}\n"
    if ingest.hint:
        user_msg += f"User note: {ingest.hint}\n"
    user_msg += f"\nText:\n{raw_text[:3000]}"

    log.info("Sending to LLM for tagging | provider=%s text_len=%d", llm_provider or "default", len(raw_text))
    llm = get_llm(llm_provider)
    raw_json = await llm.chat(_ANALYSIS_SYSTEM, user_msg)

    # Strip markdown fences if model wraps them anyway
    raw_json = re.sub(r"^```[a-z]*\n?", "", raw_json.strip())
    raw_json = re.sub(r"\n?```$", "", raw_json.strip())

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        log.error("LLM returned invalid JSON: %s\n---\n%s", exc, raw_json[:500])
        data = {}

    tags_raw = data.get("tags", {})
    tags = TagSet(
        topics=tags_raw.get("topics", []),
        methods=tags_raw.get("methods", []),
        concepts=tags_raw.get("concepts", []),
        domain=tags_raw.get("domain", []),
        problem_type=tags_raw.get("problem_type", []),
    )

    source = Source(
        id=str(uuid.uuid4())[:12],
        title=title or data.get("title", content[:60]),
        content_type=ctype,
        raw_text=raw_text[:4000],
        url=url,
        authors=authors,
        year=year,
        tags=tags,
        summary=data.get("summary", ""),
        key_concepts=data.get("key_concepts", []),
        notable_quote=data.get("notable_quote", ""),
    )

    elapsed = (time.perf_counter() - t0) * 1000
    log.info(
        "analyse_source done | id=%s title=%r tags=%d | %.0fms",
        source.id, source.title[:60], len(source.tags.all_tags()), elapsed,
    )
    log.debug("tags=%s", source.tags.model_dump())
    return source
