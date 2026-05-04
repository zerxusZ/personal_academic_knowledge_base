from fastapi import APIRouter
from fastapi.responses import JSONResponse
from api.models.knowledge import KnowledgeBase, KBQuery, KBQueryResult, Paper
from services.knowledge.kb_service import (
    load_all_papers, export_kb, import_kb, search_kb, add_papers, enrich_paper
)
from api.routes.user import load_profile

router = APIRouter(prefix="/kb", tags=["knowledge_base"])


@router.get("/papers", response_model=list[Paper])
async def list_papers():
    return load_all_papers()


@router.post("/query", response_model=KBQueryResult)
async def query_kb(body: KBQuery):
    results = search_kb(body.query, body.top_k)
    return KBQueryResult(query=body.query, results=results)


@router.get("/export", response_model=KnowledgeBase)
async def export_knowledge_base():
    profile = load_profile()
    if not profile:
        from fastapi import HTTPException
        raise HTTPException(400, "Set user profile first via POST /user/profile")
    return export_kb(profile)


@router.post("/import", response_model=dict)
async def import_knowledge_base(kb: KnowledgeBase):
    added = import_kb(kb)
    return {"imported": added, "message": f"Added {added} new papers to knowledge base"}


@router.delete("/papers/{paper_id}", response_model=dict)
async def delete_paper(paper_id: str):
    import json, os
    KB_PATH = "data/knowledge_base/kb.json"
    if not os.path.exists(KB_PATH):
        from fastapi import HTTPException
        raise HTTPException(404, "Knowledge base is empty")
    with open(KB_PATH) as f:
        kb = json.load(f)
    papers = kb.get("papers", {})
    if paper_id not in papers:
        from fastapi import HTTPException
        raise HTTPException(404, f"Paper {paper_id} not found")
    del papers[paper_id]
    kb["papers"] = papers
    with open(KB_PATH, "w") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)
    return {"deleted": paper_id}


@router.post("/enrich/{paper_id}", response_model=Paper)
async def enrich_one(paper_id: str, llm: str | None = None):
    papers = {p.id: p for p in load_all_papers()}
    if paper_id not in papers:
        from fastapi import HTTPException
        raise HTTPException(404, f"Paper {paper_id} not found")
    profile = load_profile()
    if not profile:
        from fastapi import HTTPException
        raise HTTPException(400, "Set user profile first via POST /user/profile")
    enriched = await enrich_paper(papers[paper_id], profile, llm)
    add_papers([enriched])
    return enriched
