"""Bridge classes.

The bridge is a passive shared resource: it has NO traffic light and takes
no decisions. It only exposes what a driver standing at the bridgehead can
observe (which direction is flowing, how many vehicles are on it, when the
last vehicle entered, how many vehicles are waiting on each side, how many
have crossed in the current "batch") plus a monitor (lock + condition) that
drivers use to consult that state atomically and to sleep while waiting.

All decisions ("do I cross now or do I wait?") live in the vehicle classes.
"""

from __future__ import annotations

import threading
from .clock import SimClock

NORTH = 0
SOUTH = 1
DIRECTION_NAME = {NORTH: "Norte->Sul", SOUTH: "Sul->Norte"}


def opposite(direction: int) -> int:
    return SOUTH if direction == NORTH else NORTH


class Ponte:
    """Main one-lane bridge (Tc = 5 s, Ts = 1 s, capacity 5 cars)."""

    def __init__(self, name: str, clock: SimClock,
                 crossing_time: float = 5.0, gap: float = 1.0,
                 truck_crossing_time: float = 10.0, allows_trucks: bool = True,
                 batch_size: int = 5, capacity: int | None = None,
                 lock=None):
        self.name = name
        self.clock = clock
        self.crossing_time = crossing_time          # Tc
        self.gap = gap                              # Ts
        self.truck_crossing_time = truck_crossing_time  # Tt
        self.allows_trucks = allows_trucks
        self.batch_size = batch_size                # P
        # How many vehicles fit at once. Tc / Ts for the main bridge = 5.
        self.capacity = capacity or int(crossing_time // gap)

        # Stage 4 shares one monitor between the two bridges, so a driver
        # in the single queue can observe both bridges atomically.
        self.lock = lock if lock is not None else threading.Lock()
        self.cond = threading.Condition(self.lock)

        # --- observable state (always accessed while holding self.lock) ---
        self.direction: int | None = None   # direction currently flowing
        self.on_bridge = 0                  # vehicles physically on the bridge
        self.truck_on_bridge = False
        self.last_entry_time = -1e9         # sim time of the last entry
        self.waiting = {NORTH: 0, SOUTH: 0}
        self.batch_count = 0                # vehicles that crossed in current batch
        self.batch_full = False             # P cars (or U=1 truck) already crossed
        # What a driver sees right after the bridge empties: who was flowing
        # and whether that flow had already completed a full batch.
        self.last_direction: int | None = None
        self.last_batch_full = False
        self.crossed = {NORTH: {"carro": 0, "caminhao": 0},
                        SOUTH: {"carro": 0, "caminhao": 0}}

        # --- statistics ---
        self.busy_time = 0.0
        self._busy_since: float | None = None

    # ---- helpers used by drivers while holding the lock ----

    def gap_remaining(self) -> float:
        """Seconds a driver still has to wait to respect Ts after the last entry."""
        return self.gap - (self.clock.now() - self.last_entry_time)

    def is_empty(self) -> bool:
        return self.on_bridge == 0

    def other_side_waiting(self, direction: int) -> bool:
        return self.waiting[opposite(direction)] > 0

    # ---- bookkeeping performed by the driver when entering / leaving ----

    def register_entry(self, direction: int, is_truck: bool) -> None:
        now = self.clock.now()
        if self.on_bridge == 0:
            self._busy_since = now
        self.on_bridge += 1
        self.direction = direction
        self.last_entry_time = now
        self.truck_on_bridge = is_truck
        if is_truck:
            self.batch_full = True          # U = 1 truck closes the batch
        else:
            self.batch_count += 1
            if self.batch_count >= self.batch_size:
                self.batch_full = True

    def register_exit(self, direction: int, is_truck: bool) -> None:
        self.on_bridge -= 1
        self.crossed[direction]["caminhao" if is_truck else "carro"] += 1
        if is_truck:
            self.truck_on_bridge = False
        if self.on_bridge == 0:
            self.busy_time += self.clock.now() - self._busy_since
            self._busy_since = None
            # Bridge is free. The bridge takes no decision: it just keeps
            # the observable facts (who was flowing, was the batch full)
            # and the drivers decide who goes next.
            self.last_direction = direction
            self.last_batch_full = self.batch_full
            self.direction = None
            self.batch_count = 0
            self.batch_full = False
        self.cond.notify_all()

    def utilization(self, total_time: float) -> float:
        busy = self.busy_time
        if self._busy_since is not None:
            busy += self.clock.now() - self._busy_since
        return busy / total_time if total_time > 0 else 0.0

    def total_crossed(self, direction: int) -> int:
        return sum(self.crossed[direction].values())


class PonteAntiga(Ponte):
    """Old parallel bridge (stage 4): cars only, Q = 2, Tc' = 4 s, Ts' = 2 s."""

    def __init__(self, clock: SimClock, batch_size: int = 5,
                 lock=None):
        super().__init__(name="Ponte Antiga", clock=clock, crossing_time=4.0,
                         gap=2.0, allows_trucks=False, batch_size=batch_size,
                         capacity=2, lock=lock)
