import logging
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.database import supabase
from app.security import get_current_user
from app.schemas import GeneratePaperRequest, SavePaperRequest
from app.prompt_builder import build_question_prompt
from app.gemini_client import generate_gemini_content, get_working_model_name
from app.pdf_extractor import extract_text_from_pdf
from app.config import settings

router = APIRouter(prefix="/papers", tags=["papers"])
logger = logging.getLogger("paperbanao")

FREE_LIMIT = 5


class RegenerateQuestionRequest(BaseModel):
    old_text: str
    subject: str
    topics: str = ""


def extract_question_number(text: str):
    """Pulls the question number out of a block like '**Q3.** ...' or '3. ...'
    so the matching Answer Key entry can be kept in sync."""
    m = re.search(r'Q\.?\s*(\d+)', text, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.match(r'\s*\**\s*(\d+)\.', text)
    if m2:
        return m2.group(1)
    return None


@router.post("/regenerate-question")
def regenerate_question(payload: RegenerateQuestionRequest, user: dict = Depends(get_current_user)):
    topic_context = payload.topics.strip() if payload.topics.strip() else payload.subject
    prompt = (
        f"You are regenerating ONE question from a {payload.subject} exam paper. "
        f"The paper's topics are: {topic_context}. Stay strictly within this subject and these topics — "
        f"do not drift into unrelated topics.\n\n"
        f"The original question being replaced was:\n{payload.old_text}\n\n"
        "Write a NEW question of the same type, difficulty, and marks as the original, strictly on the same "
        "subject/topics. Keep the same question number label if the original had one (e.g. 'Q3.'). "
        "Use Unicode math symbols (θ, π, √, ²) instead of LaTeX.\n\n"
        "Then on a new line write the exact delimiter @@@ANSWER@@@ followed by the correct answer/solution for "
        "THIS NEW question — a brief correct option letter for MCQ/True-False/Fill-in-the-blank, or a full "
        "step-by-step explanation for Short/Long answer questions.\n\n"
        "Output ONLY the question text, then @@@ANSWER@@@, then the answer. No extra commentary."
    )
    api_key = settings.GEMINI_API_KEY
    model_name = get_working_model_name(api_key)
    try:
        resp_text = generate_gemini_content(prompt, api_key, model_name)
    except Exception as e:
        logger.error(f"[Regenerate Error] {e}")
        msg = str(e).lower()
        if "429" in msg or "quota" in msg:
            raise HTTPException(429, "Daily generation limit reached. Please try again later.")
        raise HTTPException(500, "Couldn't regenerate this question. Please try again.")

    if "@@@ANSWER@@@" in resp_text:
        q_part, a_part = resp_text.split("@@@ANSWER@@@", 1)
        new_question, new_answer = q_part.strip(), a_part.strip()
    else:
        new_question, new_answer = resp_text.strip(), None

    return {
        "question": new_question,
        "answer": new_answer,
        "question_number": extract_question_number(payload.old_text),
    }


@router.post("/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
    start_page: int = Form(1),
    end_page: int = Form(5),
    user: dict = Depends(get_current_user),
):
    pdf_bytes = await file.read()
    text = extract_text_from_pdf(pdf_bytes, start_page, end_page)
    if not text.strip():
        raise HTTPException(400, "Couldn't extract any text from that page range. Try a different range or PDF.")
    return {"text": text, "char_count": len(text)}


@router.post("/generate")
def generate_paper(req: GeneratePaperRequest, user: dict = Depends(get_current_user)):
    is_pro = bool(user.get("is_pro"))
    papers_used = user.get("papers_generated", 0)

    if not is_pro and papers_used >= FREE_LIMIT:
        raise HTTPException(402, "Free trial expired. Please upgrade to Pro to keep generating papers.")

    prompt = build_question_prompt(req)
    api_key = settings.GEMINI_API_KEY
    model_name = get_working_model_name(api_key)

    try:
        resp_text = generate_gemini_content(prompt, api_key, model_name)
    except Exception as e:
        logger.error(f"[Generate Error] {e}")
        msg = str(e).lower()
        if "429" in msg or "quota" in msg:
            raise HTTPException(429, "Daily generation limit reached. Please try again later.")
        raise HTTPException(500, "Something went wrong generating the paper.")

    blocks = [b.strip() for b in resp_text.split("|||") if b.strip()]

    supabase.table("users").update({"papers_generated": papers_used + 1}).eq("username", user["username"]).execute()

    return {"blocks": blocks}


@router.get("/history")
def list_history(user: dict = Depends(get_current_user)):
    # Auto-delete papers older than 30 days. Done lazily here (rather than a
    # background scheduler) so it works reliably regardless of hosting
    # platform — no separate always-on process required.
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    try:
        supabase.table("papers").delete().eq("username", user["username"]).lt("date", cutoff).execute()
    except Exception as e:
        logger.error(f"[Auto-delete Error] {e}")

    res = supabase.table("papers").select("*").eq("username", user["username"]).order("id", desc=True).execute()
    return res.data


@router.post("/history", status_code=201)
def save_paper(payload: SavePaperRequest, user: dict = Depends(get_current_user)):
    data = {
        "username": user["username"],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "subject": payload.subject,
        "board": payload.board,
        "content": payload.content,
    }
    res = supabase.table("papers").insert(data).execute()
    return res.data[0] if res.data else data


@router.delete("/history/{paper_id}")
def delete_paper(paper_id: str, user: dict = Depends(get_current_user)):
    # Accept the ID as a plain string and parse it ourselves — letting
    # FastAPI enforce `int` directly on the path parameter produces a
    # confusing raw Pydantic error ("Input should be a valid integer...")
    # if anything odd ever reaches this route.
    try:
        paper_id_int = int(paper_id)
    except ValueError:
        raise HTTPException(400, "Invalid paper ID.")
    supabase.table("papers").delete().eq("id", paper_id_int).eq("username", user["username"]).execute()
    return {"message": "Deleted."}
