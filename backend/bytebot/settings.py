from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
CORS_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get(
        "BYTEBOT_CORS_ORIGINS",
        "http://127.0.0.1:5174,http://localhost:5174",
    ).split(",")
    if origin.strip()
)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', '')
EXTRACTION_MODE = os.environ.get('BYTEBOT_EXTRACTION_MODE', 'gemini')
SARVAM_API_KEY = os.environ.get('SARVAM_API_KEY', '')
SARVAM_CHAT_MODEL = os.environ.get('SARVAM_CHAT_MODEL', 'sarvam-105b-conversations')
