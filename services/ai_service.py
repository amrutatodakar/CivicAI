"""Complaint understanding pipeline: category, summary, priority, department.

Order of operations:
1. Local keyword classifier and extractive summary always run.
2. If an OpenAI-compatible LLM is configured, it may replace category/summary;
   malformed responses or timeouts fall back to the local result.
3. Priority scoring is always deterministic and explainable (never delegated).
"""
from flask import current_app

from models import CATEGORIES
from services import llm_client
from services.nlp import classify_category, summarize
from services.priority_service import score_priority

DEPARTMENT_BY_CATEGORY = {
    "Road Damage": "Road Maintenance",
    "Waterlogging": "Stormwater & Drainage",
    "Garbage and Waste": "Sanitation",
    "Drainage": "Stormwater & Drainage",
    "Streetlight": "Electrical Services",
    "Public Safety": "Public Safety Cell",
    "Other": "General Administration",
}


def analyze_complaint(
    title,
    description,
    selected_category=None,
    duplicate_count=0,
    has_image=False,
    has_location=False,
):
    local_category, confidence, evidence = classify_category(title, description)
    category = local_category
    category_source = "local_keyword_rules"
    summary = summarize(description, local_category)
    summary_source = "extractive"
    engine = "Local rule-based NLP"
    notes = []

    config = current_app.config if current_app else {}
    if config.get("LLM_BASE_URL") and config.get("LLM_MODEL"):
        try:
            llm_result = llm_client.analyze_with_llm(title, description)
            category = llm_result["category"]
            summary = llm_result["summary"]
            summary_source = "llm"
            engine = f"LLM · {llm_result['model']}"
            category_source = "llm"
            confidence = max(confidence, 0.7)
        except llm_client.LLMError as exc:
            notes.append(f"LLM unavailable; local NLP used ({exc}).")
            engine = "Local rule-based NLP (LLM fallback)"

    # If local rules cannot confidently classify, respect a valid category the
    # citizen explicitly chose instead of silently forcing "Other".
    if category_source == "local_keyword_rules" and local_category == "Other":
        if selected_category in CATEGORIES and selected_category != "Other":
            category = selected_category
            category_source = "citizen_selected_fallback"
            confidence = 0.35
            notes.append("Low keyword confidence; used the citizen-selected category.")
            summary = summarize(description, category)

    priority = score_priority(
        title=title,
        description=description,
        category=category,
        duplicate_count=duplicate_count,
        has_image=has_image,
        has_location=has_location,
        config=config,
    )

    return {
        "category": category,
        "category_confidence": round(float(confidence), 2),
        "category_source": category_source,
        "category_evidence": evidence,
        "summary": summary,
        "summary_source": summary_source,
        "priority_score": priority["score"],
        "priority_level": priority["level"],
        "priority_explanation": priority["explanation"],
        "priority_factors": priority["factors"],
        "recommended_department": DEPARTMENT_BY_CATEGORY.get(
            category, "General Administration"
        ),
        "ai_engine": engine,
        "ai_notes": " ".join(notes),
    }
