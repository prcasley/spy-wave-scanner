"""Module 3: Fibonacci Mapper — calculate retracement and extension levels."""

from __future__ import annotations

import logging
from typing import Optional

from src.models import ConfluenceZone, FibLevel

logger = logging.getLogger(__name__)


class FibMapper:
    """Calculate Fibonacci retracement and extension levels from swing pivots."""

    RETRACEMENT_RATIOS: dict[float, str] = {
        0.236: "23.6%",
        0.382: "38.2%",
        0.500: "50.0%",
        0.618: "61.8%",
        0.786: "78.6%",
        1.000: "100.0%",
    }

    EXTENSION_RATIOS: dict[float, str] = {
        1.000: "100.0%",
        1.272: "127.2%",
        1.382: "138.2%",
        1.618: "161.8%",
        2.000: "200.0%",
        2.618: "261.8%",
    }

    def __init__(
        self,
        retracement_levels: list[float] | None = None,
        extension_levels: list[float] | None = None,
    ):
        if retracement_levels is not None:
            self.RETRACEMENT_RATIOS = {
                r: f"{r*100:.1f}%" for r in retracement_levels
            }
        if extension_levels is not None:
            self.EXTENSION_RATIOS = {
                r: f"{r*100:.1f}%" for r in extension_levels
            }

    # ------------------------------------------------------------------
    # Retracements
    # ------------------------------------------------------------------

    def calculate_retracements(
        self,
        swing_high: float,
        swing_low: float,
        direction: str = "down",
    ) -> list[FibLevel]:
        """Calculate Fibonacci retracement levels.

        Parameters
        ----------
        swing_high, swing_low : float
            The two anchors.
        direction : str
            ``"down"`` — move went high→low, retracements project *upward*.
            ``"up"``   — move went low→high, retracements project *downward*.

        Returns
        -------
        list[FibLevel]
            Sorted from lowest to highest price.
        """
        span = swing_high - swing_low
        levels: list[FibLevel] = []

        for ratio, label in self.RETRACEMENT_RATIOS.items():
            if direction == "down":
                price = swing_low + span * ratio
            else:
                price = swing_high - span * ratio
            levels.append(
                FibLevel(
                    ratio=ratio,
                    price=round(price, 2),
                    label=f"{label} retracement",
                    source=f"swing {swing_high:.2f}→{swing_low:.2f}",
                )
            )

        levels.sort(key=lambda lv: lv.price)
        return levels

    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------

    def calculate_extensions(
        self,
        wave1_start: float,
        wave1_end: float,
        wave2_end: float,
    ) -> list[FibLevel]:
        """Project wave-3/5 extension targets from wave-1 length.

        Parameters
        ----------
        wave1_start : float
            Price at wave 1 origin.
        wave1_end : float
            Price at wave 1 terminus.
        wave2_end : float
            Price at wave 2 terminus (launch point for wave 3).

        Returns
        -------
        list[FibLevel]
        """
        w1_length = abs(wave1_end - wave1_start)
        direction_down = wave1_end < wave1_start
        levels: list[FibLevel] = []

        for ratio, label in self.EXTENSION_RATIOS.items():
            if direction_down:
                price = wave2_end - w1_length * ratio
            else:
                price = wave2_end + w1_length * ratio
            levels.append(
                FibLevel(
                    ratio=ratio,
                    price=round(price, 2),
                    label=f"{label} extension",
                    source=(
                        f"W1 {wave1_start:.2f}→{wave1_end:.2f}, "
                        f"W2 end {wave2_end:.2f}"
                    ),
                )
            )

        levels.sort(key=lambda lv: lv.price)
        return levels

    # ------------------------------------------------------------------
    # Confluence detection
    # ------------------------------------------------------------------

    def find_fib_confluence(
        self,
        fib_sets: list[list[FibLevel]],
        tolerance: float = 0.50,
    ) -> list[ConfluenceZone]:
        """Find price zones where multiple Fibonacci levels cluster.

        Parameters
        ----------
        fib_sets : list[list[FibLevel]]
            Multiple sets of fib levels (retracements + extensions, or from
            different swings).
        tolerance : float
            Maximum dollar distance to treat two levels as confluent.

        Returns
        -------
        list[ConfluenceZone]
            Sorted by strength (most levels first), then by price.
        """
        # Flatten all levels
        all_levels: list[FibLevel] = []
        for s in fib_sets:
            all_levels.extend(s)
        if not all_levels:
            return []

        all_levels.sort(key=lambda lv: lv.price)

        zones: list[ConfluenceZone] = []
        used: set[int] = set()

        for i, anchor in enumerate(all_levels):
            if i in used:
                continue
            cluster = [anchor]
            used.add(i)
            for j in range(i + 1, len(all_levels)):
                if j in used:
                    continue
                if abs(all_levels[j].price - anchor.price) <= tolerance:
                    cluster.append(all_levels[j])
                    used.add(j)
                else:
                    break  # sorted — no further matches

            if len(cluster) >= 2:
                center = sum(lv.price for lv in cluster) / len(cluster)
                zones.append(
                    ConfluenceZone(
                        center_price=round(center, 2),
                        levels=cluster,
                        strength=len(cluster),
                    )
                )

        zones.sort(key=lambda z: (-z.strength, z.center_price))
        return zones
