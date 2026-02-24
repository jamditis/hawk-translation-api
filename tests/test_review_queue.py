from unittest.mock import MagicMock, call, patch
import uuid


def test_assigns_available_reviewer():
    mock_db = MagicMock()
    reviewer = MagicMock()
    reviewer.id = "rev-1"
    reviewer.language_pairs_json = ["en-es", "en-fr"]
    reviewer.active = True

    mock_db.query.return_value.filter.return_value.all.return_value = [reviewer]
    from review.queue import assign_reviewer

    result = assign_reviewer(job_id="job-1", language_pair="en-es", db=mock_db)
    assert result == "rev-1"


def test_no_available_reviewer_returns_none():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []
    from review.queue import assign_reviewer

    result = assign_reviewer(job_id="job-1", language_pair="en-zh", db=mock_db)
    assert result is None


def test_skips_reviewer_without_matching_language_pair():
    """A reviewer active for en-fr is not assigned to an en-es job."""
    mock_db = MagicMock()
    reviewer = MagicMock()
    reviewer.id = "rev-2"
    reviewer.language_pairs_json = ["en-fr", "en-de"]
    reviewer.active = True

    mock_db.query.return_value.filter.return_value.all.return_value = [reviewer]
    from review.queue import assign_reviewer

    result = assign_reviewer(job_id="job-1", language_pair="en-es", db=mock_db)
    assert result is None
    mock_db.add.assert_not_called()


def test_creates_review_assignment_in_db():
    """When a reviewer is found, a ReviewAssignment is added to the DB and committed."""
    mock_db = MagicMock()
    reviewer = MagicMock()
    reviewer.id = "rev-3"
    reviewer.language_pairs_json = ["en-pt"]
    reviewer.active = True

    mock_db.query.return_value.filter.return_value.all.return_value = [reviewer]
    from review.queue import assign_reviewer

    assign_reviewer(job_id="job-42", language_pair="en-pt", db=mock_db)

    mock_db.add.assert_called_once()
    assignment = mock_db.add.call_args[0][0]
    assert assignment.job_id == "job-42"
    assert assignment.reviewer_id == "rev-3"
    assert assignment.role == "reviewer"
    mock_db.commit.assert_called_once()


def test_assigns_first_eligible_reviewer():
    """When multiple reviewers qualify, the first one in the list is assigned."""
    mock_db = MagicMock()
    reviewer_a = MagicMock()
    reviewer_a.id = "rev-a"
    reviewer_a.language_pairs_json = ["en-es"]
    reviewer_b = MagicMock()
    reviewer_b.id = "rev-b"
    reviewer_b.language_pairs_json = ["en-es"]

    mock_db.query.return_value.filter.return_value.all.return_value = [reviewer_a, reviewer_b]
    from review.queue import assign_reviewer

    result = assign_reviewer(job_id="job-5", language_pair="en-es", db=mock_db)
    assert result == "rev-a"
    mock_db.add.assert_called_once()
