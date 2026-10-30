"""Database models for CivicAI.

All workflow changes are persisted here; the browser never owns the source of
truth for complaint status, assignment or history.
"""
import json
from datetime import datetime, timezone

from extensions import db

CATEGORIES = [
    "Road Damage",
    "Waterlogging",
    "Garbage and Waste",
    "Drainage",
    "Streetlight",
    "Public Safety",
    "Other",
]

STATUSES = ["Submitted", "Under Review", "Assigned", "In Progress", "Resolved"]
PRIORITY_LEVELS = ["Low", "Medium", "High", "Critical"]

DEPARTMENTS = [
    "Road Maintenance",
    "Stormwater & Drainage",
    "Sanitation",
    "Electrical Services",
    "Public Safety Cell",
    "General Administration",
]


def utcnow():
    """Naive UTC timestamp, stored consistently in SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)

    ai_summary = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(40), nullable=False, index=True)
    category_confidence = db.Column(db.Float, default=0.0)
    priority_score = db.Column(db.Integer, nullable=False, index=True)
    priority_level = db.Column(db.String(20), nullable=False, index=True)
    priority_explanation = db.Column(db.Text, nullable=False)
    priority_factors = db.Column(db.Text, default="[]")
    recommended_department = db.Column(db.String(80), nullable=False)
    ai_engine = db.Column(db.String(120), default="Local rules")
    ai_notes = db.Column(db.Text, default="")

    image_path = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    address = db.Column(db.String(250))

    status = db.Column(db.String(30), nullable=False, default="Submitted", index=True)
    assigned_department = db.Column(db.String(80))
    duplicate_of_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=True)

    priority_overridden = db.Column(db.Boolean, default=False)
    original_priority_score = db.Column(db.Integer)
    original_priority_level = db.Column(db.String(20))
    priority_override_note = db.Column(db.Text)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    duplicate_of = db.relationship(
        "Complaint", remote_side=[id], foreign_keys=[duplicate_of_id]
    )
    status_history = db.relationship(
        "StatusHistory",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="StatusHistory.created_at.asc()",
        foreign_keys="StatusHistory.complaint_id",
    )
    activity = db.relationship(
        "ActivityLog",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ActivityLog.created_at.asc()",
    )

    @property
    def factors(self):
        try:
            return json.loads(self.priority_factors or "[]")
        except (ValueError, TypeError):
            return []

    @property
    def coordinates(self):
        return (self.latitude, self.longitude)

    def public_dict(self, include_history=True):
        """Safe representation for the public tracking page.

        Internal notes, activity logs and officer identifiers are excluded.
        """
        data = {
            "public_id": self.public_id,
            "title": self.title,
            "category": self.category,
            "summary": self.ai_summary,
            "priority_score": self.priority_score,
            "priority_level": self.priority_level,
            "priority_explanation": self.priority_explanation,
            "recommended_department": self.recommended_department,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "status": self.status,
            "assigned_department": self.assigned_department,
            "duplicate_of": self.duplicate_of.public_id if self.duplicate_of else None,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "has_image": bool(self.image_path),
            "image_path": self.image_path,
        }
        if include_history:
            data["history"] = [
                {
                    "status": h.new_status,
                    "at": _iso(h.created_at),
                    # A note is only included when an officer marked it public.
                    "note": h.note if h.is_public else None,
                }
                for h in self.status_history
            ]
        return data

    def officer_dict(self):
        data = self.public_dict(include_history=False)
        data.update(
            {
                "description": self.description,
                "ai_engine": self.ai_engine,
                "category_confidence": self.category_confidence,
                "factors": self.factors,
                "priority_overridden": self.priority_overridden,
                "original_priority_score": self.original_priority_score,
                "original_priority_level": self.original_priority_level,
                "priority_override_note": self.priority_override_note,
                "duplicate_of": self.duplicate_of.public_id if self.duplicate_of else None,
            }
        )
        return data


class StatusHistory(db.Model):
    __tablename__ = "status_history"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    previous_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30), nullable=False)
    note = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    complaint = db.relationship(
        "Complaint", back_populates="status_history", foreign_keys=[complaint_id]
    )


class ActivityLog(db.Model):
    """Internal audit trail (never exposed on the public tracking page)."""

    __tablename__ = "activity_log"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    event_type = db.Column(db.String(40), nullable=False)
    message = db.Column(db.Text, nullable=False)
    actor = db.Column(db.String(60), default="system")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    complaint = db.relationship("Complaint", back_populates="activity")


class DuplicateLink(db.Model):
    __tablename__ = "duplicate_links"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    duplicate_of_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    text_similarity = db.Column(db.Float, nullable=False)
    distance_km = db.Column(db.Float)
    combined_score = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="suggested", nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("complaint_id", "duplicate_of_id", name="uq_duplicate_pair"),
    )


def _iso(value):
    if not value:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
