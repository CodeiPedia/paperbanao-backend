import base64
import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form

from app.database import supabase
from app.security import get_current_user

router = APIRouter(prefix="/institution", tags=["institution"])
logger = logging.getLogger("paperbanao")


@router.get("/defaults")
def get_defaults(user: dict = Depends(get_current_user)):
    res = supabase.table("users").select(
        "default_inst_name, default_inst_address, default_inst_contact, "
        "default_teacher_name, default_paper_language, default_board_format, "
        "default_custom_instructions, default_reading_time, "
        "default_logo_base64, default_logo_mimetype"
    ).eq("username", user["username"]).execute()
    return res.data[0] if res.data else {}


@router.post("/defaults")
async def save_defaults(
    inst_name: str = Form(""),
    inst_address: str = Form(""),
    inst_contact: str = Form(""),
    teacher_name: str = Form(""),
    paper_language: str = Form("English"),
    board_format: str = Form("Standard"),
    custom_instructions: str = Form(""),
    reading_time: str = Form(""),
    logo: UploadFile = File(None),
    user: dict = Depends(get_current_user),
):
    update_data = {
        "default_inst_name": inst_name,
        "default_inst_address": inst_address,
        "default_inst_contact": inst_contact,
        "default_teacher_name": teacher_name,
        "default_paper_language": paper_language,
        "default_board_format": board_format,
        "default_custom_instructions": custom_instructions,
        "default_reading_time": reading_time,
    }
    if logo is not None:
        logo_bytes = await logo.read()
        if logo_bytes:
            update_data["default_logo_base64"] = base64.b64encode(logo_bytes).decode()
            update_data["default_logo_mimetype"] = logo.content_type

    supabase.table("users").update(update_data).eq("username", user["username"]).execute()
    return {"message": "Saved."}
