"""Module 4: Wave Counter — apply Elliott Wave rules to classify wave structure."""

from __future__ import annotations

import logging
from typing import Optional

from src.models import (
    CorrectivePattern,
    Pivot,
    PivotType,
    Wave,
    WaveCount,
    WaveDirection,
    WaveDegree,
    WaveLabel,
    WaveProjection,
)

logger = logging.getLogger(__name__)


class WaveCounter:
    """Fit Elliott Wave impulse and corrective patterns to detected pivots.

    Elliott Wave Rules (cardinal — must NOT be violated):
        1. Wave 2 cannot retrace more than 100 % of Wave 1.
        2. Wave 3 cannot be the shortest of Waves 1, 3 and 5.
        3. Wave 4 cannot enter the price territory of Wave 1 (impulse only).

    Guidelines (commonly observed):
        - Wave 3 is often 161.8 % extension of Wave 1.
        - Wave 2 often retraces 50-61.8 % of Wave 1.
        - Wave 4 often retraces 38.2 % of Wave 3.
        - Wave 5 often equals Wave 1 in length.
        - Alternation: if Wave 2 is sharp, Wave 4 is flat (and vice-versa).
    """

    # ------------------------------------------------------------------
    # Impulse counting
    # ------------------------------------------------------------------

    def count_impulse(
        self,
        pivots: list[Pivot],
        direction: WaveDirection = WaveDirection.DOWN,
        degree: WaveDegree = WaveDegree.MINUETTE,
    ) -> Optional[WaveCount]:
        """Attempt to fit a 5-wave impulse to the supplied pivots.

        For a *downward* impulse we expect the sequence:
            HIGH → LOW → HIGH → LOW → HIGH → LOW
            (origin) W1-end  W2-end  W3-end  W4-end  W5-end

        Returns ``None`` if fewer than 6 alternating pivots are available.
        """
        ordered = self._select_pivots_for_direction(pivots, direction)
        if ordered is None or len(ordered) < 6:
            return None

        # Build 5 waves from the first 6 pivots
        labels = [WaveLabel.W1, WaveLabel.W2, WaveLabel.W3, WaveLabel.W4, WaveLabel.W5]
        waves: list[Wave] = []
        for idx, label in enumerate(labels):
            waves.append(Wave(label=label, start=ordered[idx], end=ordered[idx + 1]))

        wc = WaveCount(
            waves=waves,
            direction=direction,
            degree=degree,
            pattern_type="impulse",
        )

        # Validate and score
        is_valid, violations = self.validate_wave_rules(wc)
        wc.violations = violations
        wc.confidence = self._score_impulse(wc)
        wc.invalidation_price = self._compute_invalidation(wc)
        return wc

    def count_impulse_best(
        self,
        pivots: list[Pivot],
        direction: WaveDirection = WaveDirection.DOWN,
    ) -> Optional[WaveCount]:
        """Try every consecutive window of 6 pivots and return the best-scoring
        valid impulse count, or ``None`` if nothing valid is found.
        """
        ordered = self._select_pivots_for_direction(pivots, direction)
        if ordered is None or len(ordered) < 6:
            return None

        best: Optional[WaveCount] = None
        for start in range(len(ordered) - 5):
            window = ordered[start: start + 6]
            labels = [WaveLabel.W1, WaveLabel.W2, WaveLabel.W3, WaveLabel.W4, WaveLabel.W5]
            waves = [
                Wave(label=labels[i], start=window[i], end=window[i + 1])
                for i in range(5)
            ]
            wc = WaveCount(
                waves=waves,
                direction=direction,
                pattern_type="impulse",
            )
            is_valid, violations = self.validate_wave_rules(wc)
            if not is_valid:
                continue
            wc.violations = violations
            wc.confidence = self._score_impulse(wc)
            wc.invalidation_price = self._compute_invalidation(wc)
            if best is None or wc.confidence > best.confidence:
                best = wc
        return best

    # ------------------------------------------------------------------
    # Corrective counting
    # ------------------------------------------------------------------

    def count_corrective(
        self,
        pivots: list[Pivot],
        direction: WaveDirection = WaveDirection.UP,
        degree: WaveDegree = WaveDegree.MINUETTE,
    ) -> Optional[WaveCount]:
        """Attempt to fit an ABC correction to the supplied pivots.

        For a corrective rally after a downtrend we expect:
            LOW → HIGH → LOW → HIGH  (A-up, B-down, C-up)

        Returns ``None`` if fewer than 4 alternating pivots available.
        """
        ordered = self._select_pivots_for_direction(pivots, direction)
        if ordered is None or len(ordered) < 4:
            return None

        waves = [
            Wave(label=WaveLabel.WA, start=ordered[0], end=ordered[1]),
            Wave(label=WaveLabel.WB, start=ordered[1], end=ordered[2]),
            Wave(label=WaveLabel.WC, start=ordered[2], end=ordered[3]),
        ]

        subtype = self._classify_corrective(waves, direction)

        wc = WaveCount(
            waves=waves,
            direction=direction,
            degree=degree,
            pattern_type="corrective",
            corrective_subtype=subtype,
        )
        wc.confidence = self._score_corrective(wc)
        wc.invalidation_price = self._compute_invalidation(wc)
        return wc

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_wave_rules(
        self, wave_count: WaveCount
    ) -> tuple[bool, list[str]]:
        """Check the three cardinal Elliott Wave rules.

        Returns ``(is_valid, list_of_violation_descriptions)``.
        """
        violations: list[str] = []
        if wave_count.pattern_type != "impulse":
            return True, violations

        w1 = wave_count.wave_by_label(WaveLabel.W1)
        w2 = wave_count.wave_by_label(WaveLabel.W2)
        w3 = wave_count.wave_by_label(WaveLabel.W3)
        w4 = wave_count.wave_by_label(WaveLabel.W4)
        w5 = wave_count.wave_by_label(WaveLabel.W5)

        if not all([w1, w2, w3, w4, w5]):
            violations.append("Incomplete impulse — missing waves")
            return False, violations
        assert w1 is not None and w2 is not None and w3 is not None
        assert w4 is not None and w5 is not None

        # Rule 1: Wave 2 cannot retrace > 100 % of Wave 1
        if w2.length > w1.length:
            violations.append(
                f"Rule 1 violated: Wave 2 ({w2.length:.2f}) retraces "
                f"more than 100% of Wave 1 ({w1.length:.2f})"
            )

        # Rule 2: Wave 3 cannot be the shortest impulse wave
        impulse_lengths = [w1.length, w3.length, w5.length]
        if w3.length == min(impulse_lengths) and w3.length < w1.length and w3.length < w5.length:
            violations.append(
                f"Rule 2 violated: Wave 3 ({w3.length:.2f}) is the shortest "
                f"impulse wave (W1={w1.length:.2f}, W5={w5.length:.2f})"
            )

        # Rule 3: Wave 4 cannot overlap Wave 1 territory
        if wave_count.direction == WaveDirection.DOWN:
            # Down impulse: W1 goes high→low, W4 goes low→high
            # W1 low = w1.end.price, W4 high = w4.end.price
            # W4 high must stay below W1 low
            if w4.end.price > w1.end.price:
                violations.append(
                    f"Rule 3 violated: Wave 4 end ({w4.end.price:.2f}) "
                    f"overlaps Wave 1 end ({w1.end.price:.2f})"
                )
        else:
            # Up impulse: W1 goes low→high, W4 goes high→low
            # W4 low must stay above W1 high
            if w4.end.price < w1.end.price:
                violations.append(
                    f"Rule 3 violated: Wave 4 end ({w4.end.price:.2f}) "
                    f"overlaps Wave 1 end ({w1.end.price:.2f})"
                )

        return len(violations) == 0, violations

    # ------------------------------------------------------------------
    # Invalidation & Projection
    # ------------------------------------------------------------------

    def get_invalidation_level(self, wave_count: WaveCount) -> Optional[float]:
        """Price level that would invalidate the current count."""
        return wave_count.invalidation_price

    def project_targets(self, wave_count: WaveCount) -> Optional[WaveProjection]:
        """Project next wave targets based on the current position."""
        if not wave_count.waves:
            return None

        w1 = wave_count.wave_by_label(WaveLabel.W1)
        w2 = wave_count.wave_by_label(WaveLabel.W2)
        w3 = wave_count.wave_by_label(WaveLabel.W3)
        w4 = wave_count.wave_by_label(WaveLabel.W4)
        w5 = wave_count.wave_by_label(WaveLabel.W5)

        down = wave_count.direction == WaveDirection.DOWN

        # --- 5-wave complete → project ABC correction ---
        if wave_count.is_complete and wave_count.pattern_type == "impulse":
            if w1 and w5:
                total_impulse = abs(w1.start.price - w5.end.price)
                if down:
                    primary = w5.end.price + total_impulse * 0.382
                    alts = [
                        round(w5.end.price + total_impulse * 0.500, 2),
                        round(w5.end.price + total_impulse * 0.618, 2),
                    ]
                else:
                    primary = w5.end.price - total_impulse * 0.382
                    alts = [
                        round(w5.end.price - total_impulse * 0.500, 2),
                        round(w5.end.price - total_impulse * 0.618, 2),
                    ]
                return WaveProjection(
                    next_wave="ABC correction",
                    primary_target=round(primary, 2),
                    alt_targets=alts,
                    invalidation=wave_count.invalidation_price or 0.0,
                    confidence=wave_count.confidence,
                )

        # --- Waves 1-4 present → project Wave 5 ---
        if w4 and w1 and not w5:
            w1_len = w1.length
            if down:
                primary = w4.end.price - w1_len  # W5 = W1
                alt_1 = round(w4.end.price - w1_len * 0.618, 2)
                alt_2 = round(w4.end.price - w1_len * 1.618, 2)
            else:
                primary = w4.end.price + w1_len
                alt_1 = round(w4.end.price + w1_len * 0.618, 2)
                alt_2 = round(w4.end.price + w1_len * 1.618, 2)
            return WaveProjection(
                next_wave="Wave 5",
                primary_target=round(primary, 2),
                alt_targets=[alt_1, alt_2],
                invalidation=wave_count.invalidation_price or 0.0,
                confidence=wave_count.confidence,
            )

        # --- Waves 1-2 present → project Wave 3 ---
        if w2 and w1 and not w3:
            w1_len = w1.length
            if down:
                primary = w2.end.price - w1_len * 1.618
                alts = [
                    round(w2.end.price - w1_len * 1.000, 2),
                    round(w2.end.price - w1_len * 2.618, 2),
                ]
            else:
                primary = w2.end.price + w1_len * 1.618
                alts = [
                    round(w2.end.price + w1_len * 1.000, 2),
                    round(w2.end.price + w1_len * 2.618, 2),
                ]
            return WaveProjection(
                next_wave="Wave 3",
                primary_target=round(primary, 2),
                alt_targets=alts,
                invalidation=wave_count.invalidation_price or 0.0,
                confidence=wave_count.confidence,
            )

        # --- Waves 1-3 present → project Wave 4 ---
        if w3 and not w4:
            w3_len = w3.length
            if down:
                primary = w3.end.price + w3_len * 0.382
                alts = [
                    round(w3.end.price + w3_len * 0.500, 2),
                    round(w3.end.price + w3_len * 0.236, 2),
                ]
            else:
                primary = w3.end.price - w3_len * 0.382
                alts = [
                    round(w3.end.price - w3_len * 0.500, 2),
                    round(w3.end.price - w3_len * 0.236, 2),
                ]
            return WaveProjection(
                next_wave="Wave 4",
                primary_target=round(primary, 2),
                alt_targets=alts,
                invalidation=wave_count.invalidation_price or 0.0,
                confidence=wave_count.confidence,
            )

        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_pivots_for_direction(
        self,
        pivots: list[Pivot],
        direction: WaveDirection,
    ) -> Optional[list[Pivot]]:
        """Return an alternating sequence of pivots starting with the correct
        type for the given direction.

        For a *down* impulse the first pivot must be a HIGH.
        For an *up* impulse the first pivot must be a LOW.
        """
        if not pivots:
            return None

        start_type = PivotType.HIGH if direction == WaveDirection.DOWN else PivotType.LOW

        # Find first pivot of the right type
        start_idx = None
        for i, p in enumerate(pivots):
            if p.type == start_type:
                start_idx = i
                break
        if start_idx is None:
            return None

        ordered: list[Pivot] = [pivots[start_idx]]
        for p in pivots[start_idx + 1:]:
            if p.type != ordered[-1].type:
                ordered.append(p)
        return ordered

    @staticmethod
    def _score_impulse(wc: WaveCount) -> float:
        """Heuristic confidence score (0–1) for an impulse count."""
        if wc.violations:
            return 0.0

        score = 0.5  # base score for a valid count

        w1 = wc.wave_by_label(WaveLabel.W1)
        w2 = wc.wave_by_label(WaveLabel.W2)
        w3 = wc.wave_by_label(WaveLabel.W3)
        w4 = wc.wave_by_label(WaveLabel.W4)
        w5 = wc.wave_by_label(WaveLabel.W5)

        if not all([w1, w2, w3, w4, w5]):
            return score
        assert w1 is not None and w2 is not None and w3 is not None
        assert w4 is not None and w5 is not None

        # +0.1 if W3 is the longest
        if w3.length >= w1.length and w3.length >= w5.length:
            score += 0.10

        # +0.1 if W3 ≈ 161.8% of W1
        if w1.length > 0:
            w3_ratio = w3.length / w1.length
            if 1.4 <= w3_ratio <= 1.85:
                score += 0.10

        # +0.05 if W2 retraces 50-61.8% of W1
        if w1.length > 0:
            w2_ratio = w2.length / w1.length
            if 0.45 <= w2_ratio <= 0.65:
                score += 0.05

        # +0.05 if W4 retraces 38.2% of W3
        if w3.length > 0:
            w4_ratio = w4.length / w3.length
            if 0.30 <= w4_ratio <= 0.50:
                score += 0.05

        # +0.05 if W5 ≈ W1 in length
        if w1.length > 0:
            w5_ratio = w5.length / w1.length
            if 0.8 <= w5_ratio <= 1.2:
                score += 0.05

        # +0.05 alternation heuristic: W2 sharp / W4 flat (or vice versa)
        if w1.length > 0 and w3.length > 0:
            w2_depth = w2.length / w1.length
            w4_depth = w4.length / w3.length
            if abs(w2_depth - w4_depth) > 0.15:
                score += 0.05

        # +0.05 proportional time (W3 is not the shortest in time)
        w3_bars = abs(w3.end.bar_index - w3.start.bar_index)
        w1_bars = abs(w1.end.bar_index - w1.start.bar_index)
        w5_bars = abs(w5.end.bar_index - w5.start.bar_index)
        if w3_bars >= w1_bars or w3_bars >= w5_bars:
            score += 0.05

        return min(score, 1.0)

    @staticmethod
    def _score_corrective(wc: WaveCount) -> float:
        """Heuristic confidence score for a corrective count."""
        score = 0.4
        wa = wc.wave_by_label(WaveLabel.WA)
        wb = wc.wave_by_label(WaveLabel.WB)
        wc_wave = wc.wave_by_label(WaveLabel.WC)
        if wa and wb and wc_wave:
            # +0.1 if C ≈ A
            if wa.length > 0:
                ratio = wc_wave.length / wa.length
                if 0.8 <= ratio <= 1.2:
                    score += 0.10
            # +0.1 if B retraces 50-78.6% of A
            if wa.length > 0:
                b_ratio = wb.length / wa.length
                if 0.45 <= b_ratio <= 0.80:
                    score += 0.10
            # +0.1 if clear three-wave structure
            score += 0.10
        return min(score, 1.0)

    @staticmethod
    def _classify_corrective(
        waves: list[Wave], direction: WaveDirection
    ) -> CorrectivePattern:
        """Determine corrective sub-type: zigzag, flat, or triangle."""
        if len(waves) < 3:
            return CorrectivePattern.COMPLEX

        wa, wb, wc = waves[0], waves[1], waves[2]

        # Zigzag: B retraces < 61.8% of A, C ≈ A
        if wa.length > 0:
            b_ratio = wb.length / wa.length
            c_ratio = wc.length / wa.length
            if b_ratio < 0.618 and 0.8 <= c_ratio <= 1.5:
                return CorrectivePattern.ZIGZAG
            # Flat: B retraces 90-100%+ of A, C ≈ A
            if b_ratio >= 0.90:
                return CorrectivePattern.FLAT

        return CorrectivePattern.COMPLEX

    @staticmethod
    def _compute_invalidation(wc: WaveCount) -> Optional[float]:
        """Compute the invalidation price for the current count."""
        if wc.pattern_type == "impulse":
            w1 = wc.wave_by_label(WaveLabel.W1)
            w4 = wc.wave_by_label(WaveLabel.W4)
            w2 = wc.wave_by_label(WaveLabel.W2)
            if w4:
                # If we're in wave 5, invalidation is wave 4 going beyond
                # wave 1 territory (the end of wave 1)
                return w1.end.price if w1 else None
            if w2:
                # If we're in wave 3, invalidation is wave 2 start (origin)
                return w1.start.price if w1 else None
            if w1:
                return w1.start.price
        elif wc.pattern_type == "corrective":
            wa = wc.wave_by_label(WaveLabel.WA)
            if wa:
                return wa.start.price
        return None
