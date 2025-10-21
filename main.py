# main.py — MasterDex FastAPI backend (DexScreener only)
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import List, Dict, Any
from setup_logic import compute_signals

DEX_API_BASE = "https://api.dexscreener.com"
app = FastAPI(title="MasterDex API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CHAINS_ALL = ["solana","bsc","eth","base","polygon","arbitrum","avax","fantom","optimism","ton"]

async def fetch_pairs(client:httpx.AsyncClient, chain:str) -> List[Dict[str,Any]]:
    url = f"{DEX_API_BASE}/latest/dex/pairs/{chain}"
    r = await client.get(url, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    return data.get("pairs", [])

@app.get("/api/top")
async def api_top(
    chain: str = Query("all"),
    limit: int = Query(20, ge=1, le=200),
    min_liquidity_usd: float = Query(0.0, ge=0.0),
    min_volume_24h_usd: float = Query(0.0, ge=0.0),
    sort: str = Query("change24h")
):
    chains = CHAINS_ALL if chain == "all" else [chain]
    out = []
    async with httpx.AsyncClient() as client:
        for ch in chains:
            try:
                pairs = await fetch_pairs(client, ch)
                for p in pairs:
                    liq = float(p.get("liquidity",{}).get("usd",0) or 0)
                    vol = float(p.get("volume",{}).get("h24",0) or 0)
                    change = float(p.get("priceChange",{}).get("h24",0) or 0)
                    out.append({
                        "chain": p.get("chainId"),
                        "pairAddress": p.get("pairAddress"),
                        "baseToken": p.get("baseToken",{}),
                        "quoteToken": p.get("quoteToken",{}),
                        "priceUsd": p.get("priceUsd"),
                        "txns": p.get("txns",{}),
                        "liquidity": liq,
                        "volume24h": vol,
                        "change24h": change,
                        "url": p.get("url"),
                        "sparkline": p.get("priceChange",{}).get("series") or p.get("sparkline"),
                    })
            except Exception:
                continue
    key = {"change24h":"change24h","volume24h":"volume24h","liquidity":"liquidity"}.get(sort,"change24h")
    out.sort(key=lambda x: float(x.get(key,0) or 0), reverse=True)
    return {"count": len(out[:limit]), "items": out[:limit]}

@app.get("/api/signal")
async def api_signal(
    chain: str,
    pairAddress: str,
    fast: int = 7,
    slow: int = 21,
    pre_bars: int = 5
):
    url = f"{DEX_API_BASE}/latest/dex/pairs/{chain}/{pairAddress}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=20.0)
        r.raise_for_status()
        data = r.json()
    pairs = data.get("pairs", [])
    if not pairs:
        return {"ok": False, "reason": "pair-not-found"}
    p = pairs[0]
    series = p.get("priceChange",{}).get("series") or p.get("sparkline")
    if not series or len(series) < max(fast, slow) + 3:
        return {"ok": False, "reason": "no-series"}
    prices = [float(x) for x in series if x is not None]
    sig = compute_signals(prices, fast=fast, slow=slow, pre_bars=pre_bars)
    return {
        "ok": True,
        "pair": {
            "name": f"{p.get('baseToken',{}).get('symbol','?')}/{p.get('quoteToken',{}).get('symbol','?')}",
            "priceUsd": p.get("priceUsd"),
            "url": p.get("url"),
            "chain": p.get("chainId"),
        },
        "prices": prices[-300:],
        "ema_fast": sig["ema_fast"][-300:],
        "ema_slow": sig["ema_slow"][-300:],
        "cross": sig["cross"],
        "pre_alert": sig["pre_alert"]
    }
