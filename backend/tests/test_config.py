"""Hermetic tests for LLMSettings reading provider/model from env vars."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.config import LLMSettings


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
