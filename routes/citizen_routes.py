"""Citizen-facing pages: home, report, tracking and saved reports."""
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from extensions import db
from models import CATEGORIES, Complaint, DuplicateLink
from services.complaint_service import (
    complaint_counts_by_category,
    create_complaint,
    validate_submission,
)
from services.duplicate_service import find_duplicates
from services.hotspot_service import detect_hotspots

citizen_bp = Blueprint("citizen", __name__)


@citizen_bp.route("/")
def index():
    total = Complaint.query.count()
    resolved = Complaint.query.filter_by(status="Resolved").count()
    active = Complaint.query.filter(Complaint.status != "Resolved").count()
    category_counts = complaint_counts_by_category()
    high_open = Complaint.query.filter(
        Complaint.status != "Resolved",
        Complaint.priority_level.in_(["High", "Critical"]),
    ).count()
    hotspots = detect_hotspots()["clusters"][:3]
    resolved_rate = round((resolved / total) * 100) if total else 0
    return render_template(
        "index.html",
        total=total,
        resolved=resolved,
        active=active,
        high_open=high_open,
        resolved_rate=resolved_rate,
        category_counts=category_counts,
        hotspots=hotspots,
        demo_records=total,
    )


@citizen_bp.route("/report", methods=["GET", "POST"])
def report():
    form = {}
    errors = {}
    if request.method == "POST":
        data, errors = validate_submission(request.form, request.files)
        form = request.form
        if errors:
            for message in errors.values():
                flash(message, "error")
            return (
                render_template(
                    "citizen_report.html", form=form, errors=errors, categories=CATEGORIES
                ),
                400,
            )
        try:
            complaint, duplicates = create_complaint(data)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Complaint submission failed")
            flash(
                "We could not save the complaint because of a server error. Please try again.",
                "error",
            )
            return (
                render_template(
                    "citizen_report.html", form=form, errors={}, categories=CATEGORIES
                ),
                500,
            )
        message = f"Complaint {complaint.public_id} submitted and analysed."
        if duplicates:
            message += f" {len(duplicates)} possible related report(s) were found."
        flash(message, "success")
        return redirect(
            url_for("citizen.track_complaint", public_id=complaint.public_id) + "?new=1"
        )

    return render_template(
        "citizen_report.html", form=form, errors=errors, categories=CATEGORIES
    )


@citizen_bp.route("/track")
def track():
    public_id = (request.args.get("complaint_id") or "").strip().upper()
    if public_id:
        complaint = Complaint.query.filter_by(public_id=public_id).first()
        if complaint:
            return redirect(url_for("citizen.track_complaint", public_id=public_id))
        flash(f"No complaint found with ID {public_id}.", "error")
    return render_template("citizen_tracking.html", complaint=None, public_id=public_id)


@citizen_bp.route("/track/<public_id>")
def track_complaint(public_id):
    complaint = Complaint.query.filter_by(public_id=public_id.upper()).first()
    if complaint is None:
        abort(404)

    related = []
    if complaint.duplicate_of_id is None:
        candidates = Complaint.query.filter(
            Complaint.id != complaint.id, Complaint.duplicate_of_id.is_(None)
        ).all()
        related = find_duplicates(complaint, candidates, config=None)[:3]
        for item in related:
            persisted = DuplicateLink.query.filter(
                (
                    (DuplicateLink.complaint_id == complaint.id)
                    & (DuplicateLink.duplicate_of_id == item["complaint"].id)
                )
                | (
                    (DuplicateLink.duplicate_of_id == complaint.id)
                    & (DuplicateLink.complaint_id == item["complaint"].id)
                )
            ).first()
            item["link_status"] = persisted.status if persisted else "suggested"

    return render_template(
        "citizen_complaint.html",
        complaint=complaint,
        related=related,
        is_new=request.args.get("new") == "1",
    )


@citizen_bp.route("/my-reports")
def my_reports():
    return render_template("citizen_dashboard.html")
