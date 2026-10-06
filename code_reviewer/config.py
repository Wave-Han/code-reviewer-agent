"""Configuration loaded from environment / .env."""
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv


def ensure_utf8_stdout() -> None:
    """Reconfigure stdout to UTF-8 (Windows GBK console fix)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class Config:
    zhipu_api_key: str
    model: str = "glm-4"
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"


def load_config(env_file: str = ".env") -> Config:
    load_dotenv(env_file)
    return Config(
        zhipu_api_key=os.environ.get("ZHIPU_API_KEY", ""),
        model=os.environ.get("CR_MODEL", "glm-4"),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY") or None,
        deepseek_model=os.environ.get("CR_DEEPSEEK_MODEL", "deepseek-chat"),
    )
