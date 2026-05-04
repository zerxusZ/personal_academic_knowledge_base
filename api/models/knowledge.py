from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Paper(BaseModel):
    """Standard paper entry in the knowledge base."""
    id: str
    title: str
    authors: list[str]
    abstract: str
    year: int
    url: str
    source: str              # "arxiv" | "semantic_scholar"
    keywords: list[str]
    domain: str
    summary: Optional[str] = None   # LLM-generated summary
    key_points: list[str] = []      # LLM-extracted key points
    relevance_score: float = 0.0    # 0-1 relevance to user profile
    added_at: str = ""

    def model_post_init(self, __context):
        if not self.added_at:
            self.added_at = datetime.utcnow().isoformat()


class KnowledgeBase(BaseModel):
    """Top-level knowledge base object — this is the exported/shared format."""
    version: str = "1.0"
    created_at: str
    updated_at: str
    owner_profile: dict
    domain: str
    papers: list[Paper]
    total: int

    class Config:
        json_schema_extra = {
            "description": "Standard knowledge base format. Import by POST /kb/import"
        }


class KBQuery(BaseModel):
    query: str
    top_k: int = 5


class KBQueryResult(BaseModel):
    query: str
    results: list[Paper]
