from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TagSet(BaseModel):
    """Structured semantic tags produced by LLM analysis of one source."""
    topics: list[str]       # broad subject areas: "machine learning", "ecology"
    methods: list[str]      # techniques/approaches: "transformer", "regression"
    concepts: list[str]     # key ideas: "attention mechanism", "overfitting"
    domain: list[str]       # application fields: "NLP", "climate science"
    problem_type: list[str] # what problem it tackles: "classification", "prediction"

    def all_tags(self) -> list[str]:
        seen, out = set(), []
        for t in self.topics + self.methods + self.concepts + self.domain + self.problem_type:
            tl = t.lower().strip()
            if tl and tl not in seen:
                seen.add(tl)
                out.append(tl)
        return out


class Source(BaseModel):
    """A single piece of content in the knowledge base."""
    id: str
    title: str
    content_type: str       # "text" | "arxiv_id" | "doi" | "url" | "paper"
    raw_text: str           # the actual content (abstract / body snippet)
    url: Optional[str] = None
    authors: list[str] = []
    year: Optional[int] = None

    # Produced by tagging pipeline
    tags: TagSet = TagSet(topics=[], methods=[], concepts=[], domain=[], problem_type=[])
    summary: str = ""
    key_concepts: list[str] = []
    notable_quote: str = ""

    # Produced by clustering pipeline
    cluster_id: Optional[str] = None
    cluster_label: Optional[str] = None

    added_at: str = ""

    def model_post_init(self, __context):
        if not self.added_at:
            self.added_at = datetime.utcnow().isoformat()


class SourceIngest(BaseModel):
    """Payload sent by the user to add a new source."""
    content: str            # arXiv ID / DOI / URL / raw pasted text
    title: Optional[str] = None
    hint: Optional[str] = None   # user can give a short hint like "this is about CRISPR"

    class Config:
        json_schema_extra = {
            "examples": [
                {"content": "2307.09288"},
                {"content": "https://arxiv.org/abs/1706.03762"},
                {"content": "Attention Is All You Need\nAbstract: The dominant sequence...", "title": "Attention paper"},
                {"content": "Transformer models encode input sequences using self-attention...", "hint": "about NLP"},
            ]
        }


class Cluster(BaseModel):
    """A group of semantically related sources."""
    id: str
    label: str              # human-readable name: "Deep Learning Methods"
    dominant_tags: list[str]
    source_ids: list[str]
    summary: str = ""       # LLM-written description of what this cluster is about
