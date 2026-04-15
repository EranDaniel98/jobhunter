"""Verify Candidate.last_seen_at exists as a nullable timezone-aware DateTime."""
from sqlalchemy import DateTime

from app.models.candidate import Candidate


def test_candidate_has_last_seen_at_column():
    col = Candidate.__table__.c.get("last_seen_at")
    assert col is not None, "last_seen_at column missing on candidates"


def test_last_seen_at_is_nullable_datetime_tz():
    col = Candidate.__table__.c["last_seen_at"]
    assert col.nullable is True
    assert isinstance(col.type, DateTime)
    assert col.type.timezone is True


def test_last_seen_at_is_indexed():
    col = Candidate.__table__.c["last_seen_at"]
    assert col.index is True
