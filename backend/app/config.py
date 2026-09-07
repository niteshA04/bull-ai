import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
SKILL_DIR = Path(__file__).resolve().parent / "skill"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

SCHEMA_PATH = BASE_DIR / "report_schema.json"
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    REPORT_SCHEMA = json.load(f)

with open(SKILL_DIR / "SKILL.md", "r", encoding="utf-8") as f:
    SKILL_TEXT = f.read()

FALLBACK_POLICY = REPORT_SCHEMA["fallback_policy"]

LLM_AVAILABLE = bool(ANTHROPIC_API_KEY)
