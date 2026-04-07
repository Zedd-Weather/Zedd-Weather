"""
Notification channels for Zedd Weather alerting.
Supports logging, HTTP webhooks, and MQTT publishing.
"""
import json
import logging
import abc
from typing import Optional

from .rules import Alert, AlertSeverity

logger = logging.getLogger(__name__)


def _alert_to_dict(alert: Alert) -> dict:
    """Serialise an Alert to a JSON-friendly dict."""
    return {
        "id": alert.id,
        "severity": alert.severity.value,
        "title": alert.title,
        "message": alert.message,
        "metric": alert.metric,
        "value": alert.value,
        "threshold": alert.threshold,
        "timestamp": alert.timestamp.isoformat(),
        "crop": alert.crop,
    }


class NotificationChannel(abc.ABC):
    """Abstract base class for all notification channels."""

    @abc.abstractmethod
    def send(self, alert: Alert) -> bool:
        """
        Dispatch the alert through this channel.

        Returns
        -------
        True if the alert was delivered successfully, False otherwise.
        """


class LoggingChannel(NotificationChannel):
    """
    Writes alerts to the Python logging system.
    Always available; used as the default channel.
    """

    _LEVEL_MAP = {
        AlertSeverity.INFO: logging.INFO,
        AlertSeverity.WARNING: logging.WARNING,
        AlertSeverity.CRITICAL: logging.CRITICAL,
    }

    def __init__(self, channel_logger: Optional[logging.Logger] = None) -> None:
        self._logger = channel_logger or logging.getLogger("zedd.alerts")

    def send(self, alert: Alert) -> bool:
        level = self._LEVEL_MAP.get(alert.severity, logging.WARNING)
        self._logger.log(
            level,
            "[%s] %s — %s (metric=%s, value=%s)",
            alert.severity.value.upper(),
            alert.title,
            alert.message,
            alert.metric,
            alert.value,
        )
        return True


class WebhookChannel(NotificationChannel):
    """
    POSTs alert JSON payload to an HTTP webhook URL.
    Prefers aiohttp if available, falls back to requests.
    """

    def __init__(self, url: str, timeout: int = 10, headers: Optional[dict] = None) -> None:
        self.url = url
        self.timeout = timeout
        self.headers = headers or {"Content-Type": "application/json"}

    def send(self, alert: Alert) -> bool:
        payload = json.dumps(_alert_to_dict(alert))
        try:
            # Attempt with requests (sync)
            import requests  # type: ignore
            resp = requests.post(
                self.url,
                data=payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            if resp.status_code < 300:
                logger.debug("Webhook delivered alert %s → HTTP %d", alert.id, resp.status_code)
                return True
            logger.warning(
                "Webhook returned non-2xx status %d for alert %s", resp.status_code, alert.id
            )
            return False
        except ImportError:
            logger.error("requests library not available for WebhookChannel.")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Webhook delivery failed for alert %s: %s", alert.id, exc)
            return False


class MqttChannel(NotificationChannel):
    """
    Publishes alert JSON to an MQTT topic using paho-mqtt.
    """

    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        topic: str = "zedd/alerts",
        client_id: str = "zedd-alerting",
        qos: int = 1,
    ) -> None:
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client_id = client_id
        self.qos = qos

    def send(self, alert: Alert) -> bool:
        payload = json.dumps(_alert_to_dict(alert))
        try:
            import paho.mqtt.publish as publish  # type: ignore
            publish.single(
                self.topic,
                payload=payload,
                qos=self.qos,
                hostname=self.broker,
                port=self.port,
                client_id=self.client_id,
            )
            logger.debug("MQTT alert %s published to %s", alert.id, self.topic)
            return True
        except ImportError:
            logger.error("paho-mqtt not available for MqttChannel.")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("MQTT delivery failed for alert %s: %s", alert.id, exc)
            return False


class AlertDispatcher:
    """
    Dispatches alerts to all registered notification channels.

    A LoggingChannel is always included as the default fallback.
    """

    def __init__(self, channels: Optional[list[NotificationChannel]] = None) -> None:
        self._channels: list[NotificationChannel] = channels if channels is not None else []
        # Ensure there is always at least a logging channel
        if not any(isinstance(c, LoggingChannel) for c in self._channels):
            self._channels.insert(0, LoggingChannel())

    def add_channel(self, channel: NotificationChannel) -> None:
        """Register an additional notification channel."""
        self._channels.append(channel)

    def dispatch(self, alert: Alert) -> dict[str, bool]:
        """
        Send the alert to every registered channel.

        Returns
        -------
        dict mapping channel class name to delivery success boolean.
        """
        results: dict[str, bool] = {}
        for channel in self._channels:
            name = type(channel).__name__
            try:
                results[name] = channel.send(alert)
            except Exception as exc:  # noqa: BLE001
                logger.error("Channel %s raised an exception: %s", name, exc)
                results[name] = False
        return results

    def dispatch_all(self, alerts: list[Alert]) -> list[dict[str, bool]]:
        """Dispatch a list of alerts, returning per-alert delivery results."""
        return [self.dispatch(a) for a in alerts]
