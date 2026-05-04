import logging
from fastapi import APIRouter, HTTPException, Query

from api.models.source import Source, SourceIngest, Cluster
from services.tagging.tagger import analyse_source
from services.clustering.clusterer import build_clusters
from services.knowledge.source_store import (
    save_source, load_sources, delete_source,
    save_clusters, load_clusters,
)

log = logging.getLogger("routes.sources")
router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("", response_model=Source)
async def ingest_source(
    body: SourceIngest,
    llm: str | None = Query(None, description="openai | anthropic | gemini"),
    recluster: bool = Query(True, description="Re-run clustering after ingest"),
):
    """
    Add any content to the knowledge base.
    Accepts: arXiv ID (e.g. 2307.09288), arXiv URL, DOI, plain URL, or pasted text.
    """
    log.info("ingest_source | content_preview=%r recluster=%s", body.content[:80], recluster)
    source = await analyse_source(body, llm_provider=llm)
    save_source(source)

    if recluster:
        all_sources = load_sources()
        log.info("triggering recluster | total_sources=%d", len(all_sources))
        clusters = await build_clusters(all_sources, llm_provider=llm)
        save_clusters(clusters)
        # Refresh source with cluster label
        updated = next((s for s in load_sources() if s.id == source.id), source)
        return updated

    return source


@router.get("", response_model=list[Source])
async def list_sources():
    return load_sources()


@router.get("/clusters", response_model=list[Cluster])
async def list_clusters():
    return load_clusters()


@router.post("/recluster", response_model=list[Cluster])
async def recluster(
    llm: str | None = Query(None),
):
    """Force a full re-cluster of all sources."""
    sources = load_sources()
    if not sources:
        raise HTTPException(400, "No sources in knowledge base yet.")
    log.info("manual recluster | sources=%d", len(sources))
    clusters = await build_clusters(sources, llm_provider=llm)
    save_clusters(clusters)
    return clusters


@router.delete("/{source_id}", response_model=dict)
async def remove_source(source_id: str):
    if not delete_source(source_id):
        raise HTTPException(404, f"Source {source_id!r} not found.")
    return {"deleted": source_id}


@router.get("/{source_id}", response_model=Source)
async def get_source(source_id: str):
    sources = {s.id: s for s in load_sources()}
    if source_id not in sources:
        raise HTTPException(404, f"Source {source_id!r} not found.")
    return sources[source_id]
