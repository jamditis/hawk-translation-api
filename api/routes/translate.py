import uuid
from datetime import datetime, UTC
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from redis import Redis
import os

from api.auth import authenticate_request
from api.quota import check_quota, increment_quota
from db.database import get_db
from db.models import TranslationJob
from workers.tasks import run_translation_pipeline
from workers.translator import SUPPORTED_TARGET_LANGUAGES

router = APIRouter()


def _get_redis():
    return Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


LANGUAGES = [
    {"code": "es", "name": "Spanish", "native": "Español"},
    {"code": "pt", "name": "Portuguese", "native": "Português"},
    {"code": "ht", "name": "Haitian Creole", "native": "Kreyòl ayisyen"},
    {"code": "zh", "name": "Chinese (Simplified)", "native": "中文"},
    {"code": "ko", "name": "Korean", "native": "한국어"},
    {"code": "ar", "name": "Arabic", "native": "العربية"},
    {"code": "fr", "name": "French", "native": "Français"},
    {"code": "pl", "name": "Polish", "native": "Polski"},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी"},
    {"code": "ur", "name": "Urdu", "native": "اردو"},
]


class TranslateRequest(BaseModel):
    content: str
    source_language: str = "en"
    target_language: str
    tier: str = "instant"
    content_type: str = "article"
    metadata: dict | None = None
    callback_url: str | None = None
    glossary_id: str | None = None


@router.get("/languages")
def get_languages():
    return {"languages": LANGUAGES}


@router.post("/translate", status_code=202)
def create_translation_job(
    request: TranslateRequest,
    authorization: str | None = Header(default=None),
):
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "missing_auth_header"})
    db = next(get_db())
    redis_client = _get_redis()
    ctx = authenticate_request(authorization=authorization, db=db, redis_client=redis_client)
    check_quota(org_id=ctx.org_id, daily_quota=ctx.daily_quota, redis_client=redis_client)

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
        callback_url=request.callback_url,
        glossary_id=request.glossary_id,
        status="queued",
    )
    db.add(job)
    db.commit()

    increment_quota(org_id=ctx.org_id, redis_client=redis_client)
    run_translation_pipeline.delay(job_id)

    return {
        "job_id": job_id,
        "status": "queued",
        "tier": request.tier,
        "source_language": request.source_language,
        "target_language": request.target_language,
        "created_at": datetime.now(UTC).isoformat(),
        "links": {"self": f"/v1/translate/{job_id}"},
    }


@router.get("/translate/{job_id}")
def get_job(
    job_id: str,
    authorization: str | None = Header(default=None),
):
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "missing_auth_header"})
    db = next(get_db())
    redis_client = _get_redis()
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
