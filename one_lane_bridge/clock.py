"""Simulated clock.

All durations in the problem statement are given in seconds. To make the
simulation faster (e.g. when generating statistics) a scale factor can be
applied: sleep(5) with scale 0.1 takes 0.5 s of wall time, but the clock
still reports 5 simulated seconds. With scale = 1.0 the simulation runs in
real time, as required for the demonstration video.
"""

from __future__ import annotations

import time


class SimClock:
    def __init__(self, scale: float = 1.0):
        self.scale = scale
        self._start = time.monotonic()

    def now(self) -> float:
        """Simulated seconds elapsed since the clock was created."""
        return (time.monotonic() - self._start) / self.scale

    def sleep(self, seconds: float) -> None:
        """Sleep for `seconds` simulated seconds."""
        if seconds > 0:
            time.sleep(seconds * self.scale)

    def to_wall(self, seconds: float) -> float:
        """Convert simulated seconds into wall-clock seconds (for timeouts)."""
        return seconds * self.scale
