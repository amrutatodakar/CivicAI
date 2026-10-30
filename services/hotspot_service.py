"""Geographic hotspot detection.

A greedy distance-based clustering (haversine distance, configurable radius)
groups complaints, with a minimum cluster size so the UI never invents a
hotspot from one or two isolated reports. Resolved reports are retained as
historical evidence but reported separately from open issues.
"""
import hashlib
from collections import Counter

from flask import current_app

from models import Complaint
from services.duplicate_service import haversine_km


def _short_place(address, fallback):
    if not address:
        return fallback
    first = address.split(",")[0].strip()
    for prefix in ("near ", "opposite ", "beside ", "behind "):
        if first.lower().startswith(prefix):
            first = first[len(prefix):].strip()
    return first[:60] if first else fallback


def _hotspot_id(centroid_lat, centroid_lng):
    raw = f"{centroid_lat:.3f},{centroid_lng:.3f}".encode("utf-8")
    return "HS-" + hashlib.sha1(raw).hexdigest()[:6].upper()


def _inspection_hint(categories):
    names = set(categories)
    if {"Waterlogging", "Drainage"} & names and "Road Damage" in names:
        return (
            "Inspect stormwater drains, culverts and low-lying road segments together; "
            "recurring water and pavement damage may share an underlying drainage cause."
        )
    if {"Waterlogging", "Drainage"} & names:
        return "Inspect nearby drains and culverts for blockages before the next heavy rain."
    if "Garbage and Waste" in names:
        return "Review collection frequency, bin capacity and illegal dumping at this location."
    if "Streetlight" in names:
        return "Check the feeder line, lamp inventory and reported dark stretches at night."
    if "Road Damage" in names:
        return "Assess pavement condition and schedule temporary barricading where safety is at risk."
    if "Public Safety" in names:
        return "Conduct a joint safety inspection and address immediate hazards first."
    return "Conduct a site inspection and verify the reported locations."


def _build_insight(name, total, radius_m, category_counts, high_count, open_count):
    category_text = ", ".join(
        f"{category} ({count})" for category, count in category_counts.most_common(4)
    )
    parts = [
        f"{total} reports are clustered within about {radius_m} m around {name}.",
        f"Categories represented: {category_text}.",
        f"{high_count} are high or critical priority and {open_count} remain open.",
    ]
    names = {category for category, _ in category_counts.most_common(3)}
    if "Waterlogging" in names and "Drainage" in names:
        parts.append(
            "The co-occurrence of waterlogging and drainage reports may point to a shared "
            "drainage problem, but the cause is not proven and needs site verification."
        )
    elif "Garbage and Waste" in names and len(names) > 1:
        parts.append(
            "Repeated waste reports alongside other issues may indicate a location-specific "
            "service gap; verify collection coverage before concluding a cause."
        )
    elif total >= 5:
        parts.append(
            "The repetition suggests this location deserves a coordinated inspection rather "
            "than separate one-off fixes; an underlying cause is not yet established."
        )
    return " ".join(parts)


def detect_hotspots(config=None, complaints=None):
    config = config or (current_app.config if current_app else {})
    radius_km = config.get("HOTSPOT_RADIUS_KM", 0.7)
    min_reports = config.get("HOTSPOT_MIN_REPORTS", 3)

    if complaints is None:
        complaints = (
            Complaint.query.filter(
                Complaint.latitude.isnot(None),
                Complaint.longitude.isnot(None),
                Complaint.duplicate_of_id.is_(None),
            )
            .all()
        )
    points = [
        c
        for c in complaints
        if c.latitude is not None
        and c.longitude is not None
        and -90 <= c.latitude <= 90
        and -180 <= c.longitude <= 180
    ]

    if len(points) < min_reports:
        return {
            "clusters": [],
            "message": (
                f"Not enough geolocated reports to identify a hotspot. "
                f"At least {min_reports} nearby reports are required."
            ),
            "radius_km": radius_km,
            "min_reports": min_reports,
        }

    remaining = list(points)
    raw_clusters = []
    while len(remaining) >= min_reports:
        # Choose the seed with the most neighbours among unassigned reports.
        best_seed = None
        best_neighbors = []
        for point in remaining:
            neighbors = [
                other
                for other in remaining
                if other.id != point.id
                and haversine_km(
                    point.latitude, point.longitude, other.latitude, other.longitude
                )
                <= radius_km
            ]
            if len(neighbors) > len(best_neighbors):
                best_seed = point
                best_neighbors = neighbors
        if best_seed is None or len(best_neighbors) + 1 < min_reports:
            break
        group = [best_seed] + best_neighbors
        raw_clusters.append(group)
        used = {item.id for item in group}
        remaining = [item for item in remaining if item.id not in used]

    hotspots = []
    for group in raw_clusters:
        centroid_lat = sum(c.latitude for c in group) / len(group)
        centroid_lng = sum(c.longitude for c in group) / len(group)
        radius_m = max(
            haversine_km(centroid_lat, centroid_lng, c.latitude, c.longitude) for c in group
        ) * 1000
        categories = Counter(c.category for c in group)
        priorities = Counter(c.priority_level for c in group)
        open_count = sum(1 for c in group if c.status != "Resolved")
        high_count = sum(
            1 for c in group if c.priority_level in ("High", "Critical") and c.status != "Resolved"
        )
        avg_score = round(sum(c.priority_score for c in group) / len(group))
        concern_score = min(
            100,
            round(avg_score * 0.65 + min(18, len(group) * 1.5) + min(17, high_count * 3)),
        )
        if priorities.get("Critical") or concern_score >= 80:
            concern = "Critical concern"
        elif concern_score >= 60:
            concern = "High concern"
        else:
            concern = "Watch"

        place_counter = Counter(
            _short_place(c.address, f"Area near {c.public_id}") for c in group
        )
        name = place_counter.most_common(1)[0][0]
        sorted_members = sorted(
            group,
            key=lambda c: (c.priority_level == "Critical", c.priority_score, c.created_at),
            reverse=True,
        )
        hint = _inspection_hint(categories.keys())
        insight = _build_insight(
            name, len(group), round(radius_m), categories, high_count, open_count
        )
        hotspot = {
            "id": _hotspot_id(centroid_lat, centroid_lng),
            "name": name,
            "centroid": {"lat": round(centroid_lat, 6), "lng": round(centroid_lng, 6)},
            "radius_m": round(radius_m),
            "total": len(group),
            "open": open_count,
            "high_or_critical": high_count,
            "avg_priority": avg_score,
            "concern": concern,
            "concern_score": concern_score,
            "category_counts": [
                {"category": category, "count": count}
                for category, count in categories.most_common()
            ],
            "priority_counts": dict(priorities),
            "insight": insight,
            "inspection_hint": hint,
            "complaint_ids": [c.public_id for c in sorted_members],
            "addresses": list({c.address for c in group if c.address})[:5],
            "brief": {
                "what": (
                    f"Cluster of {len(group)} reports around {name}, dominated by "
                    + ", ".join(category for category, _ in categories.most_common(3))
                    + "."
                ),
                "where": f"{name} (approximately {centroid_lat:.4f}, {centroid_lng:.4f}), "
                f"within about {round(radius_m)} m.",
                "why": (
                    f"{open_count} reports are still open and {high_count} are high or critical. "
                    "The repetition suggests a shared location problem, but the underlying "
                    "cause is not proven."
                ),
                "next_steps": [
                    hint,
                    "Verify the reported locations and inspect the highest-priority report first.",
                    "Record findings against the linked complaint IDs and update their status.",
                ],
                "evidence": [
                    f"{len(group)} geolocated report(s) within {radius_km * 1000:.0f} m",
                    "Linked report IDs: " + ", ".join(c.public_id for c in sorted_members[:8]),
                ],
                "caveat": (
                    "Hotspot clusters are calculated from submitted coordinates. "
                    "They indicate concentration, not a confirmed root cause."
                ),
            },
        }
        hotspots.append(hotspot)

    hotspots.sort(key=lambda h: (h["concern_score"], h["total"]), reverse=True)
    message = (
        f"{len(hotspots)} hotspot(s) detected from {len(points)} geolocated reports."
        if hotspots
        else "No area currently meets the minimum report density for a hotspot."
    )
    return {
        "clusters": hotspots,
        "message": message,
        "radius_km": radius_km,
        "min_reports": min_reports,
    }
