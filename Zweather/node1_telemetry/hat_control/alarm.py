"""
GPIO-based alarm controller — buzzer and LED warning outputs.

Used for fail-safe local alerts when telemetry thresholds are breached
(as described in the project README: "triggers local visual/auditory alarms
via the Pi's GPIO pins if thresholds are breached").
"""
import threading
import time
import logging

from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)


class AlarmController:
    """Controls a buzzer and an indicator LED via GPIO."""

    def __init__(self):
        self._gpio = None
        self._available = False
        self._active = False
        self._pulse_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(config.ALARM_BUZZER_GPIO_PIN, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(config.ALARM_LED_GPIO_PIN, GPIO.OUT, initial=GPIO.LOW)
            self._available = True
            logger.info(
                "Alarm controller initialised (buzzer=GPIO%d, LED=GPIO%d).",
                config.ALARM_BUZZER_GPIO_PIN, config.ALARM_LED_GPIO_PIN,
            )
        except (ImportError, RuntimeError) as exc:
            logger.warning("GPIO alarm unavailable (%s). Alarm is software-only.", exc)
            self._available = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def trigger(self) -> None:
        """Activate the alarm (buzzer + LED pulsing)."""
        if self._active:
            return
        self._active = True
        logger.warning("ALARM TRIGGERED — activating buzzer and LED.")

        if self._available:
            self._stop_event.clear()
            self._pulse_thread = threading.Thread(
                target=self._pulse_loop, daemon=True
            )
            self._pulse_thread.start()

    def silence(self) -> None:
        """Deactivate the alarm."""
        if not self._active:
            return
        self._active = False
        self._stop_event.set()
        logger.info("Alarm silenced.")

        if self._available:
            self._gpio.output(config.ALARM_BUZZER_GPIO_PIN, self._gpio.LOW)
            self._gpio.output(config.ALARM_LED_GPIO_PIN, self._gpio.LOW)

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Threshold evaluation
    # ------------------------------------------------------------------
    def evaluate(self, telemetry: dict) -> None:
        """Check *telemetry* against configured thresholds and trigger/silence."""
        temp = telemetry.get("temperature_c")
        wind = telemetry.get("wind_speed_ms")
        uv = telemetry.get("uv_index")
        aqi = telemetry.get("pm2_5_ug_m3")  # use PM2.5 as AQI proxy

        should_alarm = False

        if temp is not None:
            if temp > config.ALERT_TEMP_HIGH_C or temp < config.ALERT_TEMP_LOW_C:
                logger.warning("Temperature threshold breached: %.1f °C", temp)
                should_alarm = True

        if wind is not None and wind > config.ALERT_WIND_SPEED_MS:
            logger.warning("Wind speed threshold breached: %.1f m/s", wind)
            should_alarm = True

        if uv is not None and uv > config.ALERT_UV_INDEX:
            logger.warning("UV index threshold breached: %.1f", uv)
            should_alarm = True

        if aqi is not None and aqi > config.ALERT_AQI:
            logger.warning("AQI threshold breached: %.1f µg/m³", aqi)
            should_alarm = True

        if should_alarm:
            self.trigger()
        else:
            self.silence()

    # ------------------------------------------------------------------
    # Internal pulse loop
    # ------------------------------------------------------------------
    def _pulse_loop(self) -> None:
        """Toggle buzzer and LED at ~2 Hz until stopped."""
        while not self._stop_event.is_set():
            self._gpio.output(config.ALARM_BUZZER_GPIO_PIN, self._gpio.HIGH)
            self._gpio.output(config.ALARM_LED_GPIO_PIN, self._gpio.HIGH)
            time.sleep(0.25)
            self._gpio.output(config.ALARM_BUZZER_GPIO_PIN, self._gpio.LOW)
            self._gpio.output(config.ALARM_LED_GPIO_PIN, self._gpio.LOW)
            time.sleep(0.25)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        self.silence()
        if self._available:
            try:
                self._gpio.cleanup([
                    config.ALARM_BUZZER_GPIO_PIN,
                    config.ALARM_LED_GPIO_PIN,
                ])
            except (RuntimeError, AttributeError):
                pass
