"""Settings, read once from the environment (.env in dev)."""
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    # Fail fast with a readable message instead of a confusing 500 later.
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name} (see backend-py/.env.example)")
    return value


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    paystack_secret_key: str
    frontend_origins: list[str]
    timezone: str            # ONE business timezone for every "today/this week" boundary
    telegram_bot_token: str
    telegram_chat_id: str
    reminder_interval_hours: int
    reminder_cron: str       # standard 5-field cron, evaluated in `timezone`
    disable_scheduler: bool
    # Customer reminders (all optional - a channel with no config is simply "not configured")
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_starttls: bool
    termii_api_key: str
    termii_sender_id: str
    termii_base_url: str
    customer_reminder_cooldown_hours: int
    # AI (Day 7/8)
    llm_base_url: str   # any OpenAI-compatible endpoint serving a Llama model (Groq, Together, Ollama, ...)
    llm_api_key: str
    llm_model: str
    ai_requests_per_10min: int

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_settings() -> Settings:
    return Settings(
        supabase_url=_required("SUPABASE_URL"),
        supabase_service_role_key=_required("SUPABASE_SERVICE_ROLE_KEY"),
        paystack_secret_key=_required("PAYSTACK_SECRET_KEY"),
        frontend_origins=[o.strip() for o in os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173").split(",")],
        timezone=os.environ.get("BUSINESS_TIMEZONE", "Africa/Lagos"),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        reminder_interval_hours=int(os.environ.get("REMINDER_INTERVAL_HOURS", "24")),
        reminder_cron=os.environ.get("REMINDER_CRON", "0 8 * * *"),
        disable_scheduler=os.environ.get("DISABLE_SCHEDULER", "false").lower() == "true",
        smtp_host=os.environ.get("SMTP_HOST", ""),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=os.environ.get("SMTP_USER", ""),
        smtp_password=os.environ.get("SMTP_PASSWORD", ""),
        smtp_from=os.environ.get("SMTP_FROM", "") or os.environ.get("SMTP_USER", ""),
        smtp_starttls=os.environ.get("SMTP_STARTTLS", "true").lower() == "true",
        termii_api_key=os.environ.get("TERMII_API_KEY", ""),
        termii_sender_id=os.environ.get("TERMII_SENDER_ID", ""),
        termii_base_url=os.environ.get("TERMII_BASE_URL", "https://api.ng.termii.com").rstrip("/"),
        customer_reminder_cooldown_hours=int(os.environ.get("CUSTOMER_REMINDER_COOLDOWN_HOURS", "24")),
        llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        llm_model=os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile"),
        ai_requests_per_10min=int(os.environ.get("AI_REQUESTS_PER_10MIN", "20")),
    )


settings = load_settings()
