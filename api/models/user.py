from pydantic import BaseModel
from typing import Optional


class UserProfile(BaseModel):
    name: str
    profession: str          # e.g. "PhD student", "Engineer", "Researcher"
    department: str          # e.g. "Computer Science", "Biology"
    research_interests: list[str]
    project_description: str
    language: str = "en"     # "en" or "zh"

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Alice",
                "profession": "PhD student",
                "department": "Computer Science",
                "research_interests": ["NLP", "knowledge graphs"],
                "project_description": "Building a QA system over scientific papers",
                "language": "en"
            }
        }


class ProfileSummary(BaseModel):
    profile: UserProfile
    domain_keywords: list[str]
    suggested_queries: list[str]
