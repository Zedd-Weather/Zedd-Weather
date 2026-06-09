"""
Zedd Weather — Residential Intelligence

Heuristic engine for residential property weather risk assessment
with UK regional climate profiles.
"""
from .engine import ResidentialEngine
from .models import (
    PropertyProfile,
    PROPERTY_PROFILES,
    BuildingFabricAssessment,
    OccupantSafety,
    PropertyHazard,
    EnergyAssessment,
    PropertyType,
    ConstructionEra,
    HeatingType,
)

__all__ = [
    "ResidentialEngine",
    "PropertyProfile",
    "PROPERTY_PROFILES",
    "BuildingFabricAssessment",
    "OccupantSafety",
    "PropertyHazard",
    "EnergyAssessment",
    "PropertyType",
    "ConstructionEra",
    "HeatingType",
]
