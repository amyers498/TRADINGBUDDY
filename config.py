"""Configuration utilities for the Trade Buddy system."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


def _env(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Return the value of *name* from the environment with optional default."""
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


GOOGLE_APPLICATION_CREDENTIALS = _env("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_OAUTH_CLIENT_SECRETS = _env("GOOGLE_OAUTH_CLIENT_SECRETS")
GOOGLE_OAUTH_TOKEN_FILE = Path(_env("GOOGLE_OAUTH_TOKEN_FILE", "token.json"))
if not (GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_OAUTH_CLIENT_SECRETS):
    raise RuntimeError(
        "Either GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_OAUTH_CLIENT_SECRETS must be set"
    )

RAW_TRADES_FOLDER_ID = _env("RAW_TRADES_FOLDER_ID", required=True)
DAILY_REPORTS_FOLDER_ID = _env("DAILY_REPORTS_FOLDER_ID", required=True)
WEEKLY_REPORTS_FOLDER_ID = _env("WEEKLY_REPORTS_FOLDER_ID", required=True)
MONTHLY_REPORTS_FOLDER_ID = _env("MONTHLY_REPORTS_FOLDER_ID", required=True)

GEMINI_API_KEY = _env("GEMINI_API_KEY", required=True)
GEMINI_MODEL_NAME = _env("GEMINI_MODEL_NAME", "gemini-2.5-pro")

EMAIL_FROM = _env("EMAIL_FROM", required=True)
EMAIL_TO = _env("EMAIL_TO", required=True)
SMTP_HOST = _env("SMTP_HOST", required=True)
SMTP_PORT = int(_env("SMTP_PORT", "587"))
SMTP_USERNAME = _env("SMTP_USERNAME", required=True)
SMTP_PASSWORD = _env("SMTP_PASSWORD", required=True)

DB_PATH = Path(_env("TRADE_BUDDY_DB_PATH", "trade_buddy.db"))
DOWNLOAD_DIR = Path(_env("TRADE_BUDDY_DOWNLOAD_DIR", "downloads"))
REPORTS_DIR = Path(_env("TRADE_BUDDY_REPORTS_DIR", "reports"))
DAILY_REPORTS_LOCAL_DIR = REPORTS_DIR / "daily"
WEEKLY_REPORTS_LOCAL_DIR = REPORTS_DIR / "weekly"
MONTHLY_REPORTS_LOCAL_DIR = REPORTS_DIR / "monthly"

for directory in (
    DOWNLOAD_DIR,
    REPORTS_DIR,
    DAILY_REPORTS_LOCAL_DIR,
    WEEKLY_REPORTS_LOCAL_DIR,
    MONTHLY_REPORTS_LOCAL_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)
