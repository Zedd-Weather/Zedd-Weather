"""
Tests for the Zedd Weather email reporter.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from Zweather.reporting.email_reporter import (
    EmailConfig,
    _build_report_html,
    _load_config_from_env,
    _risk_badge_html,
    send_report,
    send_sector_report,
)


class TestEmailReporterCore:
    def test_load_config_from_env_defaults(self):
        cfg = _load_config_from_env()
        assert cfg.smtp_host == "localhost"
        assert cfg.smtp_port == 587
        assert cfg.use_tls is True
        assert cfg.from_addr == "zedd-weather@localhost"
        assert cfg.to_addrs == []

    @patch.dict("os.environ", {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "465",
        "SMTP_USER": "user@example.com",
        "SMTP_PASSWORD": "secret",
        "SMTP_USE_TLS": "false",
        "SMTP_FROM": "noreply@zedd.weather",
        "SMTP_TO": "admin@example.com,ops@example.com",
    })
    def test_load_config_from_env_overrides(self):
        cfg = _load_config_from_env()
        assert cfg.smtp_host == "smtp.example.com"
        assert cfg.smtp_port == 465
        assert cfg.smtp_user == "user@example.com"
        assert cfg.smtp_password == "secret"
        assert cfg.use_tls is False
        assert cfg.from_addr == "noreply@zedd.weather"
        assert cfg.to_addrs == ["admin@example.com", "ops@example.com"]

    def test_risk_badge_low(self):
        html = _risk_badge_html("low")
        assert "badge-low" in html
        assert "low" in html

    def test_risk_badge_medium(self):
        html = _risk_badge_html("medium")
        assert "badge-medium" in html
        assert "medium" in html

    def test_risk_badge_high(self):
        html = _risk_badge_html("high")
        assert "badge-high" in html
        assert "high" in html

    def test_risk_badge_critical(self):
        html = _risk_badge_html("critical")
        assert "badge-critical" in html
        assert "critical" in html

    def test_risk_badge_unknown_falls_to_medium(self):
        html = _risk_badge_html("unknown")
        assert "badge-medium" in html
        assert "unknown" in html

    def test_risk_badge_none_falls_to_medium(self):
        html = _risk_badge_html(None)
        assert "badge-medium" in html

    def test_build_report_html_single_sector(self):
        results = {
            "construction": {
                "risk_level": "high",
                "region": "Glasgow",
                "recommendations": ["Wear PPE", "Monitor wind"],
                "temperature_c": 5.0,
                "wind_speed_ms": 15.0,
            }
        }
        html = _build_report_html(results, region="Glasgow")
        assert "Construction" in html
        assert "Glasgow" in html
        assert "high" in html
        assert "Wear PPE" in html
        assert "Zedd Weather Report" in html

    def test_build_report_html_all_sectors(self):
        sectors = ["construction", "agricultural", "industrial", "residential",
                    "marine", "aviation", "energy", "transportation"]
        results = {s: {"risk_level": "low", "recommendations": ["OK"], "region": "Midlands"} for s in sectors}
        html = _build_report_html(results)
        for s in sectors:
            assert s.title() in html
        assert "Midlands" in html

    def test_build_report_html_no_recommendations(self):
        results = {
            "marine": {
                "risk_level": "low",
                "region": "Belfast",
                "sea_state": "calm",
            }
        }
        html = _build_report_html(results, region="Belfast")
        assert "Marine" in html
        assert "Belfast" in html
        assert "sea_state" in html

    def test_build_report_html_empty(self):
        html = _build_report_html({})
        assert "Zedd Weather Report" in html

    def test_send_report_no_recipients(self):
        cfg = EmailConfig(to_addrs=[])
        result = send_report({"test": {"risk_level": "low", "region": "Midlands"}}, config=cfg)
        assert result is False

    @patch("smtplib.SMTP")
    def test_send_report_success(self, mock_smtp):
        mock_instance = mock_smtp.return_value.__enter__.return_value
        cfg = EmailConfig(
            smtp_host="localhost", smtp_port=587,
            smtp_user="user", smtp_password="pass",
            from_addr="test@test.com",
            to_addrs=["admin@test.com"],
        )
        result = send_report({"test": {"risk_level": "low", "region": "Midlands"}}, config=cfg)
        assert result is True
        mock_instance.sendmail.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_report_no_tls(self, mock_smtp):
        mock_instance = mock_smtp.return_value.__enter__.return_value
        cfg = EmailConfig(
            smtp_host="localhost", smtp_port=25, use_tls=False,
            from_addr="test@test.com",
            to_addrs=["admin@test.com"],
        )
        result = send_report({"test": {"risk_level": "low", "region": "Midlands"}}, config=cfg)
        assert result is True
        mock_instance.starttls.assert_not_called()

    @patch("smtplib.SMTP")
    def test_send_report_no_auth(self, mock_smtp):
        mock_instance = mock_smtp.return_value.__enter__.return_value
        cfg = EmailConfig(
            smtp_host="localhost", smtp_port=25, use_tls=False,
            from_addr="test@test.com",
            to_addrs=["admin@test.com"],
        )
        send_report({"test": {"risk_level": "low", "region": "Midlands"}}, config=cfg)
        mock_instance.login.assert_not_called()

    @patch("smtplib.SMTP")
    def test_send_report_smtp_error(self, mock_smtp):
        mock_instance = mock_smtp.return_value.__enter__.return_value
        mock_instance.sendmail.side_effect = ConnectionRefusedError("refused")
        cfg = EmailConfig(
            smtp_host="localhost", smtp_port=587,
            from_addr="test@test.com",
            to_addrs=["admin@test.com"],
        )
        result = send_report({"test": {"risk_level": "low", "region": "Midlands"}}, config=cfg)
        assert result is False

    def test_send_sector_report(self):
        analysis = {"risk_level": "medium", "region": "London"}
        with patch("Zweather.reporting.email_reporter.send_report") as mock_send:
            send_sector_report("construction", analysis)
            mock_send.assert_called_once()

    def test_email_config_defaults(self):
        cfg = EmailConfig()
        assert cfg.smtp_host == "localhost"
        assert cfg.smtp_port == 587
        assert cfg.smtp_user is None
        assert cfg.smtp_password is None
        assert cfg.from_addr == "zedd-weather@localhost"
        assert cfg.to_addrs == []

    def test_email_config_custom(self):
        cfg = EmailConfig(
            smtp_host="smtp.gmail.com",
            smtp_port=465,
            smtp_user="bot@gmail.com",
            smtp_password="app-password",
            use_tls=True,
            from_addr="bot@gmail.com",
            to_addrs=["user@gmail.com"],
        )
        assert cfg.smtp_host == "smtp.gmail.com"
        assert cfg.to_addrs == ["user@gmail.com"]
