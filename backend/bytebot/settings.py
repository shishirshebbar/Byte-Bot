from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', '')
EXTRACTION_MODE = os.environ.get('BYTEBOT_EXTRACTION_MODE', 'gemini')
