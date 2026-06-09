"""
Energy data models for Zedd Weather.
Energy asset profiles, grid stability, and renewable generation assessment.
"""
from dataclasses import dataclass, field
from enum import Enum


class EnergyAssetType(Enum):
    SOLAR_FARM = "solar_farm"
    WIND_FARM = "wind_farm"
    HYDRO_PLANT = "hydro_plant"
    GAS_PLANT = "gas_plant"
    BATTERY_STORAGE = "battery_storage"
    NUCLEAR_PLANT = "nuclear_plant"
    GENERAL = "general"


class EnergyMarket(Enum):
    DAY_AHEAD = "day_ahead"
    INTRADAY = "intraday"
    BALANCING = "balancing"
    GENERAL = "general"


@dataclass
class EnergyAssetProfile:
    name: str
    asset_type: EnergyAssetType
    capacity_mw: float = 100.0
    max_operational_wind_ms: float = 25.0
    max_survival_wind_ms: float = 40.0
    min_solar_irradiance_wm2: float = 200.0
    max_ambient_temp_c: float = 45.0
    min_ambient_temp_c: float = -20.0
    max_humidity_pct: float = 95.0
    derating_factor: float = 1.0
    constraints: dict = field(default_factory=dict)


ENERGY_ASSET_PROFILES: dict[str, EnergyAssetProfile] = {
    "solar_farm": EnergyAssetProfile(
        name="Solar PV Farm",
        asset_type=EnergyAssetType.SOLAR_FARM,
        capacity_mw=50.0,
        min_solar_irradiance_wm2=200.0,
        max_ambient_temp_c=45.0,
        derating_factor=0.85,
        constraints={"snow_derate": 0.3, "soiling_derate": 0.05},
    ),
    "wind_farm": EnergyAssetProfile(
        name="Onshore Wind Farm",
        asset_type=EnergyAssetType.WIND_FARM,
        capacity_mw=100.0,
        max_operational_wind_ms=25.0,
        max_survival_wind_ms=40.0,
        min_ambient_temp_c=-20.0,
        derating_factor=0.95,
        constraints={"cut_in_wind_ms": 3.0, "cut_out_wind_ms": 25.0, "optimal_wind_ms": 12.0},
    ),
    "hydro_plant": EnergyAssetProfile(
        name="Hydroelectric Plant",
        asset_type=EnergyAssetType.HYDRO_PLANT,
        capacity_mw=200.0,
        max_ambient_temp_c=40.0,
        constraints={"min_flow_rate": 10.0, "flood_risk_precip_mm": 100.0},
    ),
    "gas_plant": EnergyAssetProfile(
        name="Gas Turbine Plant",
        asset_type=EnergyAssetType.GAS_PLANT,
        capacity_mw=300.0,
        max_ambient_temp_c=40.0,
        derating_factor=0.9,
        constraints={"max_temp_derate_c": 35.0, "min_temp_boost_c": 5.0},
    ),
    "battery_storage": EnergyAssetProfile(
        name="Battery Energy Storage",
        asset_type=EnergyAssetType.BATTERY_STORAGE,
        capacity_mw=50.0,
        max_ambient_temp_c=40.0,
        min_ambient_temp_c=-10.0,
        constraints={"optimal_temp_c": 25.0, "derate_high_temp_c": 35.0},
    ),
    "general": EnergyAssetProfile(
        name="General Energy Asset",
        asset_type=EnergyAssetType.GENERAL,
    ),
}


@dataclass
class GridStabilityAssessment:
    risk_level: str
    demand_pressure: str
    renewable_contribution_pct: float
    volatility_risk: str
    recommendation: str


@dataclass
class GenerationForecast:
    asset_type: EnergyAssetType
    estimated_output_mw: float
    capacity_factor_pct: float
    limiting_factors: list[str]
    recommendation: str


@dataclass
class EnergyHazard:
    hazard: str
    risk_level: str
    condition: str
    affected_capacity_mw: float
    recommendation: str
