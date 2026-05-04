"""Persistent JSON store for Sources and Clusters."""
import json
import logging
import os
from datetime import datetime

from api.models.source import Source, Cluster

log = logging.getLogger("kb.store")
STORE_PATH = "data/knowledge_base/sources.json"


def _load() -> dict:
    if os.path.exists(STORE_PATH):
        log.debug("Loading source store from %s", STORE_PATH)
        with open(STORE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"sources": {}, "clusters": {}, "updated_at": ""}


def _save(store: dict):
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    store["updated_at"] = datetime.utcnow().isoformat()
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    log.debug("Store saved | sources=%d clusters=%d", len(store["sources"]), len(store["clusters"]))


# ── Sources ──────────────────────────────────────────────────────────────────

def save_source(source: Source):
    store = _load()
    store["sources"][source.id] = source.model_dump()
    _save(store)
    log.info("save_source | id=%s title=%r", source.id, source.title[:60])


def load_sources() -> list[Source]:
    store = _load()
    out = [Source(**v) for v in store["sources"].values()]
    log.debug("load_sources | count=%d", len(out))
    return out


def delete_source(source_id: str) -> bool:
    store = _load()
    if source_id not in store["sources"]:
        return False
    del store["sources"][source_id]
    # Remove from any cluster
    for c in store["clusters"].values():
        if source_id in c.get("source_ids", []):
            c["source_ids"].remove(source_id)
    _save(store)
    log.info("delete_source | id=%s", source_id)
    return True


# ── Clusters ─────────────────────────────────────────────────────────────────

def save_clusters(clusters: list[Cluster]):
    store = _load()
    store["clusters"] = {c.id: c.model_dump() for c in clusters}
    # Propagate cluster labels into source records
    for c in clusters:
        for sid in c.source_ids:
            if sid in store["sources"]:
                store["sources"][sid]["cluster_id"] = c.id
                store["sources"][sid]["cluster_label"] = c.label
    _save(store)
    log.info("save_clusters | count=%d", len(clusters))


def load_clusters() -> list[Cluster]:
    store = _load()
    return [Cluster(**v) for v in store["clusters"].values()]
