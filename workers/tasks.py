import logging
import os
from datetime import datetime, UTC

import httpx

from db.database import SessionLocal
from db.models import Glossary, TranslationJob
from workers.celery_app import celery_app
from workers.glossary import apply_glossary
from workers.scorer import score_translation
from workers.segmenter import reassemble_html, segment_html
from workers.translator import translate_segments

logger = logging.getLogger(__name__)


def get_db_session():
    return SessionLocal()


def send_webhook(callback_url: str, job_id: str, payload: dict) -> None:
    if not callback_url.startswith(("http://", "https://")):
        logger.warning("Skipping webhook for job %s: invalid URL scheme", job_id)
        return
    try:
        httpx.post(callback_url, json=payload, timeout=10.0)
    except Exception as e:
        logger.warning("Webhook delivery failed for job %s: %s", job_id, e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_translation_pipeline(self, job_id: str) -> None:
    db = None
    try:
        db = get_db_session()
        job = None
        job = db.get(TranslationJob, job_id)
        if not job:
            logger.error("Job %s not found", job_id)
            return

        # Stage 1: segment HTML content
        job.status = "machine_translated"
        db.commit()
        segments = segment_html(job.content)

        # Stage 2: apply glossary substitutions
        glossary_terms = {}
        if job.glossary_id:
            glossary = db.get(Glossary, job.glossary_id)
            if glossary:
                glossary_terms = glossary.terms_json
        for seg in segments:
            seg["text"] = apply_glossary(seg["text"], glossary_terms)

        # Stage 3: translate via DeepL
        deepl_key = os.getenv("DEEPL_API_KEY", "")
        segments = translate_segments(
            segments, target_language=job.target_language, api_key=deepl_key
        )

        # Stage 4: reassemble translated HTML
        job.translated_content = reassemble_html(segments)
        job.word_count = sum(len(s["text"].split()) for s in segments)

        # Stage 5: quality scoring (non-blocking — None result is fine)
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

        # Stage 6: mark complete (instant) or queue for review
        if job.tier == "instant":
            job.status = "complete"
            job.completed_at = datetime.now(UTC)
        else:
            job.status = "in_review"

        db.commit()

        # Stage 7: fire webhook if job is complete
        if job.callback_url and job.status == "complete":
            send_webhook(job.callback_url, job_id, {
                "job_id": job_id,
                "status": job.status,
                "translated_content": job.translated_content,
                "quality_scores": job.quality_scores_json,
            })

    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        try:
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        if db is not None:
            db.close()
