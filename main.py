"""One-Lane Bridge Problem — entry point.

Usage:
    python main.py --etapa 3               # real-time run (for the video)
    python main.py --etapa 4 --escala 0.05 # 20x faster, for statistics
    python main.py --etapa 2 --seed 42 --quiet
"""

from __future__ import annotations

import argparse
from one_lane_bridge.simulacao import STAGES, Simulacao, print_statistics


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador da ponte de faixa única")
    parser.add_argument("--etapa", type=int, choices=STAGES.keys(), default=1,
                        help="etapa do problema (1 a 4)")
    parser.add_argument("--escala", type=float, default=1.0,
                        help="fator de escala do tempo (1.0 = tempo real; 0.1 = 10x mais rápido)")
    parser.add_argument("--seed", type=int, default=None,
                        help="semente do gerador aleatório (reprodutibilidade)")
    parser.add_argument("--quiet", action="store_true",
                        help="não imprime os eventos, apenas as estatísticas")
    args = parser.parse_args()

    sim = Simulacao(STAGES[args.etapa], scale=args.escala,
                    seed=args.seed, verbose=not args.quiet)
    stats = sim.run()
    print_statistics(stats)


if __name__ == "__main__":
    main()
