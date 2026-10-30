"""Shared lightweight NLP helpers.

This is a transparent, rule-based local pipeline: synonym normalisation,
tokenisation, a weighted civic-category lexicon and extractive summaries.
It is intentionally described as rule-based, not as a trained ML model.
"""
import math
import re
from collections import Counter

CATEGORY_KEYWORDS = {
    "Road Damage": {
        "hole": 7,
        "road hole": 6,
        "damaged road": 5,
        "road damage": 5,
        "broken road": 5,
        "cracked road": 4,
        "crack": 2,
        "asphalt": 2,
        "speed breaker": 3,
        "uneven road": 4,
        "footpath": 2,
        "pavement": 2,
        "road": 1,
    },
    "Waterlogging": {
        "waterlogging": 7,
        "waterlogged": 7,
        "standing water": 6,
        "flood": 6,
        "flooded": 6,
        "submerged": 5,
        "knee deep": 5,
        "water on road": 5,
        "rain water": 4,
        "water": 1,
    },
    "Garbage and Waste": {
        "garbage": 7,
        "trash": 6,
        "waste": 6,
        "dump": 5,
        "dumping": 5,
        "litter": 5,
        "bin": 3,
        "dustbin": 5,
        "rotting": 4,
        "smell": 2,
        "stink": 2,
        "uncollected": 5,
    },
    "Drainage": {
        "drainage": 7,
        "drain": 6,
        "sewer": 6,
        "sewage": 6,
        "manhole": 5,
        "blocked": 2,
        "overflowing drain": 6,
        "stagnant": 3,
        "open drain": 5,
        "sludge": 4,
    },
    "Streetlight": {
        "streetlight": 7,
        "street light": 7,
        "streetlamp": 6,
        "street lamp": 6,
        "lamp post": 5,
        "lamp": 4,
        "dark street": 4,
        "dark": 2,
        "light pole": 4,
        "pole": 2,
        "not working": 2,
        "flickering": 3,
    },
    "Public Safety": {
        "unsafe": 5,
        "safety": 4,
        "accident": 5,
        "injury": 5,
        "injured": 5,
        "live wire": 7,
        "open manhole": 6,
        "exposed wire": 6,
        "stray dog": 5,
        "collapse": 5,
        "collapsed": 5,
        "fire": 5,
        "danger": 4,
        "hazard": 4,
        "electrocution": 7,
    },
    "Other": {},
}

# Phrases that should be treated the same during normalisation. They make the
# classifier and duplicate detector robust to common Indian-English variants.
SYNONYM_PHRASES = [
    (r"\bpot\s*holes?\b", "hole"),
    (r"\bpotholes?\b", "hole"),
    (r"\broad\s+holes?\b", "hole"),
    (r"\bbus\s+stand\b", "bus stop"),
    (r"\bwater\s*logging\b", "waterlogging"),
    (r"\bwater\s+logged\b", "waterlogged"),
    (r"\bstreet\s*lights?\b", "streetlight"),
    (r"\bstreet\s*lamps?\b", "streetlight"),
    (r"\blamp\s+posts?\b", "streetlight"),
    (r"\btrash\b", "garbage"),
    (r"\brubbish\b", "garbage"),
    (r"\bwaste\b", "garbage"),
    (r"\bdust\s*bins?\b", "garbage"),
    (r"\bsewage\b", "sewer"),
    (r"\bdrains?\b", "drain"),
    (r"\bfloods?\b", "flood"),
    (r"\bflooded\b", "flood"),
    (r"\binjured\b", "injury"),
    (r"\baccidents?\b", "accident"),
    (r"\bdangerous\b", "danger"),
    (r"\bcollapsed\b", "collapse"),
    (r"\boverflowing\b", "overflow"),
    (r"\boverflowed\b", "overflow"),
    (r"\bdumping\b", "dump"),
    (r"\bman\s+holes?\b", "manhole"),
    (r"\blive\s+wires?\b", "live wire"),
    (r"\bexposed\s+wires?\b", "exposed wire"),
    (r"\bstray\s+dogs?\b", "stray dog"),
]

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "there", "here", "this", "that", "these", "those", "it", "its", "of",
    "to", "in", "on", "at", "for", "with", "and", "or", "but", "as", "by",
    "from", "near", "around", "very", "too", "also", "has", "have", "had",
    "we", "our", "you", "your", "they", "their", "he", "she", "his", "her",
    "i", "my", "me", "us", "them", "would", "could", "should", "will",
    "can", "may", "might", "please", "kindly", "some", "any", "all", "so",
    "into", "over", "under", "again", "more", "most", "such", "only", "own",
    "same", "than", "then", "once", "about", "not", "no", "if", "because",
    "while", "during", "after", "before", "up", "down", "out", "off",
    "just", "now", "get", "got", "make", "makes", "made", "see", "seen",
}


def normalize_text(text):
    value = (text or "").lower()
    value = value.replace("&", " and ")
    for pattern, replacement in SYNONYM_PHRASES:
        value = re.sub(pattern, replacement, value)
    value = re.sub(r"[^a-z0-9\s.]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def stem(token):
    """Small suffix stripper sufficient for matching civic vocabulary."""
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokens(text, keep_stopwords=False):
    normalized = normalize_text(text)
    result = []
    for token in re.findall(r"[a-z0-9]+", normalized):
        if len(token) < 3 and not token.isdigit():
            continue
        if not keep_stopwords and token in STOPWORDS:
            continue
        result.append(stem(token))
    return result


def keyword_tokens(text):
    """Unigrams plus bigrams, used for TF-IDF similarity."""
    normalized = normalize_text(text)
    words = [w for w in re.findall(r"[a-z0-9]+", normalized) if len(w) >= 3]
    unigrams = [stem(w) for w in words if w not in STOPWORDS]
    bigrams = [
        f"{stem(words[i])}_{stem(words[i + 1])}"
        for i in range(len(words) - 1)
        if words[i] not in STOPWORDS and words[i + 1] not in STOPWORDS
    ]
    return unigrams + bigrams


def classify_category(*texts):
    """Weighted keyword classifier returning category, confidence, evidence."""
    combined = normalize_text(" ".join(t for t in texts if t))
    scores = {}
    evidence = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        total = 0
        matched = []
        for phrase, weight in keywords.items():
            count = len(re.findall(r"\b" + re.escape(phrase) + r"\b", combined))
            if count:
                total += weight * min(count, 3)
                matched.append(phrase)
        scores[category] = total
        evidence[category] = matched

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_category, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if top_score == 0:
        return "Other", 0.18, []

    # Confidence rewards a clear margin, so ambiguous reports are labelled
    # with lower confidence rather than overstated certainty.
    confidence = top_score / (top_score + second_score + 2.0)
    confidence = max(0.25, min(0.97, confidence))
    return top_category, round(confidence, 2), evidence.get(top_category, [])


def sentence_split(text):
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if p.strip()]


def summarize(text, category="Other", max_chars=220):
    """Extractive summary: picks the most informative sentence(s).

    This is deliberately extractive and labelled as such in the UI; it does not
    pretend to be a generative model unless an LLM is explicitly configured.
    """
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    if not cleaned:
        return "No description was provided."

    sentences = sentence_split(cleaned)
    if len(sentences) <= 1 or len(cleaned) <= max_chars:
        return _truncate(cleaned, max_chars)

    category_terms = set(CATEGORY_KEYWORDS.get(category, {}).keys())
    scored = []
    for index, sentence in enumerate(sentences):
        low = normalize_text(sentence)
        score = max(0, 3 - index)  # earlier sentences are usually more useful
        score += sum(2 for term in category_terms if term in low)
        score += sum(
            1 for word in ("injury", "accident", "danger", "school", "hospital",
                           "children", "unsafe", "urgent", "blocked", "overflow")
            if word in low
        )
        length_penalty = 0 if 35 <= len(sentence) <= 180 else 1
        scored.append((score - length_penalty, index, sentence))

    scored.sort(reverse=True)
    chosen = []
    length = 0
    for _, index, sentence in scored[:3]:
        if length + len(sentence) + 1 <= max_chars:
            chosen.append((index, sentence))
            length += len(sentence) + 1
    if not chosen:
        return _truncate(sentences[0], max_chars)
    chosen.sort(key=lambda item: item[0])
    summary = " ".join(sentence for _, sentence in chosen)
    return _truncate(summary, max_chars)


def _truncate(text, limit):
    if len(text) <= limit:
        return text
    shortened = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:")
    return shortened + "…"


def category_from_text(*texts):
    return classify_category(*texts)[0]
