import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Required ──────────────────────────────────────
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

    # ── Optional live music APIs ──────────────────────
    TICKETMASTER_API_KEY: str = os.getenv("TICKETMASTER_API_KEY", "")
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    SETLISTFM_API_KEY: str = os.getenv("SETLISTFM_API_KEY", "")

    # ── API server ────────────────────────────────────
    PLANNER_API_KEY: str = os.getenv("PLANNER_API_KEY", "")

    # ── Agent behaviour ───────────────────────────────
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    MAX_LOOP_ITERATIONS: int = int(os.getenv("MAX_LOOP_ITERATIONS", "3"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> None:
        """Raises RuntimeError if required config is missing."""
        if not cls.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. "
                "Copy .env.example → .env and add your key."
            )
