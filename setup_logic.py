# setup_logic.py — MasterDex core (DexScreener)
from typing import List, Dict, Any
import math

def ema(series: List[float], period: int) -> List[float]:
    if not series or period <= 0:
        return []
    k = 2 / (period + 1)
    out = [float(series[0])]
    prev = out[0]
    for i in range(1, len(series)):
        val = float(series[i]) * k + prev * (1 - k)
        out.append(val); prev = val
    return out

def compute_signals(prices: List[float], fast:int=7, slow:int=21, pre_bars:int=5) -> Dict[str, Any]:
    if len(prices) < max(fast, slow) + 3:
        return {"ema_fast": [], "ema_slow": [], "cross": None, "pre_alert": None}
    ef = ema(prices, fast)
    es = ema(prices, slow)
    f2, f1 = ef[-1], ef[-2]
    s2, s1 = es[-1], es[-2]

    # Crossover detection
    sign_prev = 1 if (f1 - s1) > 0 else (-1 if (f1 - s1) < 0) else 0
    sign_now  = 1 if (f2 - s2) > 0 else (-1 if (f2 - s2) < 0) else 0
    cross = None
    if sign_prev != 0 and sign_now != sign_prev:
        cross = "buy" if (sign_now > 0) else "sell"

    # Pre-alert: linear projection for N bars ahead
    df_now = f2 - s2
    slope = (f2 - f1) - (s2 - s1)
    pre_alert = None
    if slope != 0:
        bars_to_cross = -df_now / slope
        if 0 < bars_to_cross <= pre_bars:
            pre_alert = "buy" if slope > 0 else "sell"

    return {"ema_fast": ef, "ema_slow": es, "cross": cross, "pre_alert": pre_alert}
