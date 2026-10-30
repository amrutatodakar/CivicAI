"""Complaint persistence, validation and workflow operations."""
import json
import os
import uuid
from datetime import datetime
from types import SimpleNamespace

from flask import current_app
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename

from extensions import db
from models import (
    ActivityLog,
    AppSetting,
    CATEGORIES,
    Complaint,
    DEPARTMENTS,
    DuplicateLink,
    PRIORITY_LEVELS,
    STATUSES,
    StatusHistory,
    utcnow,
)
from services.ai_service import analyze_complaint
from services.duplicate_service import (
    find_duplicates,
    suggestion_status_map,
    update_suggested_links,
)
from services.nlp import classify_category
from services.priority_service import priority_level_for


class ValidationError(ValueError):
    pass


def _next_public_id():
    counter = db.session.get(AppSetting, "complaint_counter")
    if counter is None:
        max_number = 0
        for (public_id,) in db.session.query(Complaint.public_id).all():
            try:
                max_number = max(max_number, int(public_id.split("-")[1]))
            except (IndexError, ValueError):
                continue
        counter = AppSetting(key="complaint_counter", value=str(max_number))
        db.session.add(counter)
        db.session.flush()
    number = int(counter.value) + 1
    counter.value = str(number)
    db.session.flush()
    return f"CIV-{number:04d}"


def _signature_ok(extension, header):
    if extension == "png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {"jpg", "jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == "gif":
        return header.startswith(b"GIF87a") or header.startswith(b"GIF89a")
    if extension == "webp":
        return header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return False


def validate_image_upload(file_storage):
    if file_storage is None or not getattr(file_storage, "filename", ""):
        return None
    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        return "Unsupported image format. Please upload PNG, JPG, WEBP or GIF."
    stream = file_storage.stream
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)
        header = stream.read(16)
        stream.seek(0)
    except (OSError, ValueError):
        return "The uploaded image could not be read. Please try another file."
    if size <= 0:
        return "The uploaded image is empty."
    if size > current_app.config["MAX_IMAGE_BYTES"]:
        return "Image is too large. Maximum size is 5 MB."
    if not _signature_ok(extension, header):
        return "The file does not appear to be a valid image of the selected type."
    return None


def validate_submission(form, files):
    errors = {}
    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip()
    category = (form.get("category") or "").strip()
    address = (form.get("address") or "").strip()
    latitude_raw = (form.get("latitude") or "").strip()
    longitude_raw = (form.get("longitude") or "").strip()

    if len(title) < 5:
        errors["title"] = "Title must be at least 5 characters."
    elif len(title) > 120:
        errors["title"] = "Title must be 120 characters or fewer."
    if len(description) < 20:
        errors["description"] = "Description must be at least 20 characters."
    elif len(description) > 3000:
        errors["description"] = "Description must be 3,000 characters or fewer."
    if category and category not in CATEGORIES:
        errors["category"] = "Choose a valid category."
    if len(address) < 4:
        errors["address"] = "Add a location description (at least 4 characters)."
    elif len(address) > 250:
        errors["address"] = "Location description must be 250 characters or fewer."

    latitude = longitude = None
    if latitude_raw or longitude_raw:
        if not (latitude_raw and longitude_raw):
            errors["coordinates"] = "Provide both latitude and longitude, or leave both blank."
        else:
            try:
                latitude = float(latitude_raw)
                longitude = float(longitude_raw)
                if not (-90 <= latitude <= 90):
                    errors["coordinates"] = "Latitude must be between -90 and 90."
                elif not (-180 <= longitude <= 180):
                    errors["coordinates"] = "Longitude must be between -180 and 180."
                elif latitude == 0 and longitude == 0:
                    errors["coordinates"] = "Coordinates 0,0 are not a valid civic location."
            except ValueError:
                errors["coordinates"] = "Latitude and longitude must be numbers."

    image = files.get("image") if files else None
    image_error = validate_image_upload(image)
    if image_error:
        errors["image"] = image_error

    return {
        "title": title,
        "description": description,
        "category": category or None,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "image": image if image and image.filename else None,
    }, errors


def save_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit(".", 1)[-1].lower()
    unique_name = f"{uuid.uuid4().hex}.{extension}"
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, unique_name)
    file_storage.stream.seek(0)
    file_storage.save(path)
    return f"uploads/{unique_name}"


def create_complaint(data, actor="citizen"):
    title = data["title"]
    description = data["description"]
    address = data["address"]
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    image_file = data.get("image")

    # Estimate the category once before duplicate detection so that the
    # category-mismatch guard has a meaningful input.
    provisional_category = classify_category(title, description)[0]
    provisional = SimpleNamespace(
        public_id="_new_",
        title=title,
        description=description,
        latitude=latitude,
        longitude=longitude,
        category=provisional_category,
        duplicate_of_id=None,
    )
    candidates = (
        Complaint.query.filter(Complaint.duplicate_of_id.is_(None))
        .order_by(Complaint.created_at.desc())
        .all()
    )
    duplicates = find_duplicates(provisional, candidates, current_app.config)

    analysis = analyze_complaint(
        title=title,
        description=description,
        selected_category=data.get("category"),
        duplicate_count=len(duplicates),
        has_image=bool(image_file),
        has_location=latitude is not None and longitude is not None,
    )

    image_path = None
    try:
        image_path = save_image(image_file)
        complaint = Complaint(
            public_id=_next_public_id(),
            title=title,
            description=description,
            ai_summary=analysis["summary"],
            category=analysis["category"],
            category_confidence=analysis["category_confidence"],
            priority_score=analysis["priority_score"],
            priority_level=analysis["priority_level"],
            priority_explanation=analysis["priority_explanation"],
            priority_factors=json.dumps(analysis["priority_factors"]),
            recommended_department=analysis["recommended_department"],
            ai_engine=analysis["ai_engine"],
            ai_notes=analysis["ai_notes"],
            image_path=image_path,
            latitude=latitude,
            longitude=longitude,
            address=address,
            status="Submitted",
        )
        db.session.add(complaint)
        db.session.flush()

        db.session.add(
            StatusHistory(
                complaint_id=complaint.id,
                previous_status=None,
                new_status="Submitted",
                note="Complaint received and automatically analysed.",
                is_public=True,
            )
        )
        db.session.add(
            ActivityLog(
                complaint_id=complaint.id,
                event_type="submitted",
                message=(
                    f"Complaint submitted. {analysis['ai_engine']}; "
                    f"{analysis['priority_level']} priority ({analysis['priority_score']}/100)."
                ),
                actor=actor,
            )
        )
        update_suggested_links(complaint, duplicates)
        db.session.commit()
        return complaint, duplicates
    except Exception:
        db.session.rollback()
        if image_path:
            full_path = os.path.join(current_app.static_folder, image_path)
            try:
                os.remove(full_path)
            except OSError:
                pass
        raise


def update_workflow(complaint, new_status, department="", note="", is_public=False, actor="officer"):
    new_status = (new_status or "").strip()
    department = (department or "").strip()
    note = (note or "").strip()
    if new_status not in STATUSES:
        raise ValidationError("Choose a valid complaint status.")
    if department and department not in DEPARTMENTS:
        raise ValidationError("Choose a valid department.")
    if len(note) > 800:
        raise ValidationError("Action note must be 800 characters or fewer.")
    if new_status == complaint.status and department in ("", complaint.assigned_department) and not note:
        raise ValidationError("No change was selected. Choose a new status, department or note.")

    changed = []
    previous_status = complaint.status
    if new_status != complaint.status:
        complaint.status = new_status
        changed.append(f"status {previous_status} → {new_status}")
        db.session.add(
            StatusHistory(
                complaint_id=complaint.id,
                previous_status=previous_status,
                new_status=new_status,
                note=note or None,
                is_public=bool(is_public),
            )
        )
    elif note:
        # A note can be added without changing the status. It remains internal
        # unless explicitly marked public by the officer.
        db.session.add(
            StatusHistory(
                complaint_id=complaint.id,
                previous_status=new_status,
                new_status=new_status,
                note=note,
                is_public=bool(is_public),
            )
        )

    if department and department != complaint.assigned_department:
        complaint.assigned_department = department
        changed.append(f"assigned to {department}")

    if not changed and note:
        changed.append("action note added")
    complaint.updated_at = utcnow()
    db.session.add(
        ActivityLog(
            complaint_id=complaint.id,
            event_type="workflow_update",
            message="; ".join(changed).capitalize() + (f". Note: {note}" if note else ""),
            actor=actor,
        )
    )
    db.session.commit()
    return complaint


def override_priority(complaint, score, level, note, actor="officer"):
    try:
        score = int(score)
    except (TypeError, ValueError):
        raise ValidationError("Priority score must be a number between 0 and 100.")
    if not 0 <= score <= 100:
        raise ValidationError("Priority score must be between 0 and 100.")
    if level not in PRIORITY_LEVELS:
        raise ValidationError("Choose a valid priority level.")
    note = (note or "").strip()
    if len(note) < 5:
        raise ValidationError("Add a short note explaining the priority review.")
    if len(note) > 500:
        raise ValidationError("Priority review note must be 500 characters or fewer.")

    if not complaint.priority_overridden:
        complaint.original_priority_score = complaint.priority_score
        complaint.original_priority_level = complaint.priority_level
    complaint.priority_score = score
    complaint.priority_level = level
    complaint.priority_overridden = True
    complaint.priority_override_note = note
    complaint.updated_at = utcnow()
    db.session.add(
        ActivityLog(
            complaint_id=complaint.id,
            event_type="priority_review",
            message=(
                f"Officer changed priority from {complaint.original_priority_level} "
                f"({complaint.original_priority_score}/100) to {level} ({score}/100). "
                f"Reason: {note}"
            ),
            actor=actor,
        )
    )
    db.session.commit()
    return complaint


def set_duplicate_status(link, action, actor="officer"):
    if link is None:
        raise ValidationError("Duplicate suggestion not found.")
    if action not in {"confirm", "reject"}:
        raise ValidationError("Unknown duplicate action.")
    newer = db.session.get(Complaint, link.complaint_id)
    older = db.session.get(Complaint, link.duplicate_of_id)
    if not newer or not older:
        raise ValidationError("A linked complaint no longer exists.")

    if action == "confirm":
        link.status = "confirmed"
        newer.duplicate_of_id = older.id
        message = f"Confirmed {newer.public_id} as a duplicate of {older.public_id}."
        db.session.add(
            ActivityLog(
                complaint_id=newer.id,
                event_type="duplicate_confirmed",
                message=message + " Original report and history preserved.",
                actor=actor,
            )
        )
        db.session.add(
            ActivityLog(
                complaint_id=older.id,
                event_type="duplicate_linked",
                message=f"{newer.public_id} was linked as a duplicate. This report remains the original.",
                actor=actor,
            )
        )
    else:
        link.status = "rejected"
        if newer.duplicate_of_id == older.id:
            newer.duplicate_of_id = None
        message = f"Rejected duplicate suggestion between {newer.public_id} and {older.public_id}."
        db.session.add(
            ActivityLog(
                complaint_id=newer.id,
                event_type="duplicate_rejected",
                message=message,
                actor=actor,
            )
        )
    newer.updated_at = utcnow()
    db.session.commit()
    return link


def _link_map(complaint_id):
    links = DuplicateLink.query.filter(
        (DuplicateLink.complaint_id == complaint_id)
        | (DuplicateLink.duplicate_of_id == complaint_id)
    ).all()
    result = {}
    for link in links:
        other_id = (
            link.duplicate_of_id if link.complaint_id == complaint_id else link.complaint_id
        )
        result[other_id] = link
    return result


def ensure_suggestions(complaint):
    """Return live duplicate suggestions enriched with persisted link state."""
    candidates = (
        Complaint.query.filter(
            Complaint.id != complaint.id,
            Complaint.duplicate_of_id.is_(None),
        ).all()
    )
    results = find_duplicates(complaint, candidates, current_app.config)
    if results:
        update_suggested_links(complaint, results)
        db.session.commit()

    links = _link_map(complaint.id)
    decorated = []
    for result in results:
        other = result["complaint"]
        link = links.get(other.id)
        decorated.append(
            {
                **result,
                "link_id": link.id if link else None,
                "status": link.status if link else "suggested",
                "related": {
                    "public_id": other.public_id,
                    "title": other.title,
                    "category": other.category,
                    "status": other.status,
                    "priority_level": other.priority_level,
                    "priority_score": other.priority_score,
                    "created_at": other.created_at.isoformat() if other.created_at else None,
                },
            }
        )
    return decorated


def complaint_counts_by_category():
    rows = (
        db.session.query(Complaint.category, func.count(Complaint.id))
        .group_by(Complaint.category)
        .all()
    )
    counts = {category: 0 for category in CATEGORIES}
    counts.update({category: count for category, count in rows})
    return counts
