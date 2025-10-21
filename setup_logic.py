# setup_logic.py
# Cálculo de EMAs, detecção de cruzamentos e render do gráfico (PNG)

from typing import List, Dict, Any, Optional, Tuple
from io import BytesIO
import math
import datetime as dt

import matplotlib
matplotlib.use("Agg")  # backend "headless" para servidores
import matplotlib.pyplot as plt


# ---------- Cálculos base ----------

def ema(series: List[float], period: int) -> List[float]:
    """EMA clássica (sem pandas)."""
    if period <= 1 or len(series) == 0:
        return series[:]
    k = 2.0 / (period + 1.0)
    out: List[float] = []
    ema_prev: Optional[float] = None
    for v in series:
        if ema_prev is None:
            ema_prev = v  # seed pela 1ª leitura
        else:
            ema_prev = v * k + ema_prev * (1.0 - k)
        out.append(ema_prev)
    return out


def _sign(x: float) -> int:
    # retorna 1, 0, -1
    return 1 if x > 0 else (-1 if x < 0 else 0)


def compute_signals(
    prices: List[float],
    fast: int = 7,
    slow: int = 21,
    pre_bars: int = 5
) -> Dict[str, Any]:
    """Calcula EMAs, detecta cruzamento mais recente e projeta pré-alerta."""
    if len(prices) < max(fast, slow) + 3:
        return {
            "ema_fast": [],
            "ema_slow": [],
            "cross": None,
            "pre_alert": None,
            "diff": [],
        }

    ef = ema(prices, fast)
    es = ema(prices, slow)

    # Série diferença (para slope)
    diff = [a - b for a, b in zip(ef, es)]

    # Sinal antes e agora
    f2, f1 = ef[-2], ef[-1]
    s2, s1 = es[-2], es[-1]
    sign_prev = _sign(f2 - s2)
    sign_now = _sign(f1 - s1)

    cross: Optional[Dict[str, Any]] = None
    if sign_prev != 0 and sign_now != sign_prev:
        cross = {"side": "buy" if sign_now > 0 else "sell", "index": len(prices) - 1}

    # Pré-alerta: previsão linear de quando a diff cruza 0
    pre_alert: Optional[Dict[str, Any]] = None
    df_now = diff[-1]
    slope = diff[-1] - diff[-2]
    if slope != 0:
        bars_to_cross = -df_now / slope
        # Considera apenas cruzamento futuro, dentro da janela desejada
        if 0 < bars_to_cross <= pre_bars:
            pre_alert = {
                "in_bars": float(bars_to_cross),
                "side": "buy" if slope > 0 else "sell",
            }

    return {
        "ema_fast": ef,
        "ema_slow": es,
        "cross": cross,
        "pre_alert": pre_alert,
        "diff": diff,
    }


# ---------- Render gráfico ----------

def render_chart_png(
    times: List[int],            # timestamps em ms
    prices: List[float],
    fast: int,
    slow: int,
    title: str = "MasterDex – Setup Precioso"
) -> bytes:
    """
    Gera PNG do gráfico com:
      - Preço (linha)
      - EMA rápida (amarelo)
      - EMA lenta (vermelho)
      - Marcações de cruzamentos
    """
    sig = compute_signals(prices, fast=fast, slow=slow, pre_bars=5)
    ef, es = sig["ema_fast"], sig["ema_slow"]

    # Converte timestamps para datetime
    xs = [dt.datetime.utcfromtimestamp(t / 1000.0) for t in times]

    fig = plt.figure(figsize=(12, 5), dpi=130)
    ax = plt.gca()

    # preço
    ax.plot(xs, prices, linewidth=1.3, label="Preço", color="#1f77b4")
    # EMAs
    ax.plot(xs, ef, linewidth=2.0, label=f"EMA {fast}", color="#f2c94c")   # amarelo
    ax.plot(xs, es, linewidth=2.0, label=f"EMA {slow}", color="#eb5757")   # vermelho

    # Cruzamento mais recente (se houver)
    if sig["cross"]:
        idx = sig["cross"]["index"]
        side = sig["cross"]["side"]
        color = "#27ae60" if side == "buy" else "#c0392b"
        ax.scatter([xs[idx]], [prices[idx]], s=80, color=color, zorder=5)
        ax.annotate(
            f"{'BUY' if side=='buy' else 'SELL'}",
            (xs[idx], prices[idx]),
            textcoords="offset points",
            xytext=(0, -18 if side == 'buy' else 18),
            ha="center",
            color=color,
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=1),
        )

    # Pré-alerta (marcador no futuro do eixo X)
    if sig["pre_alert"]:
        bars = sig["pre_alert"]["in_bars"]
        side = sig["pre_alert"]["side"]
        # projeta posição X futura
        if len(xs) >= 2:
            # distância média entre barras
            dt_bar = (xs[-1] - xs[-2]).total_seconds()
            t_future = xs[-1] + dt.timedelta(seconds=dt_bar * bars)
            color = "#2ecc71" if side == "buy" else "#e74c3c"
            ax.axvline(t_future, linestyle="--", color=color, alpha=0.6)
            ax.text(
                t_future, ax.get_ylim()[1],
                f"Pré-alerta {side.upper()} ~{bars:.1f} barras",
                rotation=90, va="top", ha="right", color=color, fontsize=8
            )

    ax.set_title(title)
    ax.set_xlabel("Tempo (UTC)")
    ax.set_ylabel("Preço")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()