"""Duplicate detection using TF-IDF + cosine similarity + geographic proximity.

Implemented with the Python standard library only (no scikit-learn required):
tokens are normalised, TF-IDF weighted and compared with cosine similarity.
Text similarity alone never merges records; location is required for normal
matches and an officer must confirm a suggested duplicate.
"""
import math
from collections import Counter

from models import DuplicateLink
from services.nlp import keyword_tokens

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return round(EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 3)


def _vectors(documents):
    token_counts = [Counter(keyword_tokens(doc)) for doc in documents]
    doc_count = len(documents)
    doc_freq = Counter()
    for counts in token_counts:
        doc_freq.update(counts.keys())

    vectors = []
    for counts in token_counts:
        vector = {}
        for token, count in counts.items():
            tf = 1 + math.log(count)
            idf = math.log((1 + doc_count) / (1 + doc_freq[token])) + 1
            vector[token] = tf * idf
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        vectors.append({token: value / norm for token, value in vector.items()})
    return vectors


def _cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(token, 0.0) for token, value in a.items())


def text_similarity(text_a, text_b):
    if not (text_a or "").strip() or not (text_b or "").strip():
        return 0.0
    vectors = _vectors([text_a, text_b])
    return round(max(0.0, min(1.0, _cosine(vectors[0], vectors[1]))), 3)


def _proximity(distance_km):
    if distance_km is None:
        return None
    if distance_km <= 0.25:
        return 1.0
    if distance_km <= 0.75:
        return 1.0 - 0.4 * ((distance_km - 0.25) / 0.5)
    if distance_km <= 1.5:
        return 0.6 * (1 - (distance_km - 0.75) / 0.75)
    return 0.0


def _location_reason(distance_km):
    if distance_km is None:
        return "Location unavailable for one report; match is text-only"
    if distance_km < 0.1:
        return f"Same location (about {int(distance_km * 1000)} m apart)"
    if distance_km < 1:
        return f"Very close locations (about {int(distance_km * 1000)} m apart)"
    return f"Nearby locations (about {distance_km:.1f} km apart)"


def find_duplicates(complaint, candidates, config=None, limit=5):
    """Find possible duplicates for a complaint ORM object-like value.

    Both objects need public_id, title, description, latitude, longitude and
    category attributes. Returns a list of dicts with evidence, not merges.
    """
    config = config or {}
    score_min = config.get("DUPLICATE_SCORE_MIN", 0.42)
    text_min = config.get("DUPLICATE_TEXT_MIN", 0.30)
    text_only_min = config.get("DUPLICATE_TEXT_ONLY_MIN", 0.55)
    max_distance = config.get("DUPLICATE_MAX_DISTANCE_KM", 1.5)

    own_text = f"{complaint.title} {complaint.title} {complaint.description}"
    viable = []
    own_id = getattr(complaint, "public_id", None)
    for candidate in candidates:
        if getattr(candidate, "public_id", None) == own_id:
            continue
        if getattr(candidate, "duplicate_of_id", None):
            continue

        candidate_text = (
            f"{candidate.title} {candidate.title} {candidate.description}"
        )
        text_score = text_similarity(own_text, candidate_text)
        distance = haversine_km(
            complaint.latitude,
            complaint.longitude,
            candidate.latitude,
            candidate.longitude,
        )
        same_category = complaint.category == candidate.category

        if distance is None:
            if text_score < text_only_min:
                continue
            combined = text_score
            reason_prefix = "Text-only match; at least one complaint has no coordinates"
        else:
            if distance > max_distance or text_score < text_min:
                continue
            proximity = _proximity(distance)
            combined = 0.72 * text_score + 0.28 * proximity
            if not same_category:
                # Different categories can still be one underlying issue, but
                # require much stronger evidence and a very close location.
                if text_score < 0.60 or distance > 0.5:
                    continue
                combined -= 0.06
            if combined < score_min:
                continue
            reason_prefix = _location_reason(distance)

        reasons = [
            f"Text similarity {round(text_score * 100)}% (TF-IDF cosine)",
            reason_prefix,
        ]
        if distance is not None:
            reasons.append(f"Distance {distance:.2f} km")
        reasons.append(
            f"Same category: {complaint.category}"
            if same_category
            else f"Different categories: {complaint.category} / {candidate.category}"
        )

        viable.append(
            {
                "complaint": candidate,
                "public_id": candidate.public_id,
                "text_similarity": round(text_score, 3),
                "distance_km": distance,
                "combined_score": round(max(0.0, min(1.0, combined)), 3),
                "same_category": same_category,
                "reasons": reasons,
            }
        )

    viable.sort(
        key=lambda item: (item["combined_score"], item["text_similarity"]),
        reverse=True,
    )
    return viable[:limit]


def update_suggested_links(complaint, results):
    """Persist suggestions in a canonical newer->older direction."""
    for result in results:
        candidate = result["complaint"]
        newer, older = (
            (complaint, candidate) if complaint.id > candidate.id else (candidate, complaint)
        )
        link = DuplicateLink.query.filter_by(
            complaint_id=newer.id, duplicate_of_id=older.id
        ).first()
        if link is None:
            link = DuplicateLink(
                complaint_id=newer.id,
                duplicate_of_id=older.id,
                text_similarity=result["text_similarity"],
                distance_km=result["distance_km"],
                combined_score=result["combined_score"],
                reason="; ".join(result["reasons"]),
                status="suggested",
            )
            from extensions import db

            db.session.add(link)
    from extensions import db

    db.session.flush()


def confirmed_link_between(complaint_id_a, complaint_id_b):
    low, high = sorted((complaint_id_a, complaint_id_b))
    return DuplicateLink.query.filter_by(
        complaint_id=high, duplicate_of_id=low, status="confirmed"
    ).first()


def suggestion_status_map(complaint_id):
    """Map other-complaint id -> link status for links touching this complaint."""
    links = DuplicateLink.query.filter(
        (DuplicateLink.complaint_id == complaint_id)
        | (DuplicateLink.duplicate_of_id == complaint_id)
    ).all()
    result = {}
    for link in links:
        other_id = (
            link.duplicate_of_id
            if link.complaint_id == complaint_id
            else link.complaint_id
        )
        result[other_id] = link.status
    return result
