"""
Sense HAT LED matrix display controller.

Provides high-level routines to visualise system and alert state on the
8×8 RGB LED matrix:
    - Status colour fill (green / amber / red / black)
    - Scrolling text messages
    - Metric bar-graph indicators
    - Custom icon patterns
"""
import logging

from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)

# Colour constants [R, G, B]
GREEN = [0, 255, 0]
AMBER = [255, 165, 0]
RED = [255, 0, 0]
BLACK = [0, 0, 0]
WHITE = [255, 255, 255]
BLUE = [0, 0, 255]

_RISK_COLOURS = {
    "green": GREEN,
    "amber": AMBER,
    "red": RED,
    # "Black" is the most severe risk level (Green → Amber → Red → Black).
    # Filling the matrix with literal black would look identical to "off",
    # so we use white to ensure the alert is visually distinct and unmissable.
    "black": WHITE,
}


class LEDDisplay:
    """High-level LED matrix controller backed by a SenseHatDriver."""

    def __init__(self, sense_hat_driver):
        """
        Parameters
        ----------
        sense_hat_driver : SenseHatDriver | None
            Pass the driver from ``SensorManager.sense_hat``.
        """
        self._hat = sense_hat_driver

    @property
    def available(self) -> bool:
        return self._hat is not None and self._hat.available

    # ------------------------------------------------------------------
    # Full-matrix operations
    # ------------------------------------------------------------------
    def fill(self, colour: list) -> None:
        """Fill the entire 8×8 matrix with a single colour."""
        if not self.available:
            return
        self._hat.set_pixels([colour] * 64)

    def clear(self) -> None:
        """Turn off all LEDs."""
        if not self.available:
            return
        self._hat.clear_display()

    def show_risk_level(self, level: str) -> None:
        """Fill the matrix with the colour matching a risk level string.

        Parameters
        ----------
        level : str
            One of ``"green"``, ``"amber"``, ``"red"``, ``"black"``.
        """
        colour = _RISK_COLOURS.get(level.lower(), GREEN)
        self.fill(colour)
        logger.debug("LED risk level set to '%s'.", level)

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------
    def scroll_message(self, text: str, speed: float = 0.06,
                       colour: list | None = None) -> None:
        """Scroll *text* across the LED matrix."""
        if not self.available:
            return
        self._hat.show_message(
            text,
            scroll_speed=speed,
            text_colour=colour or WHITE,
        )

    # ------------------------------------------------------------------
    # Bar-graph indicator
    # ------------------------------------------------------------------
    def show_bar(self, value: float, min_val: float, max_val: float,
                 colour: list | None = None) -> None:
        """Display a vertical bar graph (column 0) from *min_val* to *max_val*.

        The bar fills bottom-to-top, scaled to 8 rows.
        """
        if not self.available:
            return
        bar_colour = colour or BLUE
        clamped = max(min_val, min(value, max_val))
        frac = (clamped - min_val) / (max_val - min_val) if max_val != min_val else 0
        filled_rows = round(frac * 8)

        pixels = [BLACK] * 64
        for row in range(8 - filled_rows, 8):
            for col in range(8):
                pixels[row * 8 + col] = bar_colour
        self._hat.set_pixels(pixels)

    # ------------------------------------------------------------------
    # Custom icon
    # ------------------------------------------------------------------
    def show_icon(self, icon: list) -> None:
        """Display a custom 8×8 icon.

        Parameters
        ----------
        icon : list
            A flat list of 64 ``[R, G, B]`` colour values.
        """
        if not self.available:
            return
        if len(icon) != 64:
            logger.warning("Icon must contain exactly 64 pixels.")
            return
        self._hat.set_pixels(icon)
