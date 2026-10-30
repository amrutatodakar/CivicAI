"""Explainable, rule-based priority scoring.

The score is a transparent sum of evidence found in the complaint plus context
signals (nearby related reports, a supporting photo, a known location). It is
decision support only — never a claim about real-world danger.
"""
import re

from services.nlp import normalize_text

CATEGORY_BASE = {
    "Road Damage": 28,
    "Waterlogging": 30,
    "Garbage and Waste": 18,
    "Drainage": 24,
    "Streetlight": 20,
    "Public Safety": 38,
    "Other": 15,
}

SEVERE_TERMS = {
    "injury": "possible injury mentioned",
    "injured": "possible injury mentioned",
    "accident": "accident risk mentioned",
    "electrocution": "electrocution risk mentioned",
    "live wire": "live electrical wire mentioned",
    "exposed wire": "exposed wiring mentioned",
    "collapse": "structural collapse mentioned",
    "collapsed": "structural collapse mentioned",
    "fire": "fire risk mentioned",
    "drowning": "drowning risk mentioned",
    "open manhole": "open manhole hazard mentioned",
    "child": "children may be exposed",
    "children": "children may be exposed",
    "school": "school area mentioned",
    "hospital": "hospital area mentioned",
    "ambulance": "ambulance access mentioned",
}

MODERATE_TERMS = {
    "danger": "danger described",
    "dangerous": "danger described",
    "hazard": "hazard described",
    "unsafe": "unsafe condition described",
    "deep": "severity described as deep/large",
    "huge": "severity described as deep/large",
    "large": "severity described as deep/large",
    "blocked": "blockage described",
    "overflow": "overflow described",
    "overflowing": "overflow described",
    "stagnant": "stagnant water mentioned",
    "exposed": "exposed infrastructure mentioned",
    "swerv": "vehicles swerving mentioned",
    "skid": "skidding risk mentioned",
    "fell": "someone fell mentioned",
    "fallen": "someone fell mentioned",
}

IMPACT_TERMS = {
    "school": "school nearby",
    "college": "college nearby",
    "hospital": "hospital nearby",
    "market": "market area",
    "bus stop": "public transport stop",
    "main road": "main road",
    "station": "station area",
    "temple": "temple area",
    "residents": "residents affected",
    "commuters": "commuters affected",
    "pedestrian": "pedestrians affected",
    "pedestrians": "pedestrians affected",
    "traffic": "traffic affected",
    "vehicles": "vehicles affected",
    "shops": "shops affected",
    "patients": "patients affected",
    "passengers": "passengers affected",
    "students": "students affected",
    "children": "children affected",
    "families": "families affected",
}

URGENCY_PATTERNS = [
    (r"\b(immediately|right away|asap)\b", 4, "immediate action requested"),
    (r"\b(urgent|emergency)\b", 3, "urgency stated by reporter"),
    (r"\b(since|for)\s+(two|three|four|five|\d+)\s+(days?|weeks?)\b", 5, "problem reported as long-standing"),
    (r"\b(since yesterday|since morning|last week)\b", 4, "problem reported as long-standing"),
    (r"\b(knee[- ]deep|waist[- ]deep)\b", 5, "water depth indicates severity"),
]

SCALE_TERMS = {
    "entire": "affects a wide area",
    "whole": "affects a wide area",
    "multiple": "multiple people or assets affected",
    "several": "multiple people or assets affected",
    "many": "multiple people or assets affected",
    "throughout": "affects a wide area",
}

LOW_SEVERITY_TERMS = {
    "minor": "reporter describes issue as minor",
    "small": "reporter describes issue as small",
    "cosmetic": "reporter describes issue as cosmetic",
    "not urgent": "reporter says it is not urgent",
}


def priority_level_for(score, config):
    if score >= config.get("PRIORITY_CRITICAL_MIN", 80):
        return "Critical"
    if score >= config.get("PRIORITY_HIGH_MIN", 60):
        return "High"
    if score >= config.get("PRIORITY_MEDIUM_MIN", 35):
        return "Medium"
    return "Low"


def score_priority(
    title,
    description,
    category,
    duplicate_count=0,
    has_image=False,
    has_location=False,
    config=None,
):
    """Return score, level, human explanation and itemised factors."""
    config = config or {}
    text = normalize_text(f"{title} {description}")
    factors = []
    base = CATEGORY_BASE.get(category, 15)
    factors.append(
        {
            "label": "Category baseline",
            "detail": f"{category} reports start at {base} points",
            "points": base,
        }
    )

    # Safety evidence. Severe terms are capped so repeating a word cannot
    # by itself push a report to critical.
    severe_hits = []
    for term, detail in SEVERE_TERMS.items():
        if re.search(r"\b" + re.escape(term), text):
            severe_hits.append(detail)
    severe_points = min(36, len(set(severe_hits)) * 12)
    if severe_points:
        factors.append(
            {
                "label": "Safety risk",
                "detail": "; ".join(sorted(set(severe_hits))[:4]),
                "points": severe_points,
            }
        )

    moderate_hits = []
    for term, detail in MODERATE_TERMS.items():
        if re.search(r"\b" + re.escape(term), text):
            moderate_hits.append(detail)
    moderate_points = min(16, len(set(moderate_hits)) * 4)
    if moderate_points:
        factors.append(
            {
                "label": "Severity / hazard wording",
                "detail": "; ".join(sorted(set(moderate_hits))[:4]),
                "points": moderate_points,
            }
        )

    impact_hits = []
    for term, detail in IMPACT_TERMS.items():
        if re.search(r"\b" + re.escape(term), text):
            impact_hits.append(detail)
    impact_points = min(16, len(set(impact_hits)) * 4)
    if impact_points:
        factors.append(
            {
                "label": "Public impact",
                "detail": "; ".join(sorted(set(impact_hits))[:4]),
                "points": impact_points,
            }
        )

    urgency_points = 0
    urgency_details = []
    for pattern, points, detail in URGENCY_PATTERNS:
        if re.search(pattern, text):
            urgency_points += points
            urgency_details.append(detail)
    urgency_points = min(9, urgency_points)
    if urgency_points:
        factors.append(
            {
                "label": "Urgency signals",
                "detail": "; ".join(urgency_details),
                "points": urgency_points,
            }
        )

    scale_hits = []
    for term, detail in SCALE_TERMS.items():
        if re.search(r"\b" + re.escape(term), text):
            scale_hits.append(detail)
    scale_points = min(6, len(set(scale_hits)) * 2)
    if scale_points:
        factors.append(
            {
                "label": "Scale",
                "detail": "; ".join(sorted(set(scale_hits))[:3]),
                "points": scale_points,
            }
        )

    dup_points = 0
    if duplicate_count:
        dup_points = min(12, 4 + duplicate_count * 2 + (4 if duplicate_count >= 3 else 0))
        factors.append(
            {
                "label": "Reported more than once",
                "detail": f"{duplicate_count} similar nearby report(s) found",
                "points": dup_points,
            }
        )

    if has_image:
        factors.append(
            {"label": "Supporting photo", "detail": "citizen attached an image", "points": 2}
        )
    if has_location:
        factors.append(
            {"label": "Locatable report", "detail": "coordinates were provided", "points": 2}
        )

    penalty = 0
    low_hits = [detail for term, detail in LOW_SEVERITY_TERMS.items() if re.search(r"\b" + re.escape(term), text)]
    if low_hits:
        penalty = 8
        factors.append(
            {
                "label": "Lower severity wording",
                "detail": "; ".join(sorted(set(low_hits))),
                "points": -penalty,
            }
        )

    raw = (
        base
        + severe_points
        + moderate_points
        + impact_points
        + urgency_points
        + scale_points
        + dup_points
        + (2 if has_image else 0)
        + (2 if has_location else 0)
        - penalty
    )
    score = max(0, min(98, raw))
    level = priority_level_for(score, config)

    reason_parts = []
    for factor in factors:
        if factor["points"] > 0:
            reason_parts.append(f"{factor['label'].lower()} (+{factor['points']})")
    if penalty:
        reason_parts.append(f"lower-severity wording (-{penalty})")
    explanation = (
        f"{level} priority ({score}/100). "
        + "Contributing signals: " + ", ".join(reason_parts) + ". "
        + "This is decision support based on the report text and available context; "
        + "it is not a verified assessment of real-world danger."
    )

    return {
        "score": score,
        "level": level,
        "explanation": explanation,
        "factors": factors,
        "disclaimer": "Priority is an explainable estimate, not a guarantee of danger.",
    }
