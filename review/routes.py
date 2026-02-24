from datetime import datetime, UTC

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import ReviewAssignment, Reviewer, TranslationJob
from workers.tasks import deliver_webhook

router = APIRouter()
templates = Jinja2Templates(directory="review/templates")


@router.get("/", response_class=HTMLResponse)
def review_list(request: Request, db: Session = Depends(get_db)):
    jobs = (
        db.query(TranslationJob)
        .filter(TranslationJob.status == "in_review")
        .order_by(TranslationJob.created_at)
        .all()
    )
    return templates.TemplateResponse("review_list.html", {"request": request, "jobs": jobs})


@router.get("/{job_id}", response_class=HTMLResponse)
def review_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    job = db.get(TranslationJob, job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)
    return templates.TemplateResponse("review.html", {"request": request, "job": job})


@router.post("/{job_id}/approve")
def approve_translation(
    job_id: str,
    edited_content: str = Form(...),
    db: Session = Depends(get_db),
):
    job = db.get(TranslationJob, job_id)
    if not job:
        return {"error": "not found"}
    job.translated_content = edited_content
    job.status = "reviewed" if job.tier == "reviewed" else "complete"
    job.completed_at = datetime.now(UTC)
    db.commit()

    if job.callback_url and job.status == "complete":
        deliver_webhook.delay(job.callback_url, job_id, {
            "job_id": job_id,
            "status": job.status,
            "translated_content": job.translated_content,
            "quality_scores": job.quality_scores_json,
        })

    return {"status": job.status}
