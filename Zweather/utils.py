"""
Shared utility functions for Zedd Weather.

Provides common formulas used across multiple engines to avoid duplication:
heat index, wind chill, and other shared calculations.
"""

def compute_heat_index(temp: float, humidity: float) -> float:
    """
    Simplified heat index (°C) from temperature and relative humidity.

    Uses the Rothfusz regression adapted to Celsius.
    Returns the raw temperature when below the heat-index threshold.
    """
    if temp < 27.0 or humidity < 40.0:
        return temp

    t = temp
    r = humidity
    hi = (
        -8.784
        + 1.611 * t
        + 2.339 * r
        - 0.1461 * t * r
        - 0.01231 * t * t
        - 0.01642 * r * r
        + 0.002212 * t * t * r
        + 0.000725 * t * r * r
        - 0.000004 * t * t * r * r
    )
    return round(hi, 1)


def compute_dew_point(temp: float, humidity: float) -> float:
    """
    Approximate dew point (°C) using the Magnus formula.
    """
    import math
    a = 17.27
    b = 237.7
    gamma = (a * temp) / (b + temp) + math.log(humidity / 100.0)
    return round((b * gamma) / (a - gamma), 1)


def compute_fog_risk(humidity: float, temp: float, wind_speed: float | None = None) -> str:
    """
    Estimate fog risk based on humidity, temperature and wind.
    Returns "none", "mist", "fog", or "dense_fog".
    """
    dew_point = compute_dew_point(temp, humidity)
    delta = temp - dew_point

    if delta <= 0.5 and humidity > 95:
        return "dense_fog"
    if delta <= 1.5 and humidity > 90:
        return "fog"
    if delta <= 2.5 and humidity > 80:
        if wind_speed is not None and wind_speed > 3.0:
            return "mist"
        return "fog"
    if delta <= 4.0 and humidity > 70:
        return "mist"
    return "none"


def compute_wind_chill(temp: float, wind_speed_ms: float) -> float:
    """
    Compute wind chill temperature (°C).

    Uses the North American wind chill index formula (adapted to m/s).
    Only applicable when temp < 10°C and wind > 1.3 m/s.
    """
    if temp >= 10.0 or wind_speed_ms < 1.3:
        return temp

    v_kmh = wind_speed_ms * 3.6
    wc = (
        13.12
        + 0.6215 * temp
        - 11.37 * (v_kmh ** 0.16)
        + 0.3965 * temp * (v_kmh ** 0.16)
    )
    return round(wc, 1)
