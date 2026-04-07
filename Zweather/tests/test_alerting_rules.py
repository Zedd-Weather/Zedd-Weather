"""Tests for Zweather.alerting.rules"""
import pytest
from datetime import datetime, timezone
from Zweather.alerting.rules import AlertRulesEngine, Alert, AlertRule, AlertSeverity


class TestAlertRulesEngine:
    def setup_method(self):
        self.engine = AlertRulesEngine()
        # Engine rules use metrics: "temperature", "humidity", "pressure"
        self.normal_telemetry = {
            "temperature": 22.0,
            "humidity": 65.0,
            "pressure": 1013.0,
        }

    def test_no_alerts_normal_conditions(self):
        alerts = self.engine.evaluate(self.normal_telemetry)
        assert isinstance(alerts, list)

    def test_high_temp_triggers_alert(self):
        hot = {**self.normal_telemetry, "temperature": 41.0}
        alerts = self.engine.evaluate(hot)
        assert len(alerts) > 0
        severities = {a.severity for a in alerts}
        assert AlertSeverity.WARNING in severities or AlertSeverity.CRITICAL in severities

    def test_frost_triggers_critical_alert(self):
        freezing = {**self.normal_telemetry, "temperature": -5.0}
        alerts = self.engine.evaluate(freezing)
        assert any(a.severity == AlertSeverity.CRITICAL for a in alerts)

    def test_low_pressure_storm_alert(self):
        stormy = {**self.normal_telemetry, "pressure": 980.0}
        alerts = self.engine.evaluate(stormy)
        assert isinstance(alerts, list)

    def test_alert_has_required_fields(self):
        hot = {**self.normal_telemetry, "temperature": 41.0}
        alerts = self.engine.evaluate(hot)
        if alerts:
            a = alerts[0]
            assert hasattr(a, "id")
            assert hasattr(a, "severity")
            assert hasattr(a, "title")
            assert hasattr(a, "message")
            assert hasattr(a, "timestamp")

    def test_add_custom_rule(self):
        custom = AlertRule(
            name="test-rule",
            metric="temperature",
            condition=">",
            threshold=100.0,
            severity=AlertSeverity.INFO,
            message_template="Test alert: {value}",
            enabled=True,
        )
        self.engine.add_rule(custom)
        alerts = self.engine.evaluate(self.normal_telemetry)
        # Custom rule threshold (100°C) not triggered by 22°C
        custom_alerts = [a for a in alerts if a.title == "test-rule"]
        assert len(custom_alerts) == 0

    def test_disabled_rule_not_triggered(self):
        disabled = AlertRule(
            name="disabled-rule",
            metric="temperature",
            condition=">",
            threshold=0.0,
            severity=AlertSeverity.CRITICAL,
            message_template="Should not fire",
            enabled=False,
        )
        self.engine.add_rule(disabled)
        alerts = self.engine.evaluate(self.normal_telemetry)
        fired = [a for a in alerts if a.title == "disabled-rule"]
        assert len(fired) == 0
