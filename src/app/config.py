from __future__ import annotations

import os
from pathlib import Path

import yaml
from croniter import croniter
from pydantic import BaseModel, Field, field_validator


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


class SiteConfig(BaseModel):
    id: str
    name: str
    url: str
    frequency: str
    enabled: bool = True
    wait_selector: str | None = None

    @field_validator("frequency")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        if not croniter.is_valid(value):
            raise ValueError(f"'{value}' is not a valid cron expression")
        return value


class AppConfig(BaseModel):
    settings: Settings
    sites: list[SiteConfig]

    def get_site(self, site_id: str) -> SiteConfig:
        for site in self.sites:
            if site.id == site_id:
                return site
        raise KeyError(f"No site with id '{site_id}' in config")


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    with path.open("r") as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw)
