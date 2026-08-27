from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = "config/settings.yaml"


class LLMSettings(BaseModel):
    api_key_env: str = "LLM_API_KEY"

    @property
    def provider(self) -> str:
        value = os.environ.get("LLM_PROVIDER")
        if not value:
            raise RuntimeError("Set LLM_PROVIDER in your .env file (e.g. 'gemini' or 'claude').")
        return value

    @property
    def model(self) -> str:
        value = os.environ.get("LLM_MODEL")
        if not value:
            raise RuntimeError("Set LLM_MODEL in your .env file (e.g. 'claude-haiku-4-5').")
        return value

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


class PlaywrightSettings(BaseModel):
    headless: bool = True
    timeout_ms: int = 30_000
    # Caps simultaneous Chromium instances when scraping multiple companies at
    # once (scrape-all, scheduler tick) — the LLM call for each company rides
    # along in the same worker thread, so this also bounds concurrent LLM calls.
    max_concurrency: int = 4
    # Upper bound on "next page" / "load more" / infinite-scroll steps the fetcher
    # follows past the first screen of results. A safety cap, not a target — the
    # fetcher stops as soon as a step yields nothing new.
    max_pages: int = 20


class StorageSettings(BaseModel):
    root: str = "data/"


class LoggingSettings(BaseModel):
    level: str = "info"


class Settings(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
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
