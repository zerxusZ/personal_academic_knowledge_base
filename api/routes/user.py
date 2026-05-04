import json
import os
from fastapi import APIRouter
from api.models.user import UserProfile, ProfileSummary
from services.llm import get_llm

router = APIRouter(prefix="/user", tags=["user"])
PROFILE_PATH = "data/profile.json"


def load_profile() -> UserProfile | None:
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH) as f:
            return UserProfile(**json.load(f))
    return None


def save_profile(profile: UserProfile):
    os.makedirs("data", exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)


@router.post("/profile", response_model=ProfileSummary)
async def set_profile(profile: UserProfile, llm: str | None = None):
    save_profile(profile)
    svc = get_llm(llm)
    system = (
        "You are a research advisor. Given a user profile, return a JSON with: "
        "domain_keywords (list of 8 important keywords), "
        "suggested_queries (list of 5 academic search queries). Only return JSON."
    )
    user = (
        f"Profession: {profile.profession}\n"
        f"Department: {profile.department}\n"
        f"Research interests: {', '.join(profile.research_interests)}\n"
        f"Project: {profile.project_description}"
    )
    raw = await svc.chat(system, user)
    start, end = raw.find("{"), raw.rfind("}") + 1
    data = json.loads(raw[start:end])
    return ProfileSummary(
        profile=profile,
        domain_keywords=data.get("domain_keywords", []),
        suggested_queries=data.get("suggested_queries", []),
    )


@router.get("/profile", response_model=UserProfile)
async def get_profile():
    profile = load_profile()
    if not profile:
        from fastapi import HTTPException
        raise HTTPException(404, "No profile saved yet")
    return profile
