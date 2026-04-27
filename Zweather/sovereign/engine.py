"""Validation engine for sovereign RMPE-2 weather transitions."""

from __future__ import annotations

from typing import Optional

from .protocol import (
    MAX_DEPTH,
    PHASE_ORDER,
    ComposeTransitionRequest,
    RecursiveLayer,
    TransitionPhase,
    ValidationResult,
    ValidationTrace,
    WeatherCoinState,
    WeatherTransition,
)


class SovereignWeatherEngine:
    """Compose and validate deterministic RMPE-2 weather coin transitions."""

    def compose_transition(self, request: ComposeTransitionRequest) -> WeatherTransition:
        previous = request.previous_state
        phase = request.phase or self._next_phase(previous)
        next_state = WeatherCoinState(
            oracle_root=request.oracle_root,
            depth_limit=request.depth_limit,
            usage_counter=(previous.usage_counter if previous else 0) + request.usage_increment,
            weather_timestamp=request.observation.timestamp,
            phase=phase,
            sequence=(previous.sequence + 1) if previous else 0,
            station_id=request.observation.station_id,
            observation=request.observation,
            geofence=request.geofence,
            policy=request.policy,
            settlement=request.settlement,
        )
        return WeatherTransition(
            previous_state=previous,
            next_state=next_state,
            proofs=request.proofs,
            active_layers=request.active_layers,
        )

    def validate_transition(self, transition: WeatherTransition) -> ValidationResult:
        traces: list[ValidationTrace] = []
        previous = transition.previous_state
        next_state = transition.next_state

        traces.extend(self._validate_core_state(previous, next_state))
        traces.extend(self._validate_recursive_layers(transition))

        recursive_calls = len(transition.active_layers)
        remaining_depth = max(next_state.depth_limit - recursive_calls, 0)
        return ValidationResult(
            valid=all(trace.valid for trace in traces),
            traces=traces,
            recursive_calls=recursive_calls,
            remaining_depth=remaining_depth,
        )

    def _validate_core_state(
        self,
        previous: Optional[WeatherCoinState],
        next_state: WeatherCoinState,
    ) -> list[ValidationTrace]:
        traces = [
            ValidationTrace(
                layer="core",
                valid=next_state.depth_limit <= MAX_DEPTH,
                message=f"Depth limit {next_state.depth_limit} is within Minima maximum {MAX_DEPTH}",
            )
        ]

        if previous is None:
            traces.append(
                ValidationTrace(
                    layer="prevstate",
                    valid=next_state.phase == TransitionPhase.DATA_ENTRY and next_state.sequence == 0,
                    message="Root issuance must start at data_entry with sequence 0",
                )
            )
            return traces

        same_station = previous.station_id == next_state.station_id
        same_root = previous.oracle_root == next_state.oracle_root
        timestamp_increases = next_state.weather_timestamp > previous.weather_timestamp
        usage_increases = next_state.usage_counter > previous.usage_counter
        sequence_linear = next_state.sequence == previous.sequence + 1
        phase_linear = self._phase_index(next_state.phase) == self._phase_index(previous.phase) + 1

        traces.extend(
            [
                ValidationTrace(
                    layer="prevstate",
                    valid=same_station,
                    message="Station identity must remain stable across PREVSTATE transitions",
                ),
                ValidationTrace(
                    layer="prevstate",
                    valid=same_root,
                    message="Oracle root must remain stable for a deterministic transition path",
                ),
                ValidationTrace(
                    layer="prevstate",
                    valid=timestamp_increases,
                    message="Weather timestamp must strictly increase over PREVSTATE",
                ),
                ValidationTrace(
                    layer="prevstate",
                    valid=usage_increases,
                    message="Usage counter must strictly increase to prevent oracle overuse",
                ),
                ValidationTrace(
                    layer="prevstate",
                    valid=sequence_linear,
                    message="Sequence must advance one step at a time",
                ),
                ValidationTrace(
                    layer="prevstate",
                    valid=phase_linear,
                    message="Phase progression must be linear and unskippable",
                ),
            ]
        )
        return traces

    def _validate_recursive_layers(self, transition: WeatherTransition) -> list[ValidationTrace]:
        next_state = transition.next_state
        proofs_by_layer = {proof.layer: proof for proof in transition.proofs}
        traces: list[ValidationTrace] = []

        if len(transition.active_layers) > next_state.depth_limit:
            traces.append(
                ValidationTrace(
                    layer="proofs",
                    valid=False,
                    message="Recursive call count exceeds configured depth limit",
                )
            )

        for layer in transition.active_layers:
            proof = proofs_by_layer.get(layer)
            traces.append(
                ValidationTrace(
                    layer="proofs",
                    valid=proof is not None,
                    message=f"ASSERT PROOF must precede {layer.value} branch evaluation",
                )
            )
            if proof is None:
                continue
            traces.append(
                ValidationTrace(
                    layer=layer.value,
                    valid=proof.membership_verified,
                    message=f"{layer.value} proof membership must verify before evaluation",
                )
            )
            traces.append(
                ValidationTrace(
                    layer=layer.value,
                    valid=proof.proof_bytes <= next_state.depth_limit * 256,
                    message=f"{layer.value} proof must fit inside the bounded proof budget",
                )
            )

        traces.extend(self._validate_layer_claims(transition))
        return traces

    def _validate_layer_claims(self, transition: WeatherTransition) -> list[ValidationTrace]:
        next_state = transition.next_state
        active = set(transition.active_layers)
        traces: list[ValidationTrace] = []

        traces.append(
            ValidationTrace(
                layer=RecursiveLayer.STATION_IDENTITY.value,
                valid=(RecursiveLayer.STATION_IDENTITY not in active) or bool(next_state.station_id),
                message="Station identity layer requires a non-empty station_id",
            )
        )
        traces.append(
            ValidationTrace(
                layer=RecursiveLayer.GEO_FENCING.value,
                valid=(RecursiveLayer.GEO_FENCING not in active) or next_state.geofence is not None,
                message="Geo-fencing layer requires a geofence claim",
            )
        )

        policy_valid = True
        if RecursiveLayer.POLICY in active:
            policy_valid = next_state.policy is not None and self._compare_policy(
                next_state.policy.comparator,
                next_state.policy.observed_value,
                next_state.policy.threshold,
            )
        traces.append(
            ValidationTrace(
                layer=RecursiveLayer.POLICY.value,
                valid=policy_valid,
                message="Policy layer requires a policy claim whose comparator evaluates true",
            )
        )

        settlement_valid = True
        if RecursiveLayer.SETTLEMENT in active:
            settlement_valid = (
                next_state.settlement is not None
                and next_state.policy is not None
                and next_state.policy.requires_settlement
            )
        traces.append(
            ValidationTrace(
                layer=RecursiveLayer.SETTLEMENT.value,
                valid=settlement_valid,
                message="Settlement layer requires both a triggering policy and a settlement claim",
            )
        )
        return traces

    def _next_phase(self, previous: Optional[WeatherCoinState]) -> TransitionPhase:
        if previous is None:
            return TransitionPhase.DATA_ENTRY
        if previous.phase == TransitionPhase.SETTLEMENT:
            raise ValueError("Cannot advance beyond settlement; issue a new root weather coin")
        next_index = min(self._phase_index(previous.phase) + 1, len(PHASE_ORDER) - 1)
        return TransitionPhase(PHASE_ORDER[next_index])

    @staticmethod
    def _phase_index(phase: TransitionPhase) -> int:
        return PHASE_ORDER.index(phase.value)

    @staticmethod
    def _compare_policy(comparator: str, observed_value: float, threshold: float) -> bool:
        if comparator == "gt":
            return observed_value > threshold
        if comparator == "gte":
            return observed_value >= threshold
        if comparator == "lt":
            return observed_value < threshold
        if comparator == "lte":
            return observed_value <= threshold
        return observed_value == threshold
