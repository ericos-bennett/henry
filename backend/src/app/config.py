from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = "config/settings.yaml"


class LLMSettings(BaseModel):
    provider: str
    model: str
    api_key_env: str

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


class PlaywrightSettings(BaseModel):
    headless: bool = True
    timeout_ms: int = 30_000


class StorageSettings(BaseModel):
    root: str = "data/"


class LoggingSettings(BaseModel):
    level: str = "info"


class Settings(BaseModel):
    llm: LLMSettings
    playwright: PlaywrightSettings = Field(default_factory=PlaywrightSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


class AppConfig(BaseModel):
    settings: Settings


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    path = Path(path)
    with path.open("r") as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw)
