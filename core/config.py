"""Configuration — environment-variable driven, no hardcoded secrets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    """All runtime settings. Override via SENTINEL_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="SENTINEL_", env_file=_PROJECT_ROOT / ".env", extra="ignore")

    log_level: str = "INFO"
    database_path: str = "data/sentinel.db"
    plugins_dir: str = "plugins"

    detection_train_window: int = 100
    detection_z_window: int = 60
    anomaly_score_threshold: float = 0.65
    drift_alpha: float = 0.10
    drift_warmup: int = 120
    enable_lstm_ae: bool = False

    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    mqtt_enabled: bool = False
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic: str = "sentinel/events"

    ws_origin: str = "*"

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT

    @property
    def db_path(self) -> Path:
        p = Path(self.database_path)
        return p if p.is_absolute() else _PROJECT_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
