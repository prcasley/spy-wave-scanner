"""Unit tests for DiscordWebhook embed building and threshold gating."""

from unittest.mock import MagicMock, patch

import pytest

from src.discord_webhook import DiscordWebhook


def _signal(score: float = 78.0) -> dict:
    return {
        "signal_id": "abcd1234efgh",
        "timestamp": "2026-05-08T14:30:00Z",
        "ticker": "SPY",
        "direction": "long",
        "wave": {"primary_count": "wave_3_impulse", "primary_probability": 0.65, "current_wave": "3", "degree": "intermediate"},
        "price": {
            "spot": 612.45, "entry_zone": [611.5, 613.0],
            "invalidation": 608.2,
            "targets": [{"price": 618.0, "fib_ratio": 1.618, "probability": 0.55}],
        },
        "options": {
            "suggested_structure": "long_call",
            "expiration": "2026-05-16",
            "dte": 8,
            "legs": [{"action":"buy","type":"call","strike":614.0,"premium":2.85,"delta":0.42,"iv":0.18}],
            "max_loss": 285.0, "max_gain": "unlimited", "breakeven": 616.85,
            "probability_of_profit": 0.48,
        },
        "confluence": {"score": score, "factors": ["wave_3_extension", "iv_rank_below_30"]},
        "risk": {"suggested_position_size_pct": 1.5, "stop_loss_method": "invalidation_level"},
    }


def test_embed_contains_ticker_and_structure():
    embed = DiscordWebhook.build_embed(_signal())
    assert "SPY" in embed["title"]
    assert "long_call" in embed["title"]
    assert embed["color"] == 0x2ECC71  # green for long


def test_embed_red_for_short():
    sig = _signal()
    sig["direction"] = "short"
    embed = DiscordWebhook.build_embed(sig)
    assert embed["color"] == 0xE74C3C


def test_post_skipped_below_threshold():
    hook = DiscordWebhook(url="https://example.test/discord")
    with patch("src.discord_webhook.requests.post") as p:
        ok = hook.post(_signal(score=60), score_threshold=70)
    assert ok is False
    p.assert_not_called()


def test_post_called_above_threshold():
    hook = DiscordWebhook(url="https://example.test/discord")
    fake_resp = MagicMock(status_code=204)
    with patch("src.discord_webhook.requests.post", return_value=fake_resp) as p:
        ok = hook.post(_signal(score=78), score_threshold=70)
    assert ok is True
    p.assert_called_once()


def test_post_skipped_when_unconfigured():
    hook = DiscordWebhook(url=None)
    with patch("src.discord_webhook.requests.post") as p:
        assert hook.post(_signal(), score_threshold=70) is False
    p.assert_not_called()
