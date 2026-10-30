"""Officer console: demo login, dashboard, complaint workflow."""
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from auth import officer_required, verify_officer
from extensions import db
from models import (
    ActivityLog,
    CATEGORIES,
    Complaint,
    DEPARTMENTS,
    DuplicateLink,
    PRIORITY_LEVELS,
    STATUSES,
)
from services.action_brief_service import build_complaint_brief
from services.complaint_service import (
    ValidationError,
    ensure_suggestions,
    override_priority,
    set_duplicate_status,
    update_workflow,
)
from services.dashboard_service import build_dashboard

officer_bp = Blueprint("officer", __name__, url_prefix="/officer")


def _safe_next(target):
    if not target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/"):
        return None
    return target


@officer_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("officer"):
        return redirect(url_for("officer.dashboard"))
    next_url = _safe_next(request.args.get("next") or request.form.get("next"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if verify_officer(username, password):
            session.clear()
            session["officer"] = True
            session["officer_name"] = username
            session.permanent = False
            flash("Signed in to the demo operations console.", "success")
            return redirect(next_url or url_for("officer.dashboard"))
        flash("Incorrect demo username or password.", "error")
    return render_template(
        "officer/login.html",
        next_url=next_url,
        demo_username=current_app.config["OFFICER_USERNAME"],
        demo_password=current_app.config["OFFICER_PASSWORD"],
    )


@officer_bp.post("/logout")
def logout():
    session.clear()
    flash("Signed out of the officer console.", "success")
    return redirect(url_for("citizen.index"))


@officer_bp.route("/")
@officer_required
def dashboard():
    data = build_dashboard()
    return render_template(
        "officer/dashboard.html",
        dashboard=data,
        categories=CATEGORIES,
        priorities=PRIORITY_LEVELS,
        statuses=STATUSES,
    )


@officer_bp.route("/complaints/<public_id>")
@officer_required
def complaint_detail(public_id):
    complaint = Complaint.query.filter_by(public_id=public_id.upper()).first()
    if complaint is None:
        abort(404)
    suggestions = ensure_suggestions(complaint)
    brief = build_complaint_brief(complaint, suggestions)
    activity = (
        ActivityLog.query.filter_by(complaint_id=complaint.id)
        .order_by(ActivityLog.created_at.desc())
        .all()
    )
    return render_template(
        "officer/complaint_detail.html",
        complaint=complaint,
        suggestions=suggestions,
        brief=brief,
        activity=activity,
        departments=DEPARTMENTS,
        statuses=STATUSES,
        priorities=PRIORITY_LEVELS,
    )


@officer_bp.post("/complaints/<public_id>/workflow")
@officer_required
def update_workflow_route(public_id):
    complaint = Complaint.query.filter_by(public_id=public_id.upper()).first()
    if complaint is None:
        abort(404)
    try:
        update_workflow(
            complaint,
            new_status=request.form.get("status"),
            department=request.form.get("department"),
            note=request.form.get("note"),
            is_public=request.form.get("is_public") == "on",
            actor=session.get("officer_name", "officer"),
        )
        flash(f"{complaint.public_id} updated. The citizen tracking page now reflects the change.", "success")
    except ValidationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("officer.complaint_detail", public_id=public_id) + "#workflow")


@officer_bp.post("/complaints/<public_id>/priority")
@officer_required
def review_priority_route(public_id):
    complaint = Complaint.query.filter_by(public_id=public_id.upper()).first()
    if complaint is None:
        abort(404)
    try:
        override_priority(
            complaint,
            score=request.form.get("priority_score"),
            level=request.form.get("priority_level"),
            note=request.form.get("note"),
            actor=session.get("officer_name", "officer"),
        )
        flash(f"Priority for {complaint.public_id} was reviewed and updated.", "success")
    except ValidationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("officer.complaint_detail", public_id=public_id) + "#priority")


@officer_bp.post("/complaints/<public_id>/duplicates/<int:link_id>/<action>")
@officer_required
def duplicate_action(public_id, link_id, action):
    complaint = Complaint.query.filter_by(public_id=public_id.upper()).first()
    if complaint is None:
        abort(404)
    link = db.session.get(DuplicateLink, link_id)
    if link is None or complaint.id not in (link.complaint_id, link.duplicate_of_id):
        abort(404)
    try:
        set_duplicate_status(link, action, actor=session.get("officer_name", "officer"))
        if action == "confirm":
            flash("Duplicate link confirmed. The original report and both histories are preserved.", "success")
        else:
            flash("Duplicate suggestion rejected. The reports remain separate.", "success")
    except ValidationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("officer.complaint_detail", public_id=public_id) + "#duplicates")
