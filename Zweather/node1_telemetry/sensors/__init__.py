"""
Sensor drivers for the Zedd Weather edge node.
Each driver provides a consistent ``read()`` → ``dict`` interface
with automatic mock fallback when the physical hardware is absent.
"""

from Zweather.node1_telemetry.sensors.sensor_manager import SensorManager

__all__ = ["SensorManager"]
