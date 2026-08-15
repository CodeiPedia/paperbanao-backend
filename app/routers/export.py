import base64
import logging
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.database import supabase
from app.security import get_current_user
from app.document_builder import create_a4_html, create_word_docx, html_to_pdf, StoredLogo

router = APIRouter(prefix="/export", tags=["export"])
logger = logging.getLogger("paperbanao")


def safe_content_disposition(filename: str) -> str:
    """Builds a Content-Disposition header that works for ANY filename,
    including Hindi/Devanagari or other non-ASCII subject names. HTTP
    headers can only contain Latin-1 bytes, so a raw Unicode filename (e.g.
    'गणित_Paper.pdf') would otherwise crash the response entirely. We send
    a safe ASCII fallback name plus the real Unicode name via the standard
    RFC 5987 filename* parameter, which browsers use when available."""
    ascii_fallback = re.sub(r'[^\x20-\x7E]', '', filename).strip() or "paper"
    ascii_fallback = ascii_fallback.replace('"', "")
    encoded = quote(filename)
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'


class ExportRequest(BaseModel):
    content: str
    subject: str = "Subject"
    class_name: str = "Class"
    marks: str = ""
    exam_time: str = "2 Hours"
    topics: str = ""


def _get_institution_details(username: str):
    res = supabase.table("users").select(
        "default_inst_name, default_inst_address, default_inst_contact, "
        "default_teacher_name, default_logo_base64, default_logo_mimetype"
    ).eq("username", username).execute()

    if not res.data:
        return "PaperBanao", "", "", "", None

    row = res.data[0]
    logo = None
    if row.get("default_logo_base64"):
        try:
            logo = StoredLogo(base64.b64decode(row["default_logo_base64"]), row.get("default_logo_mimetype") or "image/png")
        except Exception as e:
            logger.error(f"[Logo Decode Error] {e}")

    return (
        row.get("default_inst_name") or "PaperBanao",
        row.get("default_inst_address") or "",
        row.get("default_inst_contact") or "",
        row.get("default_teacher_name") or "",
        logo,
    )


@router.post("/{fmt}")
def export_paper(fmt: str, payload: ExportRequest, user: dict = Depends(get_current_user)):
    if fmt not in ("html", "docx", "pdf"):
        raise HTTPException(400, "Format must be html, docx, or pdf.")

    inst_name, inst_address, inst_contact, teacher_name, logo = _get_institution_details(user["username"])

    html = create_a4_html(
        payload.content, inst_name, inst_address, inst_contact, teacher_name, logo,
        False, payload.subject, payload.class_name, payload.marks, payload.exam_time, payload.topics
    )

    if fmt == "html":
        return Response(content=html, media_type="text/html", headers={
            "Content-Disposition": safe_content_disposition(f"{payload.subject}_Paper.html")
        })

    if fmt == "docx":
        word_bytes = create_word_docx(
            payload.content, inst_name, inst_address, inst_contact, teacher_name, logo,
            False, payload.subject, payload.class_name, payload.marks, payload.exam_time, payload.topics
        )
        return Response(content=word_bytes, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={
            "Content-Disposition": safe_content_disposition(f"{payload.subject}_Paper.docx")
        })

    # pdf
    pdf_bytes = html_to_pdf(html)
    if not pdf_bytes:
        raise HTTPException(500, "Couldn't generate PDF. Try Word or HTML instead.")
    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": safe_content_disposition(f"{payload.subject}_Paper.pdf")
    })
