"""
Abstract base class that every sensor driver must implement.
"""
from abc import ABC, abstractmethod
import logging


class BaseSensor(ABC):
    """Uniform interface for all Zedd Weather sensor drivers."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"sensor.{name}")
        self._available = False

    @property
    def available(self) -> bool:
        """Return *True* if the physical hardware was detected."""
        return self._available

    @abstractmethod
    def initialize(self) -> None:
        """Perform one-time hardware initialisation.

        Implementations should set ``self._available = True`` on success
        and fall back to mock mode on failure (logging a warning).
        """

    @abstractmethod
    def read(self) -> dict:
        """Return a dict of the latest sensor readings.

        Keys and units should be documented in each concrete driver.
        """

    def cleanup(self) -> None:
        """Release hardware resources (optional override)."""
