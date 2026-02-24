import logging
import os
from datetime import datetime, UTC

import httpx

from db.database import SessionLocal
from db.models import Glossary, TranslationJob
from review.queue import assign_reviewer
from workers.celery_app import celery_app
from workers.glossary import apply_glossary
from workers.scorer import score_translation
from workers.segmenter import reassemble_html, segment_html
from workers.translator import translate_segments

logger = logging.getLogger(__name__)

RETRY_COUNTDOWNS = [30, 120, 600]
WEBHOOK_RETRY_COUNTDOWNS = [300, 1800, 7200, 28800, 57600]


def get_db_session():
    return SessionLocal()


@celery_app.task(bind=True, max_retries=5)
def deliver_webhook(self, callback_url: str, job_id: str, payload: dict) -> None:
    if not callback_url.startswith(("http://", "https://")):
        logger.warning("Skipping webhook for job %s: invalid URL scheme", job_id)
        return
    try:
        response = httpx.post(callback_url, json=payload, timeout=10.0)
        if response.status_code >= 300:
            raise ValueError(f"Webhook returned {response.status_code}")
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.warning("Webhook delivery abandoned for job %s", job_id)
            return
        countdown = WEBHOOK_RETRY_COUNTDOWNS[min(self.request.retries, len(WEBHOOK_RETRY_COUNTDOWNS) - 1)]
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(bind=True, max_retries=3)
def run_translation_pipeline(self, job_id: str) -> None:
    db = None
    job = None
    try:
        db = get_db_session()
        job = db.get(TranslationJob, job_id)
        if not job:
            logger.error("Job %s not found", job_id)
            return

        # --- Machine draft pipeline ---
        # Stages 1-5 generate a machine draft and flag segments for human
        # translator attention. This draft is either delivered directly
        # (instant tier) or handed off to human translators for review.

        # Stage 1: segment HTML content into translatable units
        job.status = "translating"
        db.commit()
        segments = segment_html(job.content)

        # Stage 2: apply glossary substitutions (proper nouns, gov titles, place names)
        glossary_terms = {}
        if job.glossary_id:
            glossary = db.get(Glossary, job.glossary_id)
            if glossary:
                glossary_terms = glossary.terms_json
        for seg in segments:
            seg["text"] = apply_glossary(seg["text"], glossary_terms)

        # Stage 3: generate machine draft via DeepL (or Google for ht/hi/ur)
        deepl_key = os.getenv("DEEPL_API_KEY", "")
        segments = translate_segments(
            segments, target_language=job.target_language, api_key=deepl_key
        )

        # Stage 4: reassemble translated HTML
        job.translated_content = reassemble_html(segments)
        # word_count reflects source segment word count (post-glossary, pre-translation) for billing
        job.word_count = sum(len(s["text"].split()) for s in segments)
        job.status = "machine_translated"
        db.commit()

        # Stage 5: AI quality scoring — flags segments for human translator attention
        # Segments scoring below 3.0 are marked needs_review so human translators
        # can prioritize their effort. Non-blocking: None result is fine.
        job.status = "scoring"
        db.commit()

        all_scores = []
        for seg in segments:
            score = score_translation(
                original=seg["text"],
                translated=seg.get("translated", ""),
                target_lang=job.target_language,
            )
            if score:
                all_scores.append({
                    "index": seg["index"],
                    "overall": score.overall,
                    "fluency": score.fluency,
                    "accuracy": score.accuracy,
                    "flags": score.flags,
                    "needs_review": score.needs_review,
                })

        job.quality_scores_json = all_scores if all_scores else None

        # Stage 6: instant tier completes here; reviewed/certified tiers hand off
        # to human translators for review, editing, and certification
        if job.tier == "instant":
            job.status = "complete"
            job.completed_at = datetime.now(UTC)
        else:
            # Queue for human translator review — this is where the real
            # translation quality work happens
            job.status = "in_review"
            language_pair = f"{job.source_language}-{job.target_language}"
            assign_reviewer(job_id=job.id, language_pair=language_pair, db=db)

        db.commit()

        # Stage 7: fire webhook if job is complete
        if job.callback_url and job.status == "complete":
            deliver_webhook.delay(job.callback_url, job_id, {
                "job_id": job_id,
                "status": job.status,
                "translated_content": job.translated_content,
                "quality_scores": job.quality_scores_json,
            })

    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        is_final_failure = self.request.retries >= self.max_retries
        try:
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)
                db.commit()
                if is_final_failure and job.callback_url:
                    deliver_webhook.delay(job.callback_url, job_id, {
                        "job_id": job_id,
                        "status": "failed",
                        "error": str(exc),
                    })
        except Exception as db_exc:
            logger.warning("Failed to persist failure status for job %s: %s", job_id, db_exc)
        if is_final_failure:
            raise exc
        raise self.retry(exc=exc, countdown=RETRY_COUNTDOWNS[min(self.request.retries, len(RETRY_COUNTDOWNS) - 1)])
    finally:
        if db is not None:
            db.close()
