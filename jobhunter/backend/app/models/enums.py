"""Centralized status and type enums for all models.

Using StrEnum so values serialize to plain strings - no DB migration needed.
"""

from enum import StrEnum

# ── Company ──────────────────────────────────────────────────────────


class CompanyStatus(StrEnum):
    SUGGESTED = "suggested"
    APPROVED = "approved"
    REJECTED = "rejected"


class ResearchStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Outreach ─────────────────────────────────────────────────────────


class MessageStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"
    REJECTED = "rejected"


class MessageChannel(StrEnum):
    EMAIL = "email"
    LINKEDIN = "linkedin"


class MessageType(StrEnum):
    INITIAL = "initial"
    FOLLOWUP_1 = "followup_1"
    FOLLOWUP_2 = "followup_2"
    BREAKUP = "breakup"


class EventType(StrEnum):
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    COMPLAINED = "complained"


# ── Pending Actions ──────────────────────────────────────────────────


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ActionType(StrEnum):
    SEND_EMAIL = "send_email"
    SEND_FOLLOWUP = "send_followup"
    SEND_LINKEDIN = "send_linkedin"


# ── Interview Prep ───────────────────────────────────────────────────


class PrepType(StrEnum):
    COMPANY_QA = "company_qa"
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    CULTURE_FIT = "culture_fit"
    SALARY_NEGOTIATION = "salary_negotiation"
    MOCK_INTERVIEW = "mock_interview"


class SessionStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class MockRole(StrEnum):
    CANDIDATE = "candidate"
    INTERVIEWER = "interviewer"
    FEEDBACK = "feedback"


# ── Job Postings ─────────────────────────────────────────────────────


class JobPostingStatus(StrEnum):
    PENDING = "pending"
    ANALYZED = "analyzed"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Resume ───────────────────────────────────────────────────────────


class ParseStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class SkillCategory(StrEnum):
    EXPLICIT = "explicit"
    TRANSFERABLE = "transferable"
    ADJACENT = "adjacent"


# ── Contact ──────────────────────────────────────────────────────────


class RoleType(StrEnum):
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    TEAM_LEAD = "team_lead"


# ── Incidents ────────────────────────────────────────────────────────

class IncidentCategory(StrEnum):
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    QUESTION = "question"
    OTHER = "other"

class GitHubSyncStatus(StrEnum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
