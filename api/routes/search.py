from fastapi import APIRouter, Query
from api.models.knowledge import Paper
from services.search.arxiv_service import search_arxiv
from services.search.semantic_scholar import search_semantic_scholar
from services.knowledge.kb_service import add_papers, enrich_paper
from api.routes.user import load_profile

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/arxiv", response_model=list[Paper])
async def arxiv_search(
    q: str = Query(..., description="Search query"),
    max_results: int = Query(10, le=30),
    enrich: bool = Query(False, description="Enrich with LLM summary"),
    save: bool = Query(True, description="Save results to knowledge base"),
    llm: str | None = None,
):
    papers = await search_arxiv(q, max_results)
    if enrich:
        profile = load_profile()
        if profile:
            papers = [await enrich_paper(p, profile, llm) for p in papers]
    if save:
        add_papers(papers)
    return papers


@router.get("/semantic_scholar", response_model=list[Paper])
async def ss_search(
    q: str = Query(..., description="Search query"),
    max_results: int = Query(10, le=30),
    enrich: bool = Query(False, description="Enrich with LLM summary"),
    save: bool = Query(True, description="Save results to knowledge base"),
    llm: str | None = None,
):
    papers = await search_semantic_scholar(q, max_results)
    if enrich:
        profile = load_profile()
        if profile:
            papers = [await enrich_paper(p, profile, llm) for p in papers]
    if save:
        add_papers(papers)
    return papers
