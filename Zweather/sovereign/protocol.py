"""Protocol models for the RMPE-2 sovereign weather state machine."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

PROTOCOL_TAG = "RMPE2-WEATHER"
MAX_DEPTH = 8
MAX_PROOF_SIZE = 2048
PROOF_BYTES_PER_DEPTH = 256
RNPE_VERSION = "RNPE-2"
PHASE_ORDER = ("data_entry", "consensus", "distribution", "settlement")


class TransitionPhase(str, Enum):
    DATA_ENTRY = "data_entry"
    CONSENSUS = "consensus"
    DISTRIBUTION = "distribution"
    SETTLEMENT = "settlement"


class RecursiveLayer(str, Enum):
    STATION_IDENTITY = "station_identity"
    GEO_FENCING = "geo_fencing"
    POLICY = "policy"
    SETTLEMENT = "settlement"


class ValidationProof(BaseModel):
    """Cryptographic membership proof metadata supplied at validation time."""

    layer: RecursiveLayer
    oracle_leaf: str = Field(..., min_length=1, description="Committed leaf or leaf hash proven under the oracle root")
    membership_verified: bool = Field(..., description="True when the caller has verified the proof before branch evaluation")
    proof_bytes: int = Field(..., ge=1, le=MAX_PROOF_SIZE, description="Serialized proof size in bytes")
    condition: str = Field(..., min_length=1, description="Human-readable branch condition guarded by this proof")


class RecursiveMerkleStep(BaseModel):
    """One compressed sibling step in an RMP membership path."""

    sibling_hash: str = Field(..., min_length=1)
    side: Literal["left", "right"] = Field(
        ...,
        description="Side of the sibling hash relative to the rolling proof hash",
    )


class RecursiveMerkleProof(BaseModel):
    """Compressed RMP proof for validating the current network state."""

    leaf_hash: str = Field(..., min_length=1)
    merkle_root: str = Field(..., min_length=1)
    path: list[RecursiveMerkleStep] = Field(default_factory=list, max_length=MAX_DEPTH)
    proof_bytes: int = Field(..., ge=1, le=MAX_PROOF_SIZE)
    state_reference: str = Field(..., min_length=1)


class PeerBlockHeader(BaseModel):
    """Minimal block header exchanged through RNPE-2 for gap recovery."""

    height: int = Field(..., ge=0)
    block_hash: str = Field(..., min_length=1)
    previous_hash: str = Field(..., min_length=1)
    state_root: str = Field(..., min_length=1)


class RNPEExchange(BaseModel):
    """Recursive Network Peer Exchange payload for consensus catch-up."""

    version: str = Field(default=RNPE_VERSION, min_length=1)
    peer_id: str = Field(..., min_length=1)
    local_tip_height: int = Field(..., ge=0)
    local_tip_hash: str = Field(..., min_length=1)
    consensus_tip_height: int = Field(..., ge=0)
    consensus_tip_hash: str = Field(..., min_length=1)
    missing_blocks: list[PeerBlockHeader] = Field(default_factory=list)
    recursive_proof: RecursiveMerkleProof


class WeatherObservation(BaseModel):
    """Weather data revealed at validation time and carried by the weather coin."""

    station_id: str = Field(..., min_length=1)
    timestamp: int = Field(..., ge=0, description="Unix timestamp carried by the weather coin")
    temperature_c: float
    humidity_pct: float = Field(..., ge=0.0, le=100.0)
    pressure_hpa: float = Field(..., gt=0.0)
    wind_speed_ms: Optional[float] = Field(None, ge=0.0)
    rainfall_mm: Optional[float] = Field(None, ge=0.0)
    alert_code: Optional[str] = None


class GeoFenceClaim(BaseModel):
    """Geographic scope validated by a recursive branch."""

    region_id: str = Field(..., min_length=1)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    radius_km: float = Field(..., gt=0.0)


class PolicyClaim(BaseModel):
    """Policy condition validated by a recursive branch."""

    policy_id: str = Field(..., min_length=1)
    metric: str = Field(..., min_length=1)
    threshold: float
    observed_value: float
    comparator: Literal["gt", "gte", "lt", "lte", "eq"] = "gte"
    requires_settlement: bool = False


class SettlementClaim(BaseModel):
    """Tokenized settlement payload triggered by policy evaluation."""

    settlement_id: str = Field(..., min_length=1)
    asset: str = Field("WEATHER-TOKEN", min_length=1)
    amount: float = Field(..., ge=0.0)
    recipient: str = Field(..., min_length=1)


class WeatherCoinState(BaseModel):
    """Canonical state carried by an RMPE-2 weather coin."""

    protocol_tag: Literal["RMPE2-WEATHER"] = "RMPE2-WEATHER"
    oracle_root: str = Field(..., min_length=1)
    depth_limit: int = Field(MAX_DEPTH, ge=0, le=MAX_DEPTH)
    usage_counter: int = Field(0, ge=0)
    weather_timestamp: int = Field(..., ge=0)
    phase: TransitionPhase = TransitionPhase.DATA_ENTRY
    sequence: int = Field(0, ge=0)
    station_id: str = Field(..., min_length=1)
    observation: WeatherObservation
    geofence: Optional[GeoFenceClaim] = None
    policy: Optional[PolicyClaim] = None
    settlement: Optional[SettlementClaim] = None

    @model_validator(mode="after")
    def align_embedded_observation(self) -> "WeatherCoinState":
        if self.station_id != self.observation.station_id:
            raise ValueError("station_id must match observation.station_id")
        if self.weather_timestamp != self.observation.timestamp:
            raise ValueError("weather_timestamp must match observation.timestamp")
        if self.policy and self.policy.requires_settlement and not self.settlement:
            raise ValueError("settlement is required when policy.requires_settlement is true")
        return self


class ComposeTransitionRequest(BaseModel):
    """Operator-tooling request for composing a transition from raw claims."""

    oracle_root: str = Field(..., min_length=1)
    observation: WeatherObservation
    proofs: list[ValidationProof] = Field(default_factory=list)
    previous_state: Optional[WeatherCoinState] = None
    phase: Optional[TransitionPhase] = None
    depth_limit: int = Field(MAX_DEPTH, ge=0, le=MAX_DEPTH)
    geofence: Optional[GeoFenceClaim] = None
    policy: Optional[PolicyClaim] = None
    settlement: Optional[SettlementClaim] = None
    usage_increment: int = Field(1, ge=1)
    active_layers: list[RecursiveLayer] = Field(default_factory=list)
    rmp_proof: Optional[RecursiveMerkleProof] = None
    rnpe_exchange: Optional[RNPEExchange] = None


class WeatherTransition(BaseModel):
    """State transition validated from PREVSTATE plus branch proofs alone."""

    previous_state: Optional[WeatherCoinState] = None
    next_state: WeatherCoinState
    proofs: list[ValidationProof] = Field(default_factory=list)
    active_layers: list[RecursiveLayer] = Field(default_factory=list)
    rmp_proof: Optional[RecursiveMerkleProof] = None
    rnpe_exchange: Optional[RNPEExchange] = None


class ValidationTrace(BaseModel):
    layer: str
    valid: bool
    message: str


class ValidationResult(BaseModel):
    """Validation outcome for a weather coin transition."""

    valid: bool
    protocol_tag: Literal["RMPE2-WEATHER"] = "RMPE2-WEATHER"
    traces: list[ValidationTrace]
    recursive_calls: int = Field(..., ge=0)
    remaining_depth: int = Field(..., ge=0, le=MAX_DEPTH)
    network_verified: bool = Field(False, description="True when RMP/RNPE-2 consensus checks passed")
    compatibility_mode: bool = Field(
        True,
        description="True when the result is emitted by HTTP tooling instead of a chain-native Minima validator",
    )
