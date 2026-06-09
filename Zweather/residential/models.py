"""
Residential data models for Zedd Weather.
Property profiles, occupant vulnerability, and building fabric risk assessment.
Shared region types sourced from global_regions.
"""
from dataclasses import dataclass, field
from enum import Enum

from Zweather.global_regions.models import UKRegion, Season, RegionProfile


class PropertyType(Enum):
    DETACHED = "detached"
    SEMI_DETACHED = "semi_detached"
    TERRACED = "terraced"
    FLAT = "flat"
    BUNGALOW = "bungalow"
    MOBILE_HOME = "mobile_home"
    GENERAL = "general"


class ConstructionEra(Enum):
    PRE_1900 = "pre_1900"
    EDWARDIAN = "edwardian"
    INTERWAR = "interwar"
    POSTWAR = "postwar"
    MODERN = "modern"
    NEW_BUILD = "new_build"


class HeatingType(Enum):
    CENTRAL_HEATING = "central_heating"
    ELECTRIC = "electric"
    HEAT_PUMP = "heat_pump"
    DISTRICT_HEATING = "district_heating"
    SOLID_FUEL = "solid_fuel"
    NONE = "none"


@dataclass
class PropertyProfile:
    """Physical characteristics and vulnerability of a residential property."""
    name: str
    property_type: PropertyType
    era: ConstructionEra
    heating: HeatingType
    # Fabric sensitivity
    damp_sensitivity: float = 0.5        # 0-1: how susceptible to damp
    mould_sensitivity: float = 0.5        # 0-1: how susceptible to mould
    frost_pipe_risk: float = 0.5          # 0-1: risk of pipe freezing
    ventilation_adequacy: float = 0.5     # 0-1: ventilation quality
    insulation_quality: float = 0.5       # 0-1: insulation effectiveness
    # Occupant vulnerability modifiers
    elderly_occupants: bool = False
    young_children: bool = False
    respiratory_conditions: bool = False
    # Temperature comfort ranges
    comfort_temp_min: float = 18.0
    comfort_temp_max: float = 26.0
    emergency_temp_min: float = 12.0      # Below this = health risk
    emergency_temp_max: float = 35.0      # Above this = health risk
    # Constraints
    constraints: dict = field(default_factory=dict)


PROPERTY_PROFILES: dict[str, PropertyProfile] = {
    "victorian_terrace": PropertyProfile(
        name="Victorian Terrace",
        property_type=PropertyType.TERRACED,
        era=ConstructionEra.PRE_1900,
        heating=HeatingType.CENTRAL_HEATING,
        damp_sensitivity=0.7,
        mould_sensitivity=0.7,
        frost_pipe_risk=0.6,
        ventilation_adequacy=0.3,
        insulation_quality=0.2,
    ),
    "modern_detached": PropertyProfile(
        name="Modern Detached House",
        property_type=PropertyType.DETACHED,
        era=ConstructionEra.NEW_BUILD,
        heating=HeatingType.HEAT_PUMP,
        damp_sensitivity=0.2,
        mould_sensitivity=0.2,
        frost_pipe_risk=0.3,
        ventilation_adequacy=0.8,
        insulation_quality=0.9,
    ),
    "modern_flat": PropertyProfile(
        name="Modern Apartment",
        property_type=PropertyType.FLAT,
        era=ConstructionEra.NEW_BUILD,
        heating=HeatingType.DISTRICT_HEATING,
        damp_sensitivity=0.3,
        mould_sensitivity=0.3,
        frost_pipe_risk=0.2,
        ventilation_adequacy=0.6,
        insulation_quality=0.8,
    ),
    "postwar_semi": PropertyProfile(
        name="Post-War Semi-Detached",
        property_type=PropertyType.SEMI_DETACHED,
        era=ConstructionEra.POSTWAR,
        heating=HeatingType.CENTRAL_HEATING,
        damp_sensitivity=0.5,
        mould_sensitivity=0.5,
        frost_pipe_risk=0.5,
        ventilation_adequacy=0.4,
        insulation_quality=0.4,
    ),
    "interwar_bungalow": PropertyProfile(
        name="Interwar Bungalow",
        property_type=PropertyType.BUNGALOW,
        era=ConstructionEra.INTERWAR,
        heating=HeatingType.ELECTRIC,
        damp_sensitivity=0.4,
        mould_sensitivity=0.4,
        frost_pipe_risk=0.7,
        ventilation_adequacy=0.4,
        insulation_quality=0.3,
    ),
    "general": PropertyProfile(
        name="General Residential",
        property_type=PropertyType.GENERAL,
        era=ConstructionEra.MODERN,
        heating=HeatingType.CENTRAL_HEATING,
    ),
}


@dataclass
class BuildingFabricAssessment:
    """Assessment of building fabric risk from weather conditions."""
    damp_risk_index: float           # 0.0-1.0
    mould_risk_index: float          # 0.0-1.0
    condensation_risk: bool
    pipe_freeze_risk: bool
    insulation_effectiveness_pct: float
    ventilation_recommendations: list[str]


@dataclass
class OccupantSafety:
    """Occupant health and safety assessment from atmospheric data."""
    heat_stress_index: float         # 0.0-1.0
    cold_stress_index: float         # 0.0-1.0
    indoor_air_quality_concern: bool
    recommended_indoor_temp: float
    recommendations: list[str]


@dataclass
class PropertyHazard:
    """A single property-related hazard from weather conditions."""
    hazard: str
    risk_level: str
    condition: str
    recommendation: str
    affected_rooms: list[str] | None = None


@dataclass
class EnergyAssessment:
    """Energy and utility implications from weather conditions."""
    heating_demand_index: float      # 0.0-1.0 (higher = more heating needed)
    cooling_demand_index: float      # 0.0-1.0 (higher = more cooling needed)
    power_outage_risk: str           # "low", "medium", "high"
    estimated_daily_cost_pct: float  # % above normal
    recommendations: list[str]
