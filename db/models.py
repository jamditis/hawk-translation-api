from datetime import datetime, UTC
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[Optional[str]] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    daily_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, insert_default=lambda: datetime.now(UTC))

    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="organization")
    jobs: Mapped[list["TranslationJob"]] = relationship("TranslationJob", back_populates="organization")

    def __init__(self, **kwargs):
        kwargs.setdefault("tier", "instant")
        kwargs.setdefault("daily_quota", 50)
        kwargs.setdefault("active", True)
        super().__init__(**kwargs)


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[Optional[str]] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, insert_default=lambda: datetime.now(UTC))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="api_keys")

    def __init__(self, **kwargs):
        kwargs.setdefault("active", True)
        super().__init__(**kwargs)


class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    id: Mapped[Optional[str]] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=True)
    api_key_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("api_keys.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_language: Mapped[str] = mapped_column(String(10), nullable=False)
    target_language: Mapped[str] = mapped_column(String(10), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    translated_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_scores_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    callback_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    glossary_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("glossaries.id"), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, insert_default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        insert_default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="jobs")

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "queued")
        kwargs.setdefault("content_type", "article")
        super().__init__(**kwargs)


class Glossary(Base):
    __tablename__ = "glossaries"

    id: Mapped[Optional[str]] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    language_pair: Mapped[str] = mapped_column(String(10), nullable=False)
    terms_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    org_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, insert_default=lambda: datetime.now(UTC))

    def __init__(self, **kwargs):
        kwargs.setdefault("terms_json", {})
        super().__init__(**kwargs)


class Reviewer(Base):
    __tablename__ = "reviewers"

    id: Mapped[Optional[str]] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    language_pairs_json: Mapped[list] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, insert_default=lambda: datetime.now(UTC))

    def __init__(self, **kwargs):
        kwargs.setdefault("language_pairs_json", [])
        kwargs.setdefault("active", True)
        super().__init__(**kwargs)


class ReviewAssignment(Base):
    __tablename__ = "review_assignments"

    id: Mapped[Optional[str]] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("translation_jobs.id"), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviewers.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, insert_default=lambda: datetime.now(UTC))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    diff_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[Optional[str]] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("translation_jobs.id"), nullable=False)
    callback_url: Mapped[str] = mapped_column(String(500), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    last_response_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "pending")
        kwargs.setdefault("attempt_count", 0)
        super().__init__(**kwargs)
