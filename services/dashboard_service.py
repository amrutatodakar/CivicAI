"""Dashboard aggregates and complaint filtering for the officer console."""
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_

from extensions import db
from models import (
    CATEGORIES,
    Complaint,
    DuplicateLink,
    PRIORITY_LEVELS,
    STATUSES,
)
from services.action_brief_service import build_complaint_brief
from services.hotspot_service import detect_hotspots


def _active():
    return Complaint.status != "Resolved"


def build_dashboard():
    total = Complaint.query.count()
    active = Complaint.query.filter(_active()).count()
    pending = Complaint.query.filter(
        Complaint.status.in_(["Submitted", "Under Review"])
    ).count()
    in_progress = Complaint.query.filter(
        Complaint.status.in_(["Assigned", "In Progress"])
    ).count()
    resolved = Complaint.query.filter(Complaint.status == "Resolved").count()
    high = Complaint.query.filter(_active(), Complaint.priority_level == "High").count()
    critical = Complaint.query.filter(
        _active(), Complaint.priority_level == "Critical"
    ).count()
    avg_priority = (
        db.session.query(func.avg(Complaint.priority_score)).scalar() or 0
    )
    duplicate_suggestions = DuplicateLink.query.filter_by(status="suggested").count()
    confirmed_duplicates = Complaint.query.filter(
        Complaint.duplicate_of_id.isnot(None)
    ).count()

    category_rows = dict(
        db.session.query(Complaint.category, func.count(Complaint.id))
        .group_by(Complaint.category)
        .all()
    )
    priority_rows = dict(
        db.session.query(Complaint.priority_level, func.count(Complaint.id))
        .group_by(Complaint.priority_level)
        .all()
    )
    status_rows = dict(
        db.session.query(Complaint.status, func.count(Complaint.id))
        .group_by(Complaint.status)
        .all()
    )

    trends = []
    today = date.today()
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        next_day = day + timedelta(days=1)
        count = Complaint.query.filter(
            Complaint.created_at >= datetime.combine(day, datetime.min.time()),
            Complaint.created_at < datetime.combine(next_day, datetime.min.time()),
        ).count()
        trends.append({"date": day.isoformat(), "label": day.strftime("%d %b"), "count": count})

    recent = (
        Complaint.query.order_by(Complaint.created_at.desc()).limit(8).all()
    )
    critical_queue = (
        Complaint.query.filter(
            _active(), Complaint.priority_level.in_(["Critical", "High"])
        )
        .order_by(Complaint.priority_score.desc(), Complaint.created_at.desc())
        .limit(6)
        .all()
    )
    hotspot_data = detect_hotspots()

    map_points = [
        {
            "public_id": c.public_id,
            "title": c.title,
            "category": c.category,
            "priority_level": c.priority_level,
            "priority_score": c.priority_score,
            "status": c.status,
            "address": c.address,
            "lat": c.latitude,
            "lng": c.longitude,
            "related_count": len(c.status_history) - 1 if c.status_history else 0,
        }
        for c in Complaint.query.filter(
            Complaint.latitude.isnot(None), Complaint.longitude.isnot(None)
        )
        .order_by(Complaint.created_at.desc())
        .limit(500)
        .all()
    ]

    return {
        "stats": {
            "total": total,
            "active": active,
            "pending": pending,
            "in_progress": in_progress,
            "resolved": resolved,
            "high": high,
            "critical": critical,
            "avg_priority": round(float(avg_priority), 1),
            "duplicate_suggestions": duplicate_suggestions,
            "confirmed_duplicates": confirmed_duplicates,
            "hotspots": len(hotspot_data["clusters"]),
        },
        "category_distribution": [
            {"category": category, "count": category_rows.get(category, 0)}
            for category in CATEGORIES
        ],
        "priority_distribution": [
            {"level": level, "count": priority_rows.get(level, 0)}
            for level in PRIORITY_LEVELS
        ],
        "status_distribution": [
            {"status": status, "count": status_rows.get(status, 0)}
            for status in STATUSES
        ],
        "trends": trends,
        "recent": [c.officer_dict() for c in recent],
        "critical_queue": [c.officer_dict() for c in critical_queue],
        "map_points": map_points,
        "hotspot_data": hotspot_data,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }


def filtered_complaints(args):
    query = Complaint.query
    search = (args.get("q") or "").strip()
    category = (args.get("category") or "").strip()
    priority = (args.get("priority") or "").strip()
    status = (args.get("status") or "").strip()
    related = (args.get("related") or "").strip()
    sort = (args.get("sort") or "newest").strip()

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Complaint.public_id.ilike(pattern),
                Complaint.title.ilike(pattern),
                Complaint.description.ilike(pattern),
                Complaint.address.ilike(pattern),
                Complaint.ai_summary.ilike(pattern),
            )
        )
    if category in CATEGORIES:
        query = query.filter(Complaint.category == category)
    if priority in PRIORITY_LEVELS:
        query = query.filter(Complaint.priority_level == priority)
    if status in STATUSES:
        query = query.filter(Complaint.status == status)
    if related == "duplicates":
        query = query.filter(Complaint.duplicate_of_id.isnot(None))
    elif related == "unique":
        query = query.filter(Complaint.duplicate_of_id.is_(None))

    if sort == "priority":
        query = query.order_by(
            Complaint.priority_score.desc(), Complaint.created_at.desc()
        )
    elif sort == "oldest":
        query = query.order_by(Complaint.created_at.asc())
    else:
        query = query.order_by(Complaint.created_at.desc())

    rows = query.limit(200).all()
    return [c.officer_dict() for c in rows]
