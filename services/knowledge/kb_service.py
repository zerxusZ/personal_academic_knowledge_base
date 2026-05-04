import json
import logging
import os
import time
from datetime import datetime
from api.models.knowledge import Paper, KnowledgeBase
from api.models.user import UserProfile
from services.llm import get_llm

log = logging.getLogger("kb")
KB_PATH = "data/knowledge_base/kb.json"


def _load_kb() -> dict:
    if os.path.exists(KB_PATH):
        log.debug("Loading KB from %s", KB_PATH)
        with open(KB_PATH) as f:
            return json.load(f)
    log.debug("KB file not found, starting empty")
    return {}


def _save_kb(kb: dict):
    os.makedirs(os.path.dirname(KB_PATH), exist_ok=True)
    with open(KB_PATH, "w") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)
    log.debug("KB saved to %s | total_papers=%d", KB_PATH, len(kb.get("papers", {})))


def load_all_papers() -> list[Paper]:
    kb = _load_kb()
    papers = [Paper(**p) for p in kb.get("papers", {}).values()]
    log.debug("load_all_papers | count=%d", len(papers))
    return papers


def add_papers(papers: list[Paper]) -> int:
    log.info("add_papers | incoming=%d", len(papers))
    kb = _load_kb()
    existing = kb.get("papers", {})
    before = len(existing)
    added = 0
    for p in papers:
        if p.id not in existing:
            existing[p.id] = p.model_dump()
            added += 1
            log.debug("KB +paper | id=%s title=%r", p.id, p.title[:80])
        else:
            log.debug("KB skip (dup) | id=%s", p.id)
    kb["papers"] = existing
    kb["updated_at"] = datetime.utcnow().isoformat()
    if not kb.get("created_at"):
        kb["created_at"] = kb["updated_at"]
    _save_kb(kb)
    log.info("add_papers done | before=%d added=%d total=%d", before, added, len(existing))
    return added


def search_kb(query: str, top_k: int = 5) -> list[Paper]:
    log.info("search_kb | query=%r top_k=%d", query, top_k)
    t0 = time.perf_counter()
    terms = query.lower().split()
    scored: list[tuple[float, Paper]] = []
    all_papers = load_all_papers()
    for paper in all_papers:
        text = (paper.title + " " + paper.abstract + " " + " ".join(paper.keywords)).lower()
        score = sum(text.count(t) for t in terms)
        if score > 0:
            scored.append((score, paper))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [p for _, p in scored[:top_k]]
    elapsed = (time.perf_counter() - t0) * 1000
    log.info(
        "search_kb done | query=%r scanned=%d matched=%d returned=%d | %.1fms",
        query, len(all_papers), len(scored), len(results), elapsed,
    )
    for rank, (score, p) in enumerate(scored[:top_k], 1):
        log.debug("  rank=%d score=%d id=%s title=%r", rank, score, p.id, p.title[:80])
    return results


def export_kb(profile: UserProfile) -> KnowledgeBase:
    log.info("export_kb | owner=%s domain=%s", profile.name, profile.research_interests)
    papers = load_all_papers()
    now = datetime.utcnow().isoformat()
    kb = _load_kb()
    result = KnowledgeBase(
        created_at=kb.get("created_at", now),
        updated_at=kb.get("updated_at", now),
        owner_profile=profile.model_dump(),
        domain=", ".join(profile.research_interests),
        papers=papers,
        total=len(papers),
    )
    log.info("export_kb done | papers=%d", result.total)
    return result


def import_kb(kb: KnowledgeBase) -> int:
    log.info("import_kb | incoming_papers=%d domain=%s", len(kb.papers), kb.domain)
    added = add_papers(kb.papers)
    log.info("import_kb done | added=%d", added)
    return added


async def enrich_paper(paper: Paper, profile: UserProfile, llm_provider: str | None = None) -> Paper:
    log.info("enrich_paper | id=%s provider=%s title=%r", paper.id, llm_provider or "default", paper.title[:80])
    llm = get_llm(llm_provider)
    system = (
        "You are a research assistant. Given a paper abstract and a user's research profile, "
        "return a JSON object with keys: summary (2 sentences), key_points (list of 3 strings), "
        "relevance_score (float 0-1). Only return the JSON object."
    )
    user = (
        f"User profile: {profile.profession} in {profile.department}, "
        f"interests: {', '.join(profile.research_interests)}.\n\n"
        f"Paper title: {paper.title}\nAbstract: {paper.abstract[:1500]}"
    )
    t0 = time.perf_counter()
    try:
        raw = await llm.chat(system, user)
        start, end = raw.find("{"), raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        paper.summary = data.get("summary", "")
        paper.key_points = data.get("key_points", [])
        paper.relevance_score = float(data.get("relevance_score", 0))
        elapsed = (time.perf_counter() - t0) * 1000
        log.info(
            "enrich_paper done | id=%s relevance=%.2f | %.0fms",
            paper.id, paper.relevance_score, elapsed,
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        log.error("enrich_paper failed | id=%s | %.0fms | %s", paper.id, elapsed, exc, exc_info=True)
    return paper
