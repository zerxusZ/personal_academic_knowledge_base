"""
Tag-overlap clustering.

Algorithm:
  1. Build a tag-overlap matrix (Jaccard similarity) between all sources.
  2. Greedy merge: seed a cluster from the most-connected unassigned source,
     pull in any source with overlap >= threshold.
  3. Label each cluster by asking the LLM to name the dominant tag set.

No external ML libraries required — the LLM does the semantic lifting.
"""
import json
import logging
import time
import uuid
from collections import Counter

from api.models.source import Source, Cluster
from services.llm import get_llm

log = logging.getLogger("clustering")

OVERLAP_THRESHOLD = 0.20   # Jaccard ≥ 0.20 → same cluster


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _cluster_sources(sources: list[Source]) -> dict[str, str]:
    """Return {source_id: cluster_id} assignment."""
    if not sources:
        return {}

    tag_lists = {s.id: s.tags.all_tags() for s in sources}
    unassigned = [s.id for s in sources]
    assignment: dict[str, str] = {}

    while unassigned:
        # Seed: pick the source with most total tag overlap to others
        seed = max(
            unassigned,
            key=lambda sid: sum(
                _jaccard(tag_lists[sid], tag_lists[other])
                for other in unassigned if other != sid
            ),
        )
        cid = str(uuid.uuid4())[:8]
        assignment[seed] = cid
        unassigned.remove(seed)

        # Pull in similar sources
        to_add = [
            sid for sid in unassigned
            if _jaccard(tag_lists[seed], tag_lists[sid]) >= OVERLAP_THRESHOLD
        ]
        for sid in to_add:
            assignment[sid] = cid
            unassigned.remove(sid)
            log.debug(
                "cluster merge | cluster=%s source=%s jaccard=%.2f",
                cid, sid, _jaccard(tag_lists[seed], tag_lists[sid]),
            )

    return assignment


_LABEL_SYSTEM = """
You are a librarian naming a collection of related sources.

Given a list of tags describing a group of sources, return a JSON object:
{
  "label": "Short, human-friendly cluster name (3-6 words, title case)",
  "summary": "One sentence describing what this cluster is about, for a non-expert reader."
}

Return ONLY the JSON, no markdown.
"""


async def build_clusters(
    sources: list[Source],
    llm_provider: str | None = None,
) -> list[Cluster]:
    if not sources:
        return []

    t0 = time.perf_counter()
    log.info("build_clusters | sources=%d threshold=%.2f", len(sources), OVERLAP_THRESHOLD)

    assignment = _cluster_sources(sources)

    # Group source IDs by cluster
    groups: dict[str, list[str]] = {}
    for sid, cid in assignment.items():
        groups.setdefault(cid, []).append(sid)

    log.info("clusters formed: %d", len(groups))

    src_map = {s.id: s for s in sources}
    llm = get_llm(llm_provider)
    clusters: list[Cluster] = []

    for cid, sids in groups.items():
        # Collect dominant tags across cluster members
        all_tags: list[str] = []
        for sid in sids:
            all_tags.extend(src_map[sid].tags.all_tags())
        dominant = [tag for tag, _ in Counter(all_tags).most_common(10)]

        log.debug("labelling cluster=%s dominant_tags=%s", cid, dominant[:5])

        # Ask LLM to name the cluster
        try:
            raw = await llm.chat(
                _LABEL_SYSTEM,
                f"Tags for this group: {', '.join(dominant)}\nNumber of sources: {len(sids)}",
            )
            import re
            raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
            raw = re.sub(r"\n?```$", "", raw.strip())
            meta = json.loads(raw)
            label = meta.get("label", "Untitled Cluster")
            summary = meta.get("summary", "")
        except Exception as exc:
            log.warning("cluster label LLM failed (%s), using tag fallback", exc)
            label = " & ".join(w.title() for w in dominant[:3]) if dominant else "Cluster"
            summary = ""

        clusters.append(Cluster(
            id=cid,
            label=label,
            dominant_tags=dominant,
            source_ids=sids,
            summary=summary,
        ))
        log.info("cluster | id=%s label=%r sources=%d tags=%s", cid, label, len(sids), dominant[:4])

    # Attach cluster info back to source objects in-place
    for c in clusters:
        for sid in c.source_ids:
            if sid in src_map:
                src_map[sid].cluster_id = c.id
                src_map[sid].cluster_label = c.label

    elapsed = (time.perf_counter() - t0) * 1000
    log.info("build_clusters done | %d clusters | %.0fms", len(clusters), elapsed)
    return clusters
