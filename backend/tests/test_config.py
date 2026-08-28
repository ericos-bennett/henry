"""Hermetic tests for LLMSettings reading provider/model from env vars."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from pathlib import Path

from app.config import LLMSettings, PlaywrightSettings, StorageSettings


class LLMSettingsTest(unittest.TestCase):
    def test_provider_and_model_read_from_env(self):
        settings = LLMSettings()
        with patch.dict("os.environ", {"LLM_PROVIDER": "claude", "LLM_MODEL": "claude-haiku-4-5"}):
            self.assertEqual(settings.provider, "claude")
            self.assertEqual(settings.model, "claude-haiku-4-5")

    def test_provider_raises_when_unset(self):
        settings = LLMSettings()
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                settings.provider

    def test_model_raises_when_unset(self):
        settings = LLMSettings()
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                settings.model

    def test_api_key_env_defaults_to_llm_api_key(self):
        settings = LLMSettings()
        self.assertEqual(settings.api_key_env, "LLM_API_KEY")
        with patch.dict("os.environ", {"LLM_API_KEY": "secret"}):
            self.assertEqual(settings.api_key, "secret")


class PlaywrightSettingsTest(unittest.TestCase):
    def test_max_concurrency_defaults_to_four(self):
        self.assertEqual(PlaywrightSettings().max_concurrency, 4)


class StorageSettingsTest(unittest.TestCase):
    def test_defaults_to_home_backups_henry(self):
        s = StorageSettings()
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(s.db_dir, Path.home() / "backups/henry/db")
            self.assertEqual(s.scrapes_dir, Path.home() / "backups/henry/scrapes")

    def test_henry_backup_dir_env_drives_both_subdirs(self):
        s = StorageSettings()
        with patch.dict("os.environ", {"HENRY_BACKUP_DIR": "/mnt/backups"}):
            self.assertEqual(s.db_dir, Path("/mnt/backups/db"))
            self.assertEqual(s.scrapes_dir, Path("/mnt/backups/scrapes"))
