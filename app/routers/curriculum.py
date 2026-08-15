from fastapi import APIRouter, Depends

from app.database import supabase
from app.security import get_current_user
from app.schemas import ChaptersSaveRequest

router = APIRouter(prefix="/curriculum", tags=["curriculum"])

CLASS_OPTIONS = [f"Class {i}" for i in range(1, 13)]


@router.get("/classes")
def get_classes():
    return CLASS_OPTIONS


@router.get("/subjects")
def get_subjects(class_name: str):
    res = supabase.table("curriculum").select("subject_name").eq("class_name", class_name).execute()
    return sorted(set(r["subject_name"] for r in res.data))


@router.get("/chapters")
def get_chapters(class_name: str, subject_name: str):
    res = supabase.table("curriculum").select("chapters").eq("class_name", class_name).eq("subject_name", subject_name).execute()
    if res.data:
        return [c.strip() for c in res.data[0]["chapters"].split(",") if c.strip()]
    return []


@router.post("/chapters")
def save_chapters(payload: ChaptersSaveRequest, user: dict = Depends(get_current_user)):
    existing_res = supabase.table("curriculum").select("chapters").eq("class_name", payload.class_name).eq("subject_name", payload.subject_name).execute()
    existing_chapters = []
    if existing_res.data:
        existing_chapters = [c.strip() for c in existing_res.data[0]["chapters"].split(",") if c.strip()]

    merged = sorted(set(existing_chapters + [c.strip() for c in payload.chapters if c.strip()]))
    chapters_str = ", ".join(merged)

    existing = supabase.table("curriculum").select("id").eq("class_name", payload.class_name).eq("subject_name", payload.subject_name).execute()
    if existing.data:
        supabase.table("curriculum").update({"chapters": chapters_str}).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("curriculum").insert({"class_name": payload.class_name, "subject_name": payload.subject_name, "chapters": chapters_str}).execute()

    return {"chapters": merged}

