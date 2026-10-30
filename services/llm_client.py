"""Optional LLM integration for classification and summarisation.

Only used when LLM_BASE_URL and LLM_MODEL are configured. The key is read from
the server environment and is never sent to the browser. Any failure falls back
to the local rule-based pipeline.
"""
import json
import re

import requests
from flask import current_app, has_app_context

from models import CATEGORIES


class LLMError(RuntimeError):
    pass


def llm_status():
    if not has_app_context():
        return {"enabled": False, "model": None, "label": "Local rule-based NLP"}
    config = current_app.config
    if config.get("LLM_BASE_URL") and config.get("LLM_MODEL"):
        return {
            "enabled": True,
            "model": config["LLM_MODEL"],
            "label": f"LLM: {config['LLM_MODEL']}",
        }
    return {"enabled": False, "model": None, "label": "Local rule-based NLP"}


def _extract_json(content):
    if not content:
        raise LLMError("Empty response from language model")
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.S)
    if fenced:
        content = fenced.group(1)
    else:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            content = content[start : end + 1]
    try:
        return json.loads(content)
    except ValueError as exc:
        raise LLMError("Language model returned malformed JSON") from exc


def analyze_with_llm(title, description):
    config = current_app.config
    if not (config.get("LLM_BASE_URL") and config.get("LLM_MODEL")):
        raise LLMError("No LLM endpoint configured")

    system_prompt = (
        "You are a civic complaint triage assistant. Return ONLY a JSON object "
        'with keys "category" and "summary". "category" must be exactly one of: '
        + ", ".join(CATEGORIES)
        + '. "summary" must be one concise, neutral sentence under 200 characters. '
        "Do not invent facts, locations, injuries or causes. If uncertain, use Other."
    )
    user_prompt = f"Title: {title}\nComplaint: {description}"
    headers = {"Content-Type": "application/json"}
    if config.get("LLM_API_KEY"):
        headers["Authorization"] = f"Bearer {config['LLM_API_KEY']}"

    payload = {
        "model": config["LLM_MODEL"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }
    url = config["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=config.get("LLM_TIMEOUT_SECONDS", 12),
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"LLM request failed: {exc.__class__.__name__}") from exc

    parsed = _extract_json(content)
    category = str(parsed.get("category", "")).strip()
    summary = str(parsed.get("summary", "")).strip()
    if category not in CATEGORIES:
        raise LLMError("LLM returned an unsupported category")
    if not summary or len(summary) < 8:
        raise LLMError("LLM returned an empty summary")
    return {
        "category": category,
        "summary": summary[:240],
        "model": config["LLM_MODEL"],
    }
