"""Simulation of the four stages of the One-Lane Bridge problem."""

from __future__ import annotations

import random
import threading
from collections import deque
from dataclasses import dataclass

from .clock import SimClock
from .ponte import Ponte, PonteAntiga, NORTH, SOUTH, DIRECTION_NAME
from .veiculos import Carro, Caminhao, Veiculo


@dataclass
class StageConfig:
    stage: int
    cars_per_direction: int
    trucks_per_direction: int
    avoid_starvation: bool
    old_bridge: bool
    arrival_min: float = 1.0   # Ta
    arrival_max: float = 3.0
    batch_size: int = 5        # P


STAGES = {
    1: StageConfig(1, 50, 0, avoid_starvation=False, old_bridge=False),
    2: StageConfig(2, 50, 0, avoid_starvation=True, old_bridge=False),
    3: StageConfig(3, 50, 5, avoid_starvation=True, old_bridge=False),
    4: StageConfig(4, 60, 5, avoid_starvation=True, old_bridge=True),
}


class Simulacao:
    def __init__(self, config: StageConfig, scale: float = 1.0,
                 seed: int | None = None, verbose: bool = True):
        self.config = config
        self.clock = SimClock(scale)
        self.verbose = verbose
        self.rng = random.Random(seed)
        self._print_lock = threading.Lock()

        main = Ponte("Ponte Principal", self.clock, batch_size=config.batch_size)
        self.bridges: list[Ponte] = [main]
        if config.old_bridge:
            self.bridges.append(PonteAntiga(self.clock, config.batch_size,
                                            lock=main.lock))
        self.vehicles: list[Veiculo] = []
        # One FIFO queue per direction, shared by all bridges (stage 4).
        self.queues = {NORTH: deque(), SOUTH: deque()}

    def log(self, msg: str) -> None:
        if self.verbose:
            with self._print_lock:
                print(msg, flush=True)

    # ------------------------------------------------------------------

    def _arrivals(self, direction: int, start_id: int) -> None:
        """One generator thread per direction: vehicles arrive one after
        another with a random interval Ta in [1, 3] s."""
        kinds = (["carro"] * self.config.cars_per_direction
                 + ["caminhao"] * self.config.trucks_per_direction)
        self.rng.shuffle(kinds)
        vid = start_id
        for kind in kinds:
            self.clock.sleep(self.rng.uniform(self.config.arrival_min,
                                              self.config.arrival_max))
            cls = Caminhao if kind == "caminhao" else Carro
            v = cls(vid, direction, self.bridges, self.queues,
                    self.config.avoid_starvation, self.log)
            with self._print_lock:
                self.vehicles.append(v)
            v.start()
            vid += 1

    def run(self) -> dict:
        self.log(f"=== Etapa {self.config.stage}: {self.config.cars_per_direction} carros "
                 f"e {self.config.trucks_per_direction} caminhões por sentido ===")
        gens = [threading.Thread(target=self._arrivals, args=(NORTH, 1)),
                threading.Thread(target=self._arrivals, args=(SOUTH, 1000))]
        for g in gens:
            g.start()
        for g in gens:
            g.join()
        for v in list(self.vehicles):
            v.join()
        total_time = self.clock.now()
        return self.statistics(total_time)

    # ------------------------------------------------------------------

    def statistics(self, total_time: float) -> dict:
        waits = [v.wait_time for v in self.vehicles]
        stats = {
            "stage": self.config.stage,
            "total_time": total_time,
            "crossed": {},
            "wait_min": min(waits),
            "wait_max": max(waits),
            "wait_avg": sum(waits) / len(waits),
            "wait_by_kind": {},
            "utilization": {},
        }
        for d in (NORTH, SOUTH):
            cars = sum(1 for v in self.vehicles if v.direction == d and not v.is_truck)
            trucks = sum(1 for v in self.vehicles if v.direction == d and v.is_truck)
            stats["crossed"][DIRECTION_NAME[d]] = {"carros": cars, "caminhoes": trucks}
        for kind in ("carro", "caminhao"):
            ws = [v.wait_time for v in self.vehicles if v.kind == kind]
            if ws:
                stats["wait_by_kind"][kind] = {
                    "min": min(ws), "max": max(ws), "avg": sum(ws) / len(ws)}
        for b in self.bridges:
            stats["utilization"][b.name] = {
                "busy": b.busy_time,
                "ratio": b.utilization(total_time),
                "crossed": {DIRECTION_NAME[d]: dict(b.crossed[d]) for d in (NORTH, SOUTH)},
            }
        return stats


def print_statistics(stats: dict) -> None:
    print()
    print("=" * 64)
    print(f"ESTATÍSTICAS FINAIS — Etapa {stats['stage']}")
    print("=" * 64)
    print("1) Veículos que cruzaram por sentido:")
    for d, c in stats["crossed"].items():
        print(f"   {d:12s}: {c['carros']:3d} carros, {c['caminhoes']:2d} caminhões")
    print("2) Tempo de espera na fila:")
    print(f"   mínimo = {stats['wait_min']:.2f}s  máximo = {stats['wait_max']:.2f}s  "
          f"médio = {stats['wait_avg']:.2f}s")
    for kind, w in stats["wait_by_kind"].items():
        print(f"   ({kind:8s}) mín={w['min']:.2f}s  máx={w['max']:.2f}s  méd={w['avg']:.2f}s")
    print("3) Utilização da(s) ponte(s):")
    for name, u in stats["utilization"].items():
        print(f"   {name}: {u['busy']:.1f}s ocupada de {stats['total_time']:.1f}s "
              f"totais = {u['ratio'] * 100:.1f}%")
        for d, c in u["crossed"].items():
            print(f"      {d:12s}: {c['carro']:3d} carros, {c['caminhao']:2d} caminhões")
    print(f"Tempo total de simulação: {stats['total_time']:.1f}s")
    print("=" * 64)
