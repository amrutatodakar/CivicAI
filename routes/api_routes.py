"""JSON API used by the dashboards and available for integration testing."""
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text

from auth import officer_required
from extensions import db
from models import Complaint
from services.action_brief_service import build_complaint_brief
from services.complaint_service import (
    ValidationError,
    create_complaint as create_complaint_record,
    ensure_suggestions,
    validate_submission,
)
from services.dashboard_service import build_dashboard, filtered_complaints
from services.hotspot_service import detect_hotspots
from services.llm_client import llm_status

api_bp = Blueprint("api", __name__, url_prefix="/api")

FORM_FIELDS = ("title", "description", "category", "address", "latitude", "longitude")


@api_bp.get("/health")
def health():
    database_ok = True
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    return jsonify(
        {
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "unavailable",
            "complaints": Complaint.query.count() if database_ok else None,
            "ai": llm_status(),
            "demo_auth": "single demo officer account",
        }
    )


@api_bp.post("/complaints")
def create_complaint_api():
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        form = {
            field: "" if payload.get(field) is None else str(payload.get(field))
            for field in FORM_FIELDS
        }
        files = {}
    else:
        form = request.form
        files = request.files

    data, errors = validate_submission(form, files)
    if errors:
        return jsonify({"error": "Validation failed.", "fields": errors}), 422

    try:
        complaint, duplicates = create_complaint_record(data)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("API complaint submission failed")
        return jsonify({"error": "The complaint could not be saved."}), 500

    duplicate_payload = [
        {
            "public_id": item["public_id"],
            "title": item["complaint"].title,
            "category": item["complaint"].category,
            "text_similarity": item["text_similarity"],
            "combined_score": item["combined_score"],
            "distance_km": item["distance_km"],
            "reasons": item["reasons"],
            "status": "suggested",
        }
        for item in duplicates
    ]
    return (
        jsonify(
            {
                "public_id": complaint.public_id,
                "status": complaint.status,
                "tracking_url": f"/track/{complaint.public_id}",
                "analysis": {
                    "category": complaint.category,
                    "category_confidence": complaint.category_confidence,
                    "summary": complaint.ai_summary,
                    "priority_score": complaint.priority_score,
                    "priority_level": complaint.priority_level,
                    "priority_explanation": complaint.priority_explanation,
                    "recommended_department": complaint.recommended_department,
                    "ai_engine": complaint.ai_engine,
                    "factors": complaint.factors,
                },
                "possible_duplicates": duplicate_payload,
            }
        ),
        201,
    )


@api_bp.get("/complaints/<public_id>")
def get_complaint(public_id):
    complaint = Complaint.query.filter_by(public_id=public_id.upper()).first()
    if complaint is None:
        return jsonify({"error": "Complaint not found."}), 404
    data = complaint.public_dict(include_history=True)
    data["duplicate_of"] = complaint.duplicate_of.public_id if complaint.duplicate_of else None
    return jsonify(data)


@api_bp.get("/officer/dashboard")
@officer_required
def officer_dashboard():
    return jsonify(build_dashboard())


@api_bp.get("/officer/complaints")
@officer_required
def officer_complaints():
    rows = filtered_complaints(request.args)
    return jsonify({"count": len(rows), "complaints": rows})


@api_bp.get("/officer/hotspots")
@officer_required
def officer_hotspots():
    return jsonify(detect_hotspots())


@api_bp.get("/officer/complaints/<public_id>/brief")
@officer_required
def officer_brief(public_id):
    complaint = Complaint.query.filter_by(public_id=public_id.upper()).first()
    if complaint is None:
        return jsonify({"error": "Complaint not found."}), 404
    related = ensure_suggestions(complaint)
    return jsonify(build_complaint_brief(complaint, related))
