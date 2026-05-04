import httpx
import logging
import time
from api.models.knowledge import Paper

log = logging.getLogger("search.semantic_scholar")

SS_BASE = "https://api.semanticscholar.org/graph/v1"
FIELDS = "paperId,title,authors,abstract,year,externalIds,fieldsOfStudy,publicationTypes"


async def search_semantic_scholar(query: str, max_results: int = 10) -> list[Paper]:
    log.info("Semantic Scholar search | query=%r max_results=%d", query, max_results)
    t0 = time.perf_counter()
    params = {"query": query, "limit": max_results, "fields": FIELDS}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            log.debug("SS request | url=%s params=%s", f"{SS_BASE}/paper/search", params)
            resp = await client.get(f"{SS_BASE}/paper/search", params=params)
            log.debug("SS response | status=%d latency=%.0fms", resp.status_code,
                      resp.elapsed.total_seconds() * 1000 if resp.elapsed else 0)
            resp.raise_for_status()
            data = resp.json()

        raw_count = len(data.get("data", []))
        log.debug("SS raw results | count=%d", raw_count)

        papers = []
        for item in data.get("data", []):
            if not item.get("abstract"):
                log.debug("SS skip (no abstract) | id=%s title=%r",
                          item.get("paperId", "?"), (item.get("title") or "")[:60])
                continue
            arxiv_id = (item.get("externalIds") or {}).get("ArXiv", "")
            url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else \
                  f"https://www.semanticscholar.org/paper/{item['paperId']}"
            p = Paper(
                id=item["paperId"],
                title=item.get("title", ""),
                authors=[a["name"] for a in item.get("authors", [])],
                abstract=item.get("abstract", ""),
                year=item.get("year") or 0,
                url=url,
                source="semantic_scholar",
                keywords=[],
                domain=", ".join(item.get("fieldsOfStudy") or []),
            )
            log.debug("SS result | id=%s year=%s title=%r", p.id, p.year, p.title[:80])
            papers.append(p)

        elapsed = (time.perf_counter() - t0) * 1000
        log.info("SS done | query=%r raw=%d kept=%d | %.0fms", query, raw_count, len(papers), elapsed)
        return papers

    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        log.error("SS error | query=%r | %.0fms | %s", query, elapsed, exc, exc_info=True)
        raise
