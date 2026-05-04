import arxiv
import asyncio
import logging
import time
from api.models.knowledge import Paper

log = logging.getLogger("search.arxiv")


async def search_arxiv(query: str, max_results: int = 10) -> list[Paper]:
    log.info("arXiv search | query=%r max_results=%d", query, max_results)
    t0 = time.perf_counter()

    def _sync_search():
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        papers = []
        for r in client.results(search):
            log.debug(
                "arXiv result | id=%s year=%s title=%r",
                r.entry_id.split("/")[-1],
                r.published.year,
                r.title[:80],
            )
            papers.append(Paper(
                id=r.entry_id.split("/")[-1],
                title=r.title,
                authors=[a.name for a in r.authors],
                abstract=r.summary.replace("\n", " "),
                year=r.published.year,
                url=r.entry_id,
                source="arxiv",
                keywords=r.categories,
                domain=r.primary_category,
            ))
        return papers

    try:
        papers = await asyncio.to_thread(_sync_search)
        elapsed = (time.perf_counter() - t0) * 1000
        log.info("arXiv done  | query=%r | found=%d | %.0fms", query, len(papers), elapsed)
        return papers
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        log.error("arXiv error | query=%r | %.0fms | %s", query, elapsed, exc, exc_info=True)
        raise
