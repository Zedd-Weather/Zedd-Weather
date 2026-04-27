"""Tests for the sovereign RMPE-2 weather protocol layer."""

from fastapi.testclient import TestClient

from Zweather.api import app
from Zweather.sovereign import (
    ComposeTransitionRequest,
    PROTOCOL_TAG,
    RecursiveLayer,
    SovereignWeatherEngine,
    TransitionPhase,
    ValidationProof,
    WeatherObservation,
)

client = TestClient(app)


def _observation(
    timestamp: int,
    station_id: str = "station-001",
    temperature_c: float = 36.5,
) -> WeatherObservation:
    return WeatherObservation(
        station_id=station_id,
        timestamp=timestamp,
        temperature_c=temperature_c,
        humidity_pct=42.0,
        pressure_hpa=1008.0,
        wind_speed_ms=9.5,
        rainfall_mm=0.0,
        alert_code="EXTREME_HEAT",
    )


def _proof(layer: RecursiveLayer) -> ValidationProof:
    return ValidationProof(
        layer=layer,
        oracle_leaf=f"{layer.value}:leaf",
        membership_verified=True,
        proof_bytes=128,
        condition=f"{layer.value} membership verified",
    )


class TestSovereignWeatherEngine:
    def setup_method(self):
        self.engine = SovereignWeatherEngine()

    def test_compose_root_transition(self):
        transition = self.engine.compose_transition(
            ComposeTransitionRequest(
                oracle_root="oracle-root-1",
                observation=_observation(1_710_000_000),
                active_layers=[RecursiveLayer.STATION_IDENTITY],
                proofs=[_proof(RecursiveLayer.STATION_IDENTITY)],
            )
        )

        result = self.engine.validate_transition(transition)

        assert transition.next_state.protocol_tag == PROTOCOL_TAG
        assert transition.next_state.phase == TransitionPhase.DATA_ENTRY
        assert transition.next_state.sequence == 0
        assert transition.next_state.usage_counter == 1
        assert result.valid is True
        assert result.remaining_depth == 7

    def test_prevstate_transition_must_advance_linearly(self):
        root = self.engine.compose_transition(
            ComposeTransitionRequest(
                oracle_root="oracle-root-1",
                observation=_observation(1_710_000_000),
            )
        )
        transition = self.engine.compose_transition(
            ComposeTransitionRequest(
                oracle_root="oracle-root-1",
                previous_state=root.next_state,
                observation=_observation(1_710_000_300),
            )
        )

        result = self.engine.validate_transition(transition)

        assert transition.next_state.phase == TransitionPhase.CONSENSUS
        assert transition.next_state.sequence == 1
        assert result.valid is True

    def test_compose_handles_extreme_cold_payload(self):
        transition = self.engine.compose_transition(
            ComposeTransitionRequest(
                oracle_root="oracle-root-1",
                observation=_observation(1_710_000_000, temperature_c=-12.5),
            )
        )

        result = self.engine.validate_transition(transition)

        assert transition.next_state.observation.temperature_c == -12.5
        assert result.valid is True

    def test_prevstate_rejects_non_monotonic_timestamp(self):
        root = self.engine.compose_transition(
            ComposeTransitionRequest(
                oracle_root="oracle-root-1",
                observation=_observation(1_710_000_000),
            )
        )
        transition = self.engine.compose_transition(
            ComposeTransitionRequest(
                oracle_root="oracle-root-1",
                previous_state=root.next_state,
                observation=_observation(1_710_000_000),
            )
        )

        result = self.engine.validate_transition(transition)

        assert result.valid is False
        invalid_traces = [trace for trace in result.traces if not trace.valid]
        assert len(invalid_traces) == 1
        assert invalid_traces[0].layer == "prevstate"

    def test_settlement_layer_requires_policy_and_settlement_claim(self):
        transition = self.engine.compose_transition(
            ComposeTransitionRequest(
                oracle_root="oracle-root-1",
                observation=_observation(1_710_000_000),
                active_layers=[RecursiveLayer.SETTLEMENT],
                proofs=[_proof(RecursiveLayer.SETTLEMENT)],
            )
        )

        result = self.engine.validate_transition(transition)

        assert result.valid is False
        assert any(trace.layer == "settlement" and trace.valid is False for trace in result.traces)


class TestSovereignProtocolAPI:
    def test_protocol_descriptor_endpoint(self):
        response = client.get("/api/sovereign/protocol")

        assert response.status_code == 200
        data = response.json()
        assert data["protocol_tag"] == PROTOCOL_TAG
        assert data["compatibility_tooling"] is True
        assert "/api/telemetry/ingest" in data["compatibility_endpoints"]

    def test_compose_endpoint_returns_transition_and_validation(self):
        response = client.post(
            "/api/sovereign/compose",
            json={
                "oracle_root": "oracle-root-1",
                "observation": {
                    "station_id": "station-001",
                    "timestamp": 1710000000,
                    "temperature_c": 36.5,
                    "humidity_pct": 42.0,
                    "pressure_hpa": 1008.0,
                },
                "active_layers": ["station_identity"],
                "proofs": [
                    {
                        "layer": "station_identity",
                        "oracle_leaf": "station_identity:leaf",
                        "membership_verified": True,
                        "proof_bytes": 128,
                        "condition": "station identity proof verified",
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["transition"]["next_state"]["protocol_tag"] == PROTOCOL_TAG
        assert data["validation"]["valid"] is True

    def test_validate_endpoint_reports_missing_proof(self):
        response = client.post(
            "/api/sovereign/validate",
            json={
                "next_state": {
                    "protocol_tag": PROTOCOL_TAG,
                    "oracle_root": "oracle-root-1",
                    "depth_limit": 8,
                    "usage_counter": 1,
                    "weather_timestamp": 1710000000,
                    "phase": "data_entry",
                    "sequence": 0,
                    "station_id": "station-001",
                    "observation": {
                        "station_id": "station-001",
                        "timestamp": 1710000000,
                        "temperature_c": 36.5,
                        "humidity_pct": 42.0,
                        "pressure_hpa": 1008.0,
                    },
                    "geofence": {
                        "region_id": "sf-bay",
                        "latitude": 37.7749,
                        "longitude": -122.4194,
                        "radius_km": 10.0,
                    },
                },
                "active_layers": ["geo_fencing"],
                "proofs": [],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        invalid_traces = [trace for trace in data["traces"] if not trace["valid"]]
        assert invalid_traces
        assert any("ASSERT PROOF" in trace["message"] for trace in invalid_traces)
