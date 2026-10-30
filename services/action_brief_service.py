"""Generate evidence-based action briefs from stored complaint data."""
from services.duplicate_service import haversine_km

CATEGORY_STEPS = {
    "Road Damage": [
        "Barricade or cone off any immediate hazard until a repair crew arrives.",
        "Measure and photograph the damaged section; check for water damage beneath the surface.",
    ],
    "Waterlogging": [
        "Inspect and clear the nearest stormwater drains and culverts.",
        "Check whether standing water is entering homes or blocking emergency access.",
    ],
    "Garbage and Waste": [
        "Arrange a collection or bin-capacity review at the reported location.",
        "Inspect for illegal dumping and schedule cleanup if waste is overflowing.",
    ],
    "Drainage": [
        "Inspect the drain line for blockages, collapse or illegal connections.",
        "Check upstream and downstream flow before clearing the affected section.",
    ],
    "Streetlight": [
        "Check the feeder line, fuse and lamp inventory for the reported pole.",
        "Record the pole number and restore lighting at night where feasible.",
    ],
    "Public Safety": [
        "Secure or cordon the immediate hazard before non-urgent paperwork.",
        "Request a joint inspection if the hazard spans multiple departments.",
    ],
    "Other": [
        "Verify the reported location and route the issue to the appropriate team.",
    ],
}


def build_complaint_brief(complaint, related=None):
    related = related or []
    location = complaint.address or (
        f"{complaint.latitude:.5f}, {complaint.longitude:.5f}"
        if complaint.latitude is not None
        else "Location not provided"
    )
    why = (
        f"Assessed as {complaint.priority_level} priority ({complaint.priority_score}/100). "
        f"{complaint.priority_explanation}"
    )
    if complaint.priority_overridden:
        why += (
            f" An officer reviewed the score and recorded: "
            f"{complaint.priority_override_note or 'no note provided'}."
        )
    if related:
        why += f" {len(related)} similar nearby report(s) may describe the same issue; this is a suggestion, not a confirmed merge."

    evidence = [
        f"Report {complaint.public_id} submitted on {complaint.created_at.strftime('%d %b %Y')}.",
        f"Category: {complaint.category}; status: {complaint.status}.",
        f"AI engine: {complaint.ai_engine}.",
    ]
    if complaint.image_path:
        evidence.append("A citizen-supplied photo is attached as supporting evidence (not automatically analysed).")
    if related:
        evidence.append(
            "Related IDs: " + ", ".join(item["public_id"] for item in related[:6])
        )
    if complaint.latitude is not None:
        evidence.append(
            f"Coordinates: {complaint.latitude:.5f}, {complaint.longitude:.5f}."
        )

    steps = CATEGORY_STEPS.get(complaint.category, CATEGORY_STEPS["Other"]).copy()
    steps.append(
        f"Update the complaint status and add a short action note so the citizen can track progress."
    )
    if complaint.recommended_department:
        steps.insert(
            0,
            f"Responsible team suggested by the classifier: {complaint.recommended_department}.",
        )

    return {
        "title": f"Action brief — {complaint.public_id}",
        "what": f"{complaint.title}. {complaint.ai_summary}",
        "where": location,
        "why": why,
        "next_steps": steps,
        "evidence": evidence,
        "caveat": (
            "This brief is generated from the complaint text and stored context. "
            "Any underlying cause is a hypothesis that requires site verification."
        ),
    }


def build_hotspot_brief(hotspot, complaints=None):
    """Brief for a hotspot dict (already includes one); enrich with distance."""
    summary = hotspot.get("brief", {})
    if complaints:
        valid = [
            c for c in complaints if c.latitude is not None and c.longitude is not None
        ]
        distances = [
            haversine_km(
                hotspot["centroid"]["lat"],
                hotspot["centroid"]["lng"],
                c.latitude,
                c.longitude,
            )
            for c in valid
        ]
        if distances:
            summary.setdefault("evidence", []).append(
                f"Farthest linked report is about {max(distances):.2f} km from the cluster centre."
            )
    return summary
