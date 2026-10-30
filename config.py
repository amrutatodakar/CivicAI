"""Application configuration for CivicAI.

Values are read from environment variables so that no secret is committed.
A working local configuration is used when optional services are absent.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"


class Config:
    # Core
    SECRET_KEY = os.getenv("SECRET_KEY", "civicai-demo-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{(INSTANCE_DIR / 'civicai.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024  # 6 MB request cap (5 MB image + form)

    # Uploads
    UPLOAD_FOLDER = str(UPLOAD_DIR)
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
    MAX_IMAGE_BYTES = 5 * 1024 * 1024

    # Demo officer access. This is deliberately simple for the hackathon MVP.
    OFFICER_USERNAME = os.getenv("OFFICER_USERNAME", "officer")
    OFFICER_PASSWORD = os.getenv("OFFICER_PASSWORD", "civic2026")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Local processing / seeding
    SEED_ON_START = os.getenv("SEED_ON_START", "1") == "1"
    CSRF_ENABLED = os.getenv("CSRF_ENABLED", "1") == "1"

    # Explainable priority thresholds (0-100)
    PRIORITY_CRITICAL_MIN = 80
    PRIORITY_HIGH_MIN = 60
    PRIORITY_MEDIUM_MIN = 35

    # Duplicate detection thresholds
    DUPLICATE_SCORE_MIN = 0.40
    DUPLICATE_TEXT_MIN = 0.24
    DUPLICATE_TEXT_ONLY_MIN = 0.55
    DUPLICATE_MAX_DISTANCE_KM = 1.5

    # Hotspot detection (haversine kilometres / DBSCAN-like)
    HOTSPOT_RADIUS_KM = 0.7
    HOTSPOT_MIN_REPORTS = 3

    # Optional OpenAI-compatible LLM. When unset, local NLP is used.
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "")
    LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "12"))

    @property
    def LLM_ENABLED(self):
        return bool(self.LLM_BASE_URL and self.LLM_MODEL)
