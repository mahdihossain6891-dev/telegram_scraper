"""Tests for generation and conversation configuration."""

from __future__ import annotations

import pytest

from simulator.generation_config import GenerationConfig


class TestGenerationConfig:
    def test_phase4_fields_serialize(self) -> None:
        config = GenerationConfig(
            simulation_speed_multiplier=360.0,
            average_conversation_length=14,
            maximum_concurrent_conversations=4,
            average_replies=0.8,
            average_delay_seconds=90,
            message_length_multiplier=1.25,
            reply_probability=0.7,
            reaction_probability=0.2,
        )
        data = config.to_dict()
        assert data["simulation_speed_multiplier"] == 360.0
        assert data["average_conversation_length"] == 14
        assert data["maximum_concurrent_conversations"] == 4
        assert data["message_length_multiplier"] == 1.25
        assert data["reply_probability"] == 0.7

    def test_invalid_phase4_probabilities_raise(self) -> None:
        with pytest.raises(ValueError):
            GenerationConfig(reply_probability=1.2)
