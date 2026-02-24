import uuid
from datetime import datetime, UTC

from sqlalchemy.orm import Session

from db.models import Reviewer, ReviewAssignment


def assign_reviewer(job_id: str, language_pair: str, db: Session) -> str | None:
    """Find an active reviewer for the language pair and create an assignment.

    Queries active reviewers, matches on language pair, creates a ReviewAssignment,
    and returns the reviewer ID. Returns None if no reviewer is available.
    """
    reviewers = db.query(Reviewer).filter(Reviewer.active == True).all()

    for reviewer in reviewers:
        if language_pair in reviewer.language_pairs_json:
            assignment = ReviewAssignment(
                id=str(uuid.uuid4()),
                job_id=job_id,
                reviewer_id=reviewer.id,
                role="reviewer",
                assigned_at=datetime.now(UTC),
            )
            db.add(assignment)
            db.commit()
            return reviewer.id

    return None
