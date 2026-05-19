# -*- coding: utf-8 -*-
"""Tests for fallback LiteLLM pricing registration."""

import unittest
from unittest.mock import patch

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    from tests.litellm_stub import ensure_litellm_stub

    ensure_litellm_stub()

from src.agent import llm_adapter


class LiteLLMFallbackPricingTestCase(unittest.TestCase):
    def test_register_fallback_pricing_registers_unknown_openai_model(self) -> None:
        registered = []

        def _register(payload):
            registered.append(payload)

        with patch.object(llm_adapter.litellm, "register_model", side_effect=_register, create=True):
            with patch.object(llm_adapter.litellm, "model_cost", {}, create=True):
                llm_adapter._FALLBACK_MODEL_PRICING_REGISTERED.clear()
                llm_adapter.register_fallback_model_pricing(["openai/mimo-alpha"])

        self.assertTrue(any("mimo-alpha" in payload for payload in registered))

    def test_register_fallback_pricing_skips_custom_pricing_models(self) -> None:
        registered = []

        def _register(payload):
            registered.append(payload)

        with patch.object(llm_adapter.litellm, "register_model", side_effect=_register, create=True):
            with patch.object(llm_adapter.litellm, "model_cost", {"MiniMax-M2.7": {"input_cost_per_token": 1.0}}, create=True):
                llm_adapter._FALLBACK_MODEL_PRICING_REGISTERED.clear()
                llm_adapter.register_fallback_model_pricing(["openai/MiniMax-M2.7", "openai/mimo-beta"])

        self.assertFalse(any("MiniMax-M2.7" in payload for payload in registered))
        self.assertTrue(any("mimo-beta" in payload for payload in registered))
