import logging
import os
import uuid
from datetime import datetime, UTC
from typing import Literal

from fastapi import APIRouter, Header, Depends, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from redis import Redis, ConnectionPool
from sqlalchemy.orm import Session

from api.auth import authenticate_request
from api.quota import check_and_increment_quota
from db.database import get_db
from db.models import TranslationJob
from workers.tasks import run_translation_pipeline
from workers.translator import SUPPORTED_TARGET_LANGUAGES

logger = logging.getLogger(__name__)

router = APIRouter()

_redis_pool = ConnectionPool.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
redis_client = Redis(connection_pool=_redis_pool)


LANGUAGES = [
    {"code": "es", "name": "Spanish", "native": "Español", "status": "available"},
    {"code": "pt", "name": "Portuguese", "native": "Português", "status": "available"},
    {"code": "ht", "name": "Haitian Creole", "native": "Kreyòl ayisyen", "status": "limited"},
    {"code": "zh", "name": "Chinese (Simplified)", "native": "中文", "status": "available"},
    {"code": "ko", "name": "Korean", "native": "한국어", "status": "available"},
    {"code": "ar", "name": "Arabic", "native": "العربية", "status": "available"},
    {"code": "fr", "name": "French", "native": "Français", "status": "available"},
    {"code": "pl", "name": "Polish", "native": "Polski", "status": "available"},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी", "status": "limited"},
    {"code": "ur", "name": "Urdu", "native": "اردو", "status": "limited"},
]


class TranslateRequest(BaseModel):
    content: str
    source_language: Literal["en"] = "en"
    target_language: str
    tier: Literal["instant", "reviewed", "certified"] = "instant"
    content_type: Literal["article", "broadcast", "social"] = "article"
    metadata: dict | None = None
    callback_url: AnyHttpUrl | None = None
    glossary_id: str | None = None


@router.get("/languages")
def get_languages():
    return {"languages": LANGUAGES}


@router.post("/translate", status_code=202)
def create_translation_job(
    request: TranslateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "missing_auth_header"})
    ctx = authenticate_request(authorization=authorization, db=db, redis_client=redis_client)

    if request.target_language not in SUPPORTED_TARGET_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail={"error": "unsupported_language", "supported": sorted(SUPPORTED_TARGET_LANGUAGES)},
        )

    if len(request.content) > 50_000:
        raise HTTPException(status_code=422, detail={"error": "content_too_large"})

    job_id = str(uuid.uuid4())
    job = TranslationJob(
        id=job_id,
        org_id=ctx.org_id,
        api_key_id=ctx.api_key_id,
        source_language=request.source_language,
        target_language=request.target_language,
        tier=request.tier,
        content=request.content,
        content_type=request.content_type,
        metadata_json=request.metadata,
        callback_url=str(request.callback_url) if request.callback_url else None,
        glossary_id=request.glossary_id,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)  # ensure created_at is populated from DB

    check_and_increment_quota(org_id=ctx.org_id, daily_quota=ctx.daily_quota, redis_client=redis_client)

    try:
        run_translation_pipeline.delay(job_id)
    except Exception as e:
        logger.error("Failed to enqueue pipeline for job %s: %s", job_id, e)
        job.status = "failed"
        job.error_message = "Failed to enqueue translation job"
        db.commit()
        raise HTTPException(status_code=503, detail={"error": "service_unavailable", "job_id": job_id})

    return {
        "job_id": job_id,
        "status": "queued",
        "tier": request.tier,
        "source_language": request.source_language,
        "target_language": request.target_language,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "links": {"self": f"/v1/translate/{job_id}"},
    }


@router.get("/translate/{job_id}")
def get_job(
    job_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "missing_auth_header"})
    ctx = authenticate_request(authorization=authorization, db=db, redis_client=redis_client)
    job = db.get(TranslationJob, job_id)

    if not job or job.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail={"error": "job_not_found"})

    response = {
        "job_id": job.id,
        "status": job.status,
        "tier": job.tier,
        "source_language": job.source_language,
        "target_language": job.target_language,
        "word_count": job.word_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }

    if job.status == "complete":
        response["translated_content"] = job.translated_content
        response["quality_scores"] = job.quality_scores_json

    return response
