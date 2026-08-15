import base64
import logging
from io import BytesIO

import requests

from app.config import settings

logger = logging.getLogger("paperbanao")

DEFAULT_MODEL = "gemini-1.5-flash"


def get_working_model_name(api_key: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url, timeout=30)
        res.raise_for_status()
        models = res.json().get("models", [])
        valid = [m["name"] for m in models if "generateContent" in m.get("supportedGenerationMethods", [])]
        flash = [m for m in valid if "1.5-flash" in m]
        return (flash[0] if flash else valid[0]).replace("models/", "") if valid else DEFAULT_MODEL
    except Exception as e:
        logger.error(f"[get_working_model_name Error] {e}")
        return DEFAULT_MODEL


def generate_gemini_content(prompt: str, api_key: str, model_name: str = DEFAULT_MODEL, images=None) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    parts = [{"text": prompt}]
    if images:
        for img in images:
            buffered = BytesIO()
            if img.mode != "RGB":
                img = img.convert("RGB")  # PNGs with alpha can't be saved as JPEG otherwise
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_str}})

    payload = {"contents": [{"parts": parts}]}
    response = requests.post(url, headers=headers, json=payload, timeout=90)

    if response.status_code == 200:
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise Exception("Unexpected response format from Gemini API.")
    else:
        try:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
        except ValueError:
            error_msg = response.text[:200]
        raise Exception(f"API Error {response.status_code}: {error_msg}")

