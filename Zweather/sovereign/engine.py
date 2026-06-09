"""Validation engine for sovereign RMPE-2 weather transitions."""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from .protocol import (
    MAX_DEPTH,
    PHASE_ORDER,
    PROOF_BYTES_PER_DEPTH,
    ComposeTransitionRequest,
    PeerBlockHeader,
    RecursiveLayer,
    RecursiveMerkleProof,
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
            rmp_proof=request.rmp_proof,
            rnpe_exchange=request.rnpe_exchange,
        )

    def validate_transition(self, transition: WeatherTransition) -> ValidationResult:
        traces: list[ValidationTrace] = []
        previous = transition.previous_state
        next_state = transition.next_state

        traces.extend(self._validate_core_state(previous, next_state))
        traces.extend(self._validate_recursive_layers(transition))
        network_traces = self._validate_network_state(transition)
        traces.extend(network_traces)

        recursive_calls = len(transition.active_layers)
        remaining_depth = max(next_state.depth_limit - recursive_calls, 0)
        return ValidationResult(
            valid=all(trace.valid for trace in traces),
            traces=traces,
            recursive_calls=recursive_calls,
            remaining_depth=remaining_depth,
            network_verified=bool(network_traces) and all(trace.valid for trace in network_traces),
            compatibility_mode=True,
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
        has_timestamp_increased = next_state.weather_timestamp > previous.weather_timestamp
        has_usage_increased = next_state.usage_counter > previous.usage_counter
        is_sequence_linear = next_state.sequence == previous.sequence + 1
        is_phase_linear = self._phase_index(next_state.phase) == self._phase_index(previous.phase) + 1

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
                    valid=has_timestamp_increased,
                    message="Weather timestamp must strictly increase over PREVSTATE",
                ),
                ValidationTrace(
                    layer="prevstate",
                    valid=has_usage_increased,
                    message="Usage counter must strictly increase to prevent oracle overuse",
                ),
                ValidationTrace(
                    layer="prevstate",
                    valid=is_sequence_linear,
                    message="Sequence must advance one step at a time",
                ),
                ValidationTrace(
                    layer="prevstate",
                    valid=is_phase_linear,
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
                    valid=proof.proof_bytes <= next_state.depth_limit * PROOF_BYTES_PER_DEPTH,
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

    def _validate_network_state(self, transition: WeatherTransition) -> list[ValidationTrace]:
        traces: list[ValidationTrace] = []

        if transition.rmp_proof is not None:
            traces.extend(self._validate_rmp(transition.rmp_proof))

        if transition.rnpe_exchange is None:
            return traces

        exchange = transition.rnpe_exchange
        rmp_proof = exchange.recursive_proof
        traces.extend(self._validate_rmp(rmp_proof))

        if exchange.missing_blocks:
            first_block = exchange.missing_blocks[0]
            last_block = exchange.missing_blocks[-1]
            links_from_local_tip = (
                first_block.height == exchange.local_tip_height + 1
                and first_block.previous_hash == exchange.local_tip_hash
            )
            reaches_consensus_tip = (
                last_block.height == exchange.consensus_tip_height
                and last_block.block_hash == exchange.consensus_tip_hash
            )
            final_state_matches_rmp = last_block.state_root == rmp_proof.merkle_root
        else:
            links_from_local_tip = True
            reaches_consensus_tip = (
                exchange.local_tip_height == exchange.consensus_tip_height
                and exchange.local_tip_hash == exchange.consensus_tip_hash
            )
            final_state_matches_rmp = rmp_proof.merkle_root == transition.next_state.oracle_root

        traces.extend(
            [
                ValidationTrace(
                    layer="rnpe",
                    valid=links_from_local_tip,
                    message="RNPE-2 missing block range must start from the local tip",
                ),
                ValidationTrace(
                    layer="rnpe",
                    valid=self._missing_blocks_are_contiguous(exchange.missing_blocks),
                    message="RNPE-2 missing blocks must be height-contiguous and hash-linked",
                ),
                ValidationTrace(
                    layer="rnpe",
                    valid=reaches_consensus_tip,
                    message="RNPE-2 exchange must reconcile to the advertised consensus tip",
                ),
                ValidationTrace(
                    layer="rnpe",
                    valid=final_state_matches_rmp,
                    message="RNPE-2 consensus state root must match the recursive Merkle proof",
                ),
            ]
        )
        return traces

    def _validate_rmp(self, proof: RecursiveMerkleProof) -> list[ValidationTrace]:
        computed_root = proof.leaf_hash
        for step in proof.path:
            if step.side == "left":
                computed_root = self._hash_pair(step.sibling_hash, computed_root)
            else:
                computed_root = self._hash_pair(computed_root, step.sibling_hash)
        path_byte_lengths = (
            len(step.sibling_hash.encode("utf-8")) + len(step.side.encode("utf-8")) + 2
            for step in proof.path
        )
        effective_depth = max(len(proof.path), 1)
        serialized_minimum = len(proof.leaf_hash.encode("utf-8")) + 1 + sum(path_byte_lengths)

        return [
            ValidationTrace(
                layer="rmp",
                valid=len(proof.path) <= MAX_DEPTH,
                message="RMP path depth must fit inside the recursive proof limit",
            ),
            ValidationTrace(
                layer="rmp",
                valid=proof.proof_bytes >= serialized_minimum,
                message="RMP proof bytes must cover the serialized leaf and path",
            ),
            ValidationTrace(
                layer="rmp",
                valid=proof.proof_bytes <= effective_depth * PROOF_BYTES_PER_DEPTH,
                message="RMP compressed proof must fit inside the bounded proof budget",
            ),
            ValidationTrace(
                layer="rmp",
                valid=computed_root == proof.merkle_root,
                message="RMP leaf and compressed path must recompute the advertised Merkle root",
            ),
        ]

    @staticmethod
    def _missing_blocks_are_contiguous(blocks: list[PeerBlockHeader]) -> bool:
        for previous, current in zip(blocks, blocks[1:]):
            if current.height != previous.height + 1:
                return False
            if current.previous_hash != previous.block_hash:
                return False
        return True

    def _next_phase(self, previous: Optional[WeatherCoinState]) -> TransitionPhase:
        if previous is None:
            return TransitionPhase.DATA_ENTRY
        if previous.phase == TransitionPhase.SETTLEMENT:
            raise ValueError(
                "Cannot advance beyond settlement phase. Create a new root weather coin "
                "with compose_transition and no previous_state."
            )
        next_index = self._phase_index(previous.phase) + 1
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
        if comparator == "eq":
            return observed_value == threshold
        logging.getLogger(__name__).warning(
            "Unknown policy comparator '%s' — falling back to eq", comparator,
        )
        return observed_value == threshold

    @staticmethod
    def _hash_pair(left_hash: str, right_hash: str) -> str:
        return hashlib.sha256(f"{left_hash}:{right_hash}".encode("utf-8")).hexdigest()
