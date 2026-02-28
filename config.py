import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Anthropic
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# App
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
URL_PREFIX = os.environ.get("URL_PREFIX", "")  # e.g. "/sunosmart" for subpath deployment

# Paths — use Render persistent disk if available, else local data/
if os.environ.get("RENDER"):
    DATA_DIR = Path("/opt/render/project/src/data")
else:
    DATA_DIR = BASE_DIR / "data"

TRANSCRIPTS_DIR = DATA_DIR / "transcripts"

# Search
MAX_SEARCH_RESULTS = 20
SEARCH_CONTEXT_WINDOW = 3

# Scanner
SCAN_INTERVAL_HOURS = 4
NEWS_GENERATION_HOUR = 0  # midnight UTC
