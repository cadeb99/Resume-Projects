"""All settings in one place, loaded from environment variables / .env file.

Nothing secret is hard-coded here — real values come from your .env (which is
gitignored). See .env.example for the full list.
"""

import random
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Meta / Instagram, with a backup app ready (Requirement 1 & 4) ---
    # Flip ACTIVE_APP to "backup" if Meta revokes the primary app's access.
    active_app: str = "primary"

    ig_verify_token: str = "change-me-to-a-random-string"  # webhook handshake secret
    ig_app_secret: str = ""        # primary app — verifies incoming webhook signatures
    ig_access_token: str = ""      # primary app — used to send replies

    ig_backup_app_secret: str = ""     # backup app credentials (Requirement 1)
    ig_backup_access_token: str = ""

    graph_api_version: str = "v21.0"

    # --- The AI (Requirement 3) ---
    anthropic_api_key: str = ""
    # Defaults to the most capable model. For a high-volume bot you may switch to
    # a faster/cheaper one (claude-haiku-4-5) — just change this env var.
    ai_model: str = "claude-opus-4-8"
    ai_timeout_seconds: float = 8.0      # if the AI is slower than this -> fallback message
    ai_max_tokens: int = 1024
    confidence_threshold: float = 0.6    # (reserved) AI reports confidence per reply; not used to force takeover
    holding_message: str = (
        "Thanks for reaching out! We'll get back to you shortly."
    )

    # --- Human-like response delay (so replies don't look like an instant bot) ---
    # Before sending an auto-reply we wait a random interval in this range. Applies
    # to live replies only; /simulate just reports the delay instead of waiting.
    response_delay_min_minutes: float = 10.0
    response_delay_max_minutes: float = 30.0

    # --- Human takeover triggers (Requirement 5) ---
    # Brand rule: only affiliate/sponsorship inquiries go to a human. These keywords
    # are a backup net; the AI is the primary detector. Everything else -> support email.
    takeover_keywords: str = (
        "affiliate,sponsor,sponsorship,sponsored,collab,collaboration,"
        "ambassador,team rider"
    )

    # --- Alerts to the owner (Requirements 5 & 7) ---
    notify_channel: str = "console"  # console | slack | twilio
    owner_name: str = "your friend"
    slack_webhook_url: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    owner_phone_number: str = ""

    # --- Storage (Requirement 6) ---
    database_path: str = "data/automation.db"

    # --- Send retry (Requirement 4) ---
    send_max_retries: int = 3

    # The active app's credentials, chosen by ACTIVE_APP.
    @property
    def app_secret(self) -> str:
        return self.ig_backup_app_secret if self.active_app == "backup" else self.ig_app_secret

    @property
    def access_token(self) -> str:
        return self.ig_backup_access_token if self.active_app == "backup" else self.ig_access_token

    @property
    def keyword_list(self) -> list[str]:
        return [k.strip().lower() for k in self.takeover_keywords.split(",") if k.strip()]

    def random_response_delay_seconds(self) -> float:
        """A random, human-like delay (in seconds) to wait before an auto-reply."""
        lo = self.response_delay_min_minutes * 60.0
        hi = self.response_delay_max_minutes * 60.0
        if hi <= lo:
            return max(lo, 0.0)
        return random.uniform(lo, hi)


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env is read once per process."""
    return Settings()
