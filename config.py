import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    @staticmethod
    def _env(key, default=""):
        return os.environ.get(key, default)

    @property
    def SECRET_KEY(self):
        return self._env("SECRET_KEY", "arthi-x-dev-secret-change-in-production")

    @property
    def DATABASE_URL(self):
        return self._env(
            "DATABASE_URL",
            "mysql+pymysql://arthix:arthix@localhost:3307/arthix",
        )

    @property
    def LLM_PROVIDER(self):
        return self._env("LLM_PROVIDER", "auto")

    @property
    def ANTHROPIC_API_KEY(self):
        return self._env("ANTHROPIC_API_KEY", "")

    @property
    def OPENAI_API_KEY(self):
        return self._env("OPENAI_API_KEY", "")

    @property
    def TELEGRAM_BOT_TOKEN(self):
        return self._env("TELEGRAM_BOT_TOKEN", "")

    @property
    def TELEGRAM_CHAT_ID(self):
        return self._env("TELEGRAM_CHAT_ID", "")

    @property
    def CONFIDENCE_THRESHOLD(self):
        return int(self._env("CONFIDENCE_THRESHOLD", "7"))

    @property
    def DEMO_MODE(self):
        return self._env("DEMO_MODE", "auto")

    @property
    def AGENT_DELAY(self):
        return float(self._env("AGENT_DELAY", "0.3"))

    @property
    def SHORTLIST_PER_BUCKET(self):
        return int(self._env("SHORTLIST_PER_BUCKET", "4"))

    @property
    def PORT(self):
        return int(self._env("PORT", "5000"))

    @property
    def SESSION_COOKIE_SECURE(self):
        return self._env("SESSION_COOKIE_SECURE", "false").lower() == "true"

    @property
    def SESSION_COOKIE_HTTPONLY(self):
        return True

    @property
    def SESSION_COOKIE_SAMESITE(self):
        return "Lax"

    @property
    def RATE_LIMIT_PER_MINUTE(self):
        return int(self._env("RATE_LIMIT_PER_MINUTE", "10"))

    @property
    def ANALYSIS_CACHE_TTL(self):
        return int(self._env("ANALYSIS_CACHE_TTL", "900"))

    @classmethod
    def is_demo_mode(cls):
        mode = cls._env("DEMO_MODE", "auto").lower()
        if mode == "true":
            return True
        if mode == "false":
            return False
        provider = cls._env("LLM_PROVIDER", "auto")
        return not provider or provider == "auto"


config = Config()
