import logging
from io import BytesIO

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from PIL import Image

from app.security import get_current_user
from app.gemini_client import generate_gemini_content, get_working_model_name
from app.config import settings
from app.database import supabase

router = APIRouter(prefix="/digitize", tags=["digitize"])
logger = logging.getLogger("paperbanao")

FREE_LIMIT = 5

DIGITIZE_PROMPT = (
    "You are digitizing a handwritten or scanned question paper from the attached image(s). "
    "Transcribe it faithfully â€” preserve the original question numbering, order, sections, and "
    "marks exactly as written. Do not invent new questions, do not change the meaning, and do not "
    "add a title, institute name, header, or footer. Only fix obvious spelling/OCR mistakes. "
    "Separate each distinct question with the delimiter ||| on its own line."
)


@router.post("")
async def digitize_paper(files: list[UploadFile] = File(...), user: dict = Depends(get_current_user)):
    is_pro = bool(user.get("is_pro"))
    papers_used = user.get("papers_generated", 0)
    if not is_pro and papers_used >= FREE_LIMIT:
        raise HTTPException(402, "Free trial expired. Please upgrade to Pro to keep digitizing papers.")

    if not files:
        raise HTTPException(400, "Please upload at least one photo.")

    images = []
    for f in files:
        try:
            data = await f.read()
            images.append(Image.open(BytesIO(data)))
        except Exception as e:
            logger.error(f"[Digitize Image Read Error] {e}")
            raise HTTPException(400, f"Couldn't read image: {f.filename}")

    api_key = settings.GEMINI_API_KEY
    model_name = get_working_model_name(api_key)

    try:
        resp_text = generate_gemini_content(DIGITIZE_PROMPT, api_key, model_name, images=images)
    except Exception as e:
        logger.error(f"[Digitize Error] {e}")
        msg = str(e).lower()
        if "429" in msg or "quota" in msg:
            raise HTTPException(429, "Daily generation limit reached. Please try again later.")
        raise HTTPException(500, "Couldn't read that paper. Try clearer/well-lit photos.")

    blocks = [b.strip() for b in resp_text.split("|||") if b.strip()]

    supabase.table("users").update({"papers_generated": papers_used + 1}).eq("username", user["username"]).execute()

    return {"blocks": blocks}

