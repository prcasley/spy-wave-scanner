"""Discord webhook delivery — rich embed formatting for signals."""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_GREEN = 0x2ECC71
_RED = 0xE74C3C


class DiscordWebhook:
    """Post signals to a Discord channel via incoming-webhook."""

    def __init__(self, url: Optional[str] = None) -> None:
        self.url = url or os.environ.get("DISCORD_WEBHOOK_URL")

    @property
    def configured(self) -> bool:
        return bool(self.url)

    def post(self, signal: dict, score_threshold: float = 70.0) -> bool:
        """Post the signal as a rich embed if confluence >= threshold."""
        if not self.configured:
            logger.debug("Discord webhook not set; skipping post")
            return False
        score = float(signal.get("confluence", {}).get("score", 0))
        if score < score_threshold:
            logger.info(
                "Signal %s for %s scored %.1f < threshold %.1f — skipping Discord",
                signal.get("signal_id", "?")[:8],
                signal.get("ticker", "?"),
                score,
                score_threshold,
            )
            return False

        embed = self.build_embed(signal)
        try:
            resp = requests.post(self.url, json={"embeds": [embed]}, timeout=10)
            if 200 <= resp.status_code < 300:
                logger.info(
                    "Posted signal %s for %s to Discord",
                    signal.get("signal_id", "?")[:8], signal.get("ticker", "?"),
                )
                return True
            logger.error(
                "Discord error %d: %s", resp.status_code, resp.text[:200]
            )
        except requests.RequestException as exc:
            logger.error("Discord post failed: %s", exc)
        return False

    @staticmethod
    def build_embed(signal: dict) -> dict:
        direction = signal.get("direction", "?")
        color = _GREEN if direction == "long" else _RED
        ticker = signal.get("ticker", "?")
        wave = signal.get("wave", {}) or {}
        opts = signal.get("options", {}) or {}
        price = signal.get("price", {}) or {}
        confl = signal.get("confluence", {}) or {}
        entry = price.get("entry_zone") or [0, 0]
        targets = price.get("targets") or []
        legs = opts.get("legs") or []

        target_text = (
            "\n".join(
                f"  • ${t['price']:.2f} (fib {t['fib_ratio']}, p={t['probability']:.0%})"
                for t in targets[:3]
            )
            or "  • —"
        )
        legs_text = (
            "\n".join(
                f"  {l['action'].upper()} {l['type'].upper()} "
                f"${l['strike']:.2f} @ ${l['premium']:.2f} "
                f"(Δ={l['delta']:+.2f}, IV={l['iv']:.0%})"
                for l in legs
            )
            or "  —"
        )
        factors = "\n".join(f"  • {f}" for f in (confl.get("factors") or [])) or "  • —"

        return {
            "title": f"{ticker} — {direction.upper()} {opts.get('suggested_structure','')}",
            "color": color,
            "fields": [
                {
                    "name": "Wave",
                    "value": (
                        f"{wave.get('primary_count','?')} "
                        f"(p={wave.get('primary_probability', 0):.0%}, "
                        f"degree={wave.get('degree','?')})"
                    ),
                    "inline": False,
                },
                {
                    "name": "Price",
                    "value": (
                        f"Spot ${price.get('spot', 0):.2f} | "
                        f"Entry ${entry[0]:.2f}-${entry[1]:.2f} | "
                        f"Invalidation ${price.get('invalidation', 0):.2f}"
                    ),
                    "inline": False,
                },
                {"name": "Targets", "value": target_text, "inline": False},
                {
                    "name": f"Options (DTE {opts.get('dte','?')}, exp {opts.get('expiration','?')})",
                    "value": (
                        f"{legs_text}\n"
                        f"  Max loss ${opts.get('max_loss', 0):.2f}, "
                        f"max gain {opts.get('max_gain', 0)}, "
                        f"breakeven ${opts.get('breakeven', 0):.2f}, "
                        f"PoP {opts.get('probability_of_profit', 0):.0%}"
                    ),
                    "inline": False,
                },
                {
                    "name": f"Confluence {confl.get('score', 0):.1f}",
                    "value": factors,
                    "inline": False,
                },
            ],
            "timestamp": signal.get("timestamp"),
            "footer": {"text": f"signal_id {signal.get('signal_id','')[:8]}"},
        }
