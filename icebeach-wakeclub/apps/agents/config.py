from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv()


@dataclass(frozen=True)
class AgentsSettings:
    api_base: str
    secret: str | None
    log_path: Path
    telegram_bot_token: str | None
    telegram_owner_chat_id: str | None


def get_agents_settings() -> AgentsSettings:
    log_path = _REPO_ROOT / "logs" / "agents.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return AgentsSettings(
        api_base=os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000").rstrip("/"),
        secret=os.getenv("AGENTS_SECRET", "").strip() or None,
        log_path=log_path,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None,
        telegram_owner_chat_id=os.getenv("TELEGRAM_OWNER_CHAT_ID", "").strip() or None,
    )
