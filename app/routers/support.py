import logging
import time
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.gemini_client import generate_gemini_content, get_working_model_name
from app.config import settings

router = APIRouter(prefix="/support", tags=["support"])
logger = logging.getLogger("paperbanao")

# This is what the assistant is allowed to "know" — kept in one place so
# it's easy to update as the product changes, and so the AI can't drift
# into inventing features PaperBanao doesn't actually have.
PAPERBANAO_KNOWLEDGE = """
You are the friendly support assistant for PaperBanao (paperbanao.in), an
AI-powered question paper generator built for Indian teachers and coaching
institutes, especially BSEB (Bihar Board) and CBSE/NCERT.

WHAT PAPERBANAO DOES:
- Generates full question papers: MCQs, fill-in-the-blanks, true/false,
  short answer, and long answer questions, each with a configurable count,
  marks, and difficulty (Easy/Medium/Hard).
- Automatically generates a matching answer key.
- Supports Hindi, English, or Bilingual output.
- A dedicated "BSEB Board" builder lets teachers pick Class, Subject, and
  specific chapters from a saved syllabus list — questions are generated
  STRICTLY from those chapters only, never drifting to other topics. A
  "Select all" option can generate a full-syllabus practice paper.
- For BSEB Class 10 Mathematics specifically, chapters show a ⭐ badge
  indicating high exam weightage (based on real BSEB exam-pattern
  research), to help teachers focus revision.
- Some Geometry/Statistics questions (right-angled triangles, circles,
  bar-graph statistics) can include an accurate auto-generated diagram.
- "Digitize" feature: upload photos of a handwritten or scanned paper and
  get a clean, editable digital version with Subject/Class/Time/Marks
  fields.
- Every paper can be branded with the teacher's own institute name,
  address, contact number, and logo (set once in Settings).
- Generated papers are printed via the browser's own Print / Save-as-PDF
  — this is deliberate, since it renders Hindi text more reliably than
  server-generated PDFs.
- Cloud History saves papers for 30 days, with a Print button to reprint
  any saved paper.
- Visitors can explore the Dashboard, BSEB Board, and Digitize pages and
  fill in the whole form WITHOUT signing up — an account is only needed
  when they click the final "Generate" button, and whatever they'd
  filled in is preserved through signup.

PRICING:
- Free plan: 5 question papers total, no card required.
- Pro plan: ₹99 for 30 days of unlimited papers (fair-use limit of 75
  papers/month to prevent abuse). This is a ONE-TIME payment — it does
  NOT auto-renew. Teachers only pay again if they choose to.
- Payments are processed via Razorpay.

SUPPORT:
- Email: sk142464@gmail.com
- Phone: +91 93100 38172
- Refunds: generally not offered once Pro is activated (see the Refund
  Policy page), except for genuine billing errors like double charges.

TONE AND RULES:
- Answer in whichever language the user writes in (Hindi, Hinglish, or
  English) — match their language naturally.
- Be warm, concise, and helpful — a few sentences, not an essay, unless
  the question genuinely needs more detail.
- If you don't know the answer to something specific (e.g. a very
  technical detail not listed above), say so honestly and point them to
  contact support at sk142464@gmail.com — do NOT invent features,
  pricing, or policies that aren't listed above.
- You are not able to actually perform actions (like generating a paper,
  changing settings, or processing a refund) — you can only explain how
  the person can do it themselves on the site.
"""


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class SupportChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


# Simple in-memory rate limiting per IP isn't available without request
# context here, so we rate-limit globally instead — generous enough for
# real usage, but enough to prevent a runaway loop from burning API
# credits if something goes wrong client-side.
_last_reset = [time.time()]
_request_count = [0]
_lock = threading.Lock()
MAX_REQUESTS_PER_MINUTE = 30


def _check_global_rate_limit():
    with _lock:
        now = time.time()
        if now - _last_reset[0] > 60:
            _last_reset[0] = now
            _request_count[0] = 0
        _request_count[0] += 1
        if _request_count[0] > MAX_REQUESTS_PER_MINUTE:
            raise HTTPException(429, "The support assistant is busy right now. Please try again in a minute, or email sk142464@gmail.com.")


@router.post("/chat")
def support_chat(payload: SupportChatRequest):
    _check_global_rate_limit()

    if len(payload.message.strip()) == 0:
        raise HTTPException(400, "Please type a question.")
    if len(payload.message) > 1000:
        raise HTTPException(400, "That message is too long — please keep it under 1000 characters.")

    # Keep only the last few turns so the prompt doesn't grow unbounded.
    recent_history = payload.history[-6:]
    conversation = "\n".join(f"{m.role}: {m.content}" for m in recent_history)

    prompt = (
        PAPERBANAO_KNOWLEDGE
        + "\n\nCONVERSATION SO FAR:\n"
        + conversation
        + f"\n\nuser: {payload.message}\n\nReply as the assistant. Output ONLY your reply text, no labels or prefixes."
    )

    api_key = settings.GEMINI_API_KEY
    model_name = get_working_model_name(api_key)
    try:
        reply = generate_gemini_content(prompt, api_key, model_name)
    except Exception as e:
        logger.error(f"[Support Chat Error] {e}")
        raise HTTPException(500, "Something went wrong. Please try again or email sk142464@gmail.com.")

    return {"reply": reply.strip()}
