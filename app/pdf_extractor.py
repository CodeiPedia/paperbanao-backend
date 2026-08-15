import logging

import fitz  # PyMuPDF

logger = logging.getLogger("paperbanao")


def extract_text_from_pdf(pdf_bytes: bytes, start_page: int, end_page: int) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        start_index = max(0, start_page - 1)
        end_index = min(len(doc), end_page)
        text = ""
        for i in range(start_index, end_index):
            text += doc[i].get_text("text") + "\n"
        return text
    except Exception as e:
        logger.error(f"[PDF Extraction Error] {e}")
        return ""
