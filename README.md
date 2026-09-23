# Ponte de Faixa Única (One-Lane Bridge Problem)

Simulador concorrente em Python (biblioteca padrão) para as 4 etapas do trabalho.

```
python main.py --etapa 1                  # tempo real (para o vídeo)
python main.py --etapa 3 --escala 0.02    # 50x mais rápido, mesmas estatísticas
python main.py --etapa 4 --seed 1 --quiet # apenas as estatísticas finais
```

Estrutura:
- `one_lane_bridge/ponte.py`     — Ponte e PonteAntiga (estado observável + monitor)
- `one_lane_bridge/veiculos.py`  — Veiculo, Carro, Caminhao (a decisão do motorista)
- `one_lane_bridge/simulacao.py` — etapas, chegadas aleatórias e estatísticas
- `one_lane_bridge/clock.py`     — relógio simulado com fator de escala
- `main.py`                      — linha de comando
# Problema-Ponte-Faixa-Unica
