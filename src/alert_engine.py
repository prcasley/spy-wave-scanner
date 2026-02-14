"""Module 6: Alert Engine — monitor levels and push notifications."""

from __future__ import annotations

import json
import logging
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional

import requests

from src.models import (
    Alert,
    AlertPriority,
    AlertType,
    ConfluenceZone,
    Divergence,
    DivergenceType,
    FibLevel,
    WaveCount,
    WaveLabel,
    WaveProjection,
)

logger = logging.getLogger(__name__)


class AlertEngine:
    """Generate and deliver wave-setup alerts."""

    def __init__(
        self,
        ticker: str = "SPY",
        slack_webhook: Optional[str] = None,
        email_config: Optional[dict] = None,
        sms_config: Optional[dict] = None,
        proximity_pct: float = 0.15,
        invalidation_pct: float = 0.20,
        cooldown_minutes: int = 15,
    ):
        self.ticker = ticker
        self.slack_webhook = slack_webhook or os.environ.get("SLACK_WEBHOOK")
        self.email_config = email_config
        self.sms_config = sms_config
        self.proximity_pct = proximity_pct
        self.invalidation_pct = invalidation_pct
        self.cooldown_minutes = cooldown_minutes
        self._recent_alerts: list[Alert] = []

    # ------------------------------------------------------------------
    # Alert generation
    # ------------------------------------------------------------------

    def check_proximity_alerts(
        self,
        current_price: float,
        wave_count: Optional[WaveCount],
        fib_levels: list[FibLevel],
        confluence_zones: list[ConfluenceZone] | None = None,
        divergences: list[Divergence] | None = None,
        projection: Optional[WaveProjection] = None,
    ) -> list[Alert]:
        """Check if the current price is near any key levels and return alerts."""
        alerts: list[Alert] = []

        # --- Fib level proximity ---
        for lv in fib_levels:
            distance_pct = abs(current_price - lv.price) / current_price * 100
            if distance_pct <= self.proximity_pct:
                if "retracement" in lv.label and lv.ratio >= 0.382:
                    alert_type = AlertType.APPROACHING_RESISTANCE
                    priority = AlertPriority.MEDIUM
                else:
                    alert_type = AlertType.APPROACHING_SUPPORT
                    priority = AlertPriority.MEDIUM

                alerts.append(
                    Alert(
                        alert_type=alert_type,
                        priority=priority,
                        ticker=self.ticker,
                        current_price=current_price,
                        target_price=lv.price,
                        message=f"Price ${current_price:.2f} approaching {lv.label} at ${lv.price:.2f}",
                        fib_levels=[lv],
                        timestamp=datetime.now(),
                    )
                )

        # --- Invalidation check ---
        if wave_count and wave_count.invalidation_price is not None:
            inv_dist = abs(current_price - wave_count.invalidation_price) / current_price * 100
            if inv_dist <= self.invalidation_pct:
                alerts.append(
                    Alert(
                        alert_type=AlertType.INVALIDATION_WARNING,
                        priority=AlertPriority.HIGH,
                        ticker=self.ticker,
                        current_price=current_price,
                        invalidation_price=wave_count.invalidation_price,
                        message=(
                            f"INVALIDATION WARNING: ${current_price:.2f} within "
                            f"{inv_dist:.2f}% of invalidation at "
                            f"${wave_count.invalidation_price:.2f}"
                        ),
                        confidence=wave_count.confidence,
                        timestamp=datetime.now(),
                    )
                )

        # --- Confluence zone ---
        if confluence_zones:
            for zone in confluence_zones:
                low, high = zone.price_range
                if low <= current_price <= high:
                    alerts.append(
                        Alert(
                            alert_type=AlertType.CONFLUENCE_ZONE,
                            priority=AlertPriority.MEDIUM,
                            ticker=self.ticker,
                            current_price=current_price,
                            target_price=zone.center_price,
                            message=(
                                f"Price in confluence zone ${low:.2f}-${high:.2f} "
                                f"({zone.strength} levels)"
                            ),
                            fib_levels=zone.levels,
                            timestamp=datetime.now(),
                        )
                    )

        # --- Divergence ---
        if divergences:
            for div in divergences:
                alerts.append(
                    Alert(
                        alert_type=AlertType.DIVERGENCE_DETECTED,
                        priority=AlertPriority.HIGH,
                        ticker=self.ticker,
                        current_price=current_price,
                        message=(
                            f"{div.type.value.upper()} divergence on {div.indicator}: "
                            f"price {div.price_pivot_2.price:.2f} vs "
                            f"indicator {div.indicator_value_2:.2f}"
                        ),
                        divergences=[div],
                        timestamp=datetime.now(),
                    )
                )

        # --- Wave complete ---
        if wave_count and wave_count.is_complete:
            last_wave = wave_count.waves[-1] if wave_count.waves else None
            target_str = ""
            if projection:
                target_str = f" → Next: {projection.next_wave} target ${projection.primary_target:.2f}"
            alerts.append(
                Alert(
                    alert_type=AlertType.WAVE_COMPLETE,
                    priority=AlertPriority.HIGH,
                    ticker=self.ticker,
                    current_price=current_price,
                    message=(
                        f"{wave_count.pattern_type.upper()} complete "
                        f"({wave_count.direction.value}){target_str}"
                    ),
                    wave_label=last_wave.label.value if last_wave else None,
                    confidence=wave_count.confidence,
                    timestamp=datetime.now(),
                )
            )

        # Apply cooldown
        alerts = self._apply_cooldown(alerts)
        self._recent_alerts.extend(alerts)
        return alerts

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_alert(self, alert: Alert) -> str:
        """Format an alert as a readable text block for Slack / email."""
        icon = {
            AlertPriority.HIGH: "HIGH",
            AlertPriority.MEDIUM: "MEDIUM",
            AlertPriority.LOW: "LOW",
        }.get(alert.priority, "")

        lines = [
            "-----------------------------",
            f"  {alert.ticker} WAVE ALERT [{icon}]",
            "-----------------------------",
            f"Type: {alert.alert_type.value.replace('_', ' ').title()}",
            f"Current: ${alert.current_price:.2f}",
        ]

        if alert.target_price is not None:
            lines.append(f"Target: ${alert.target_price:.2f}")
        if alert.invalidation_price is not None:
            lines.append(f"Invalidation: ${alert.invalidation_price:.2f}")
        if alert.wave_label:
            lines.append(f"Wave: {alert.wave_label}")
        if alert.confidence > 0:
            lines.append(f"Confidence: {alert.confidence:.0%}")
        if alert.message:
            lines.append(f"Detail: {alert.message}")

        lines.append("-----------------------------")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    def send_slack(self, message: str) -> bool:
        """Post a message to Slack via incoming webhook."""
        if not self.slack_webhook:
            logger.warning("Slack webhook not configured — skipping")
            return False
        try:
            resp = requests.post(
                self.slack_webhook,
                json={"text": message},
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info("Slack alert sent")
                return True
            logger.error("Slack error %d: %s", resp.status_code, resp.text)
        except requests.RequestException as exc:
            logger.error("Slack send failed: %s", exc)
        return False

    def send_email(self, subject: str, body: str) -> bool:
        """Send an email alert via SMTP."""
        if not self.email_config:
            logger.warning("Email not configured — skipping")
            return False
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.email_config["from"]
            msg["To"] = self.email_config["to"]
            with smtplib.SMTP(
                self.email_config.get("smtp_server", "smtp.gmail.com"),
                self.email_config.get("smtp_port", 587),
            ) as server:
                server.starttls()
                server.login(
                    self.email_config["from"],
                    self.email_config["password"],
                )
                server.sendmail(
                    self.email_config["from"],
                    self.email_config["to"],
                    msg.as_string(),
                )
            logger.info("Email alert sent to %s", self.email_config["to"])
            return True
        except Exception as exc:
            logger.error("Email send failed: %s", exc)
            return False

    def send_sms(self, message: str) -> bool:
        """Send an SMS via Twilio."""
        if not self.sms_config:
            logger.warning("SMS not configured — skipping")
            return False
        try:
            from twilio.rest import Client as TwilioClient

            client = TwilioClient(
                self.sms_config["sid"],
                self.sms_config["token"],
            )
            client.messages.create(
                body=message,
                from_=self.sms_config["from"],
                to=self.sms_config["to"],
            )
            logger.info("SMS alert sent")
            return True
        except Exception as exc:
            logger.error("SMS send failed: %s", exc)
            return False

    def dispatch_alert(self, alert: Alert) -> None:
        """Format and send an alert through all configured channels."""
        text = self.format_alert(alert)
        self.send_slack(text)
        if self.email_config:
            subject = f"{self.ticker} Wave Alert: {alert.alert_type.value}"
            self.send_email(subject, text)
        if self.sms_config:
            self.send_sms(text[:160])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_cooldown(self, alerts: list[Alert]) -> list[Alert]:
        """Filter out alerts that duplicate a recent alert within cooldown."""
        cutoff = datetime.now() - timedelta(minutes=self.cooldown_minutes)
        self._recent_alerts = [
            a for a in self._recent_alerts if a.timestamp > cutoff
        ]

        filtered: list[Alert] = []
        for alert in alerts:
            is_dup = any(
                r.alert_type == alert.alert_type
                and r.target_price == alert.target_price
                for r in self._recent_alerts
            )
            if not is_dup:
                filtered.append(alert)
        return filtered
