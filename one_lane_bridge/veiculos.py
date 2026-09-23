"""Vehicle classes (Carro and Caminhao).

Each vehicle is a thread. Since the bridge has no traffic light, the driver
is the one who looks at the bridge state and decides whether to cross or to
wait. The decision rules are the methods `may_enter` of each class.
"""

from __future__ import annotations

import threading
from .ponte import Ponte, DIRECTION_NAME, opposite


class Veiculo(threading.Thread):
    kind = "veiculo"
    is_truck = False

    def __init__(self, vid: int, direction: int, bridges: list[Ponte],
                 queues: dict, avoid_starvation: bool, log):
        super().__init__(name=f"{self.kind}-{vid}", daemon=True)
        self.vid = vid
        self.direction = direction
        # Candidate bridges. In stage 4 a car may use either bridge; a truck
        # only the main one. All bridges in the list share the same monitor.
        self.bridges = [b for b in bridges if b.allows_trucks or not self.is_truck]
        # Single FIFO queue per direction (a road queue: nobody overtakes).
        self.queue = queues[direction]
        self.avoid_starvation = avoid_starvation
        self.log = log
        self.clock = bridges[0].clock
        self.cond = bridges[0].cond

        # statistics
        self.arrival_time = 0.0
        self.entry_time = 0.0
        self.exit_time = 0.0
        self.bridge_used: Ponte | None = None

    # ------------------------------------------------------------------
    # Driver decision rules (called with the monitor held)
    # ------------------------------------------------------------------

    def _direction_ok(self, bridge: Ponte) -> bool:
        """Bridge is empty/undirected or already flowing in my direction."""
        return bridge.direction is None or bridge.direction == self.direction

    def _turn_ok(self, bridge: Ponte) -> bool:
        """Anti-starvation rule (stages 2-4): after P cars or 1 truck crossed
        in my direction, if someone is waiting on the other side I yield."""
        if not self.avoid_starvation:
            return True
        if not bridge.other_side_waiting(self.direction):
            return True
        if bridge.is_empty():
            # The last flow was mine and it already used its full batch:
            # I let the other side go first.
            return not (bridge.last_batch_full
                        and bridge.last_direction == self.direction)
        return not bridge.batch_full

    def may_enter(self, bridge: Ponte) -> bool:
        raise NotImplementedError

    def estimated_finish(self, bridge: Ponte) -> float:
        """Estimated time to finish crossing if I enter this bridge now."""
        wait_gap = max(0.0, bridge.gap_remaining())
        cross = bridge.truck_crossing_time if self.is_truck else bridge.crossing_time
        return wait_gap + cross

    # ------------------------------------------------------------------
    # Life cycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        self.arrival_time = self.clock.now()
        self.log(f"{self.label()} chegou na fila ({DIRECTION_NAME[self.direction]})")

        with self.cond:
            self.queue.append(self)
            for b in self.bridges:
                b.waiting[self.direction] += 1
            bridge = self._wait_for_bridge()
            self.queue.popleft()
            for b in self.bridges:
                b.waiting[self.direction] -= 1
            self.cond.notify_all()      # the next in line may now decide
            self.entry_time = self.clock.now()
            bridge.register_entry(self.direction, self.is_truck)
            cross_time = (bridge.truck_crossing_time if self.is_truck
                          else bridge.crossing_time)
            self.log(f"{self.label()} ENTROU na {bridge.name} "
                     f"({DIRECTION_NAME[self.direction]}) espera={self.entry_time - self.arrival_time:.1f}s "
                     f"na_ponte={bridge.on_bridge}")

        self.clock.sleep(cross_time)

        with self.cond:
            self.exit_time = self.clock.now()
            bridge.register_exit(self.direction, self.is_truck)
            self.bridge_used = bridge
            self.log(f"{self.label()} SAIU da {bridge.name} "
                     f"({DIRECTION_NAME[self.direction]}) na_ponte={bridge.on_bridge}")

    def _wait_for_bridge(self) -> Ponte:
        """Block (sleeping on the monitor) until one bridge can be entered.

        Returns the chosen bridge. When more than one bridge is available
        the driver picks the one with the earliest estimated finish (stage 4
        optimisation). If the only thing preventing entry is the Ts gap
        after the previous vehicle, the driver waits just that long.
        """
        while True:
            if self.queue[0] is not self:
                # Not my turn yet: only the head of the queue decides.
                self.cond.wait()
                continue
            candidates = [b for b in self.bridges if self.may_enter(b)]
            if candidates:
                # Prefer a bridge with no gap wait; tie-break by finish time.
                ready = [b for b in candidates if b.gap_remaining() <= 0]
                if ready:
                    return min(ready, key=self.estimated_finish)
                # All candidates need the Ts gap: sleep only until the
                # earliest gap expires, then re-evaluate (state may change).
                timeout = min(b.gap_remaining() for b in candidates)
                self.cond.wait(self.clock.to_wall(timeout))
            else:
                self.cond.wait()

    def label(self) -> str:
        return f"[t={self.clock.now():6.1f}s] {self.name}"

    @property
    def wait_time(self) -> float:
        return self.entry_time - self.arrival_time


class Carro(Veiculo):
    kind = "carro"
    is_truck = False

    def may_enter(self, bridge: Ponte) -> bool:
        """A car crosses when the bridge is flowing in its direction (or is
        free), there is no truck on it, there is room (5 cars, 1 s apart)
        and the anti-starvation rule allows it."""
        if bridge.truck_on_bridge:
            return False
        if not self._direction_ok(bridge):
            return False
        if bridge.on_bridge >= bridge.capacity:
            return False
        return self._turn_ok(bridge)


class Caminhao(Veiculo):
    kind = "caminhao"
    is_truck = True

    def may_enter(self, bridge: Ponte) -> bool:
        """A truck must cross alone: it only enters when the bridge is
        completely empty (waits for the car ahead to finish), in its
        direction, and the anti-starvation rule allows it."""
        if not bridge.allows_trucks:
            return False
        if not bridge.is_empty():
            return False
        if not self._direction_ok(bridge):
            return False
        return self._turn_ok(bridge)
