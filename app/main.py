import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, papers, curriculum, institution, export, digitize, payments

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="PaperBanao API", version="1.0.0")

origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(papers.router)
app.include_router(curriculum.router)
app.include_router(institution.router)
app.include_router(export.router)
app.include_router(digitize.router)
app.include_router(payments.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "PaperBanao API"}
