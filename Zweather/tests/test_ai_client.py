"""
Tests for the server-side AI client (Ollama/Gemma).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import pytest

from Zweather.ai_client import (
    SECTOR_CONFIG,
    _extract_json_object,
    _normalize_risk_level,
    analyze_forecast,
    analyze_risk,
    generate_site_map,
)


class TestAIClientCore:
    def test_sector_config_has_all_8_sectors(self):
        expected = {
            "construction", "agricultural", "industrial", "residential",
            "marine", "aviation", "energy", "transportation",
        }
        assert set(SECTOR_CONFIG.keys()) == expected

    def test_sector_config_missing(self):
        cfg = SECTOR_CONFIG.get("nonexistent", SECTOR_CONFIG["construction"])
        assert cfg["label"] == "Construction"

    def test_extract_json_object_valid(self):
        text = '{"riskLevel": "Red", "report": "Danger"}'
        result = _extract_json_object(text)
        assert result == {"riskLevel": "Red", "report": "Danger"}

    def test_extract_json_object_nested(self):
        text = '{"riskLevel":"Green","details":{"temp":20}}'
        result = _extract_json_object(text)
        assert result["riskLevel"] == "Green"
        assert result["details"]["temp"] == 20

    def test_extract_json_object_with_markdown_fence(self):
        text = '```json\n{"riskLevel": "Amber"}\n```'
        result = _extract_json_object(text)
        assert result.get("riskLevel") == "Amber"

    def test_extract_json_object_with_prefix_text(self):
        text = 'Here is the result: {"riskLevel": "Green"} --- end'
        result = _extract_json_object(text)
        assert result.get("riskLevel") == "Green"

    def test_extract_json_object_empty(self):
        assert _extract_json_object("") == {}
        assert _extract_json_object(None) == {}

    def test_extract_json_object_invalid(self):
        text = "This is not JSON at all and has no braces"
        result = _extract_json_object(text)
        assert result == {}

    def test_extract_json_object_unclosed(self):
        text = '{"riskLevel": "Red"'
        result = _extract_json_object(text)
        assert result == {}

    def test_normalize_risk_level_allowed(self):
        assert _normalize_risk_level("green") == "Green"
        assert _normalize_risk_level("RED") == "Red"
        assert _normalize_risk_level("amber") == "Amber"
        assert _normalize_risk_level("black") == "Black"

    def test_normalize_risk_level_unknown_falls_to_amber(self):
        assert _normalize_risk_level("purple") == "Amber"
        assert _normalize_risk_level("") == "Amber"
        assert _normalize_risk_level(None) == "Amber"

    def test_normalize_risk_level_numeric(self):
        assert _normalize_risk_level(1) == "Amber"

    @pytest.mark.asyncio
    @patch("Zweather.ai_client._generate_text", new_callable=AsyncMock)
    async def test_analyze_risk_all_sectors(self, mock_gen):
        mock_gen.return_value = '{"riskLevel": "Green", "report": "All clear"}'
        for sector in SECTOR_CONFIG:
            result = await analyze_risk(
                {"temp": 20.0, "humidity": 50.0, "pressure": 1013.0},
                sector,
            )
            assert result["riskLevel"] in ("Green", "Amber", "Red", "Black")
            assert "report" in result

    @pytest.mark.asyncio
    @patch("Zweather.ai_client._generate_text", new_callable=AsyncMock)
    async def test_analyze_risk_network_error(self, mock_gen):
        mock_gen.side_effect = RuntimeError("Ollama unreachable")
        with pytest.raises(RuntimeError, match="Ollama unreachable"):
            await analyze_risk(
                {"temp": 20.0, "humidity": 50.0, "pressure": 1013.0},
                "construction",
            )

    @pytest.mark.asyncio
    @patch("Zweather.ai_client._generate_text", new_callable=AsyncMock)
    async def test_analyze_forecast_all_sectors(self, mock_gen):
        mock_gen.return_value = '{"riskLevel": "Amber", "report": "Watch wind"}'
        forecast = [
            {"date": "2025-01-01", "tempMax": 20.0, "tempMin": 10.0,
             "precip": 30.0, "wind": 5.0, "uv": 2.0},
        ]
        for sector in SECTOR_CONFIG:
            result = await analyze_forecast(forecast, sector)
            assert result["riskLevel"] in ("Green", "Amber", "Red", "Black")
            assert "report" in result

    @pytest.mark.asyncio
    @patch("Zweather.ai_client._generate_text", new_callable=AsyncMock)
    async def test_analyze_forecast_invalid_json_response(self, mock_gen):
        mock_gen.return_value = "Some non-JSON response from the model"
        result = await analyze_forecast([], "construction")
        assert result["riskLevel"] == "Amber"  # default fallback
        assert result["report"] == ""

    @pytest.mark.asyncio
    @patch("Zweather.ai_client._generate_text", new_callable=AsyncMock)
    async def test_generate_site_map(self, mock_gen):
        mock_gen.return_value = "Site logistics report content"
        result = await generate_site_map(51.5, -0.1)
        assert "report" in result
        assert "links" in result
        assert result["report"] == "Site logistics report content"

    @pytest.mark.asyncio
    @patch("Zweather.ai_client._generate_text", new_callable=AsyncMock)
    async def test_generate_site_map_error_fallback(self, mock_gen):
        mock_gen.side_effect = RuntimeError("Ollama down")
        result = await generate_site_map(51.5, -0.1)
        # generate_site_map catches RuntimeError internally
        assert "report" in result
        assert "Failed" in result["report"]
        assert result["links"] == []
