"""
Central configuration for the Smart Study App backend.
All environment-driven settings live here so nothing is hard-coded
inside routes or services.
"""

import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Folders ---
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Database ---
DB_PATH = os.path.join(BASE_DIR, "database.db")

# --- AI ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-5")

# --- Uploads ---
ALLOWED_EXTENSIONS = {"pdf"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB

# --- Quiz ---
DEFAULT_QUIZ_LENGTH = 5
WEAK_TOPIC_THRESHOLD = 0.6  # below 60% correct on a topic => "weak"


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
