# main.py – MasterDex FastAPI (Dexscreener)
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import httpx

from setup_logic import compute_signals, render_chart_png

DEX_API_BASE = "https://api.dexscreener.com"
app = FastAPI(title="MasterDex API", version="1.1.0")

# CORS liberado (frontend e extensões)
app.add_middleware(
   CORSMiddleware,
   allow_origins=["*"], allow_credentials=True,
   allow_methods=["*"], allow_headers=["*"],
)

CHAINS_ALL = ["solana","bsc","eth","base","polygon","arbitrum","avax","fantom","optimism","ton","osmosis"]


# ---------- Utils HTTP ----------

async def get_json(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
   r = await client.get(url, timeout=20.0)
   r.raise_for_status()
   return r.json()


# ---------- Endpoints básicos ----------

@app.get("/status")
async def status():
   return {"status": "MasterDex API, running"}


@app.get("/pairs")
async def pairs(
   query: Optional[str] = Query(default=None, description="Busca livre por token/chain"),
   chain: Optional[str] = Query(default=None, description="Filtra por chain ex.: solana"),
   limit: int = Query(default=30, ge=1, le=200)
):
   """
   Lista pares/tokens (search). Usamos /latest/dex/search?q=...
   """
   async with httpx.AsyncClient() as client:
       try:
           if query:
               url = f"{DEX_API_BASE}/latest/dex/search?q={query}"
           elif chain:
               # fallback simples: busca por chain no search
               url = f"{DEX_API_BASE}/latest/dex/search?q={chain}"
           else:
               url = f"{DEX_API_BASE}/latest/dex/search?q=solana"

           data = await get_json(client, url)
           results = data.get("pairs") or data.get("tokens") or data.get("results") or []
           return {"success": True, "query": query or chain, "results": min(limit, len(results)), "data": results[:limit]}
       except httpx.HTTPStatusError as e:
           return JSONResponse(status_code=502, content={"success": False, "error": f"Erro HTTP {e.response.status_code} ao acessar {url}"})


# ---------- Candles + sinais ----------

async def fetch_candles(
   client: httpx.AsyncClient,
   chain: str,
   pair: str,
   timeframe: str = "5m",
   limit: int = 300
) -> Dict[str, List]:
   """
   Candles da Dexscreener:
   /latest/dex/candles/{chain}/{pair}?timeframe=5m&limit=300
   Retorna lists: times (ms) e closes.
   """
   url = f"{DEX_API_BASE}/latest/dex/candles/{chain}/{pair}?timeframe={timeframe}&limit={limit}"
   r = await client.get(url, timeout=20.0)
   r.raise_for_status()
   js = r.json()
   candles = js.get("candles", [])
   times = [c["t"] for c in candles]
   closes = [float(c["c"]) for c in candles]
   return {"times": times, "closes": closes}


@app.get("/signals")
async def signals(
   chain: str = Query(..., description="Ex: solana"),
   pair: str = Query(..., description="pairAddress / pairId"),
   fast: int = Query(7, ge=2, le=200),
   slow: int = Query(21, ge=2, le=400),
   timeframe: str = Query("5m")
):
   """Retorna EMAs e sinal de cruzamento (JSON)."""
   async with httpx.AsyncClient() as client:
       try:
           series = await fetch_candles(client, chain, pair, timeframe=timeframe)
       except httpx.HTTPStatusError as e:
           raise HTTPException(status_code=502, detail=f"Candles não encontrados ({e.response.status_code}). Verifique chain/pair/timeframe.")

   prices = series["closes"]
   out = compute_signals(prices, fast=fast, slow=slow, pre_bars=5)
   return {
       "success": True,
       "length": len(prices),
       "fast": fast, "slow": slow, "timeframe": timeframe,
       "cross": out["cross"],
       "pre_alert": out["pre_alert"]
   }


@app.get("/chart")
async def chart(
   chain: str = Query(..., description="Ex: solana"),
   pair: str = Query(..., description="pairAddress / pairId"),
   fast: int = Query(7, ge=2, le=200),
   slow: int = Query(21, ge=2, le=400),
   timeframe: str = Query("5m")
):
   """
   PNG com preço + EMA rápida/lenta + marcações de cruzamento e pré-alerta.
   Use no navegador:
     /chart?chain=solana&pair=<PAIR_ADDRESS>&timeframe=5m
   """
   async with httpx.AsyncClient() as client:
       try:
           series = await fetch_candles(client, chain, pair, timeframe=timeframe)
       except httpx.HTTPStatusError as e:
           raise HTTPException(status_code=502, detail=f"Candles não encontrados ({e.response.status_code}). Verifique chain/pair/timeframe.")

   png = render_chart_png(
       times=series["times"],
       prices=series["closes"],
       fast=fast,
       slow=slow,
       title=f"{chain.upper()} • {pair} • TF {timeframe}  –  EMA {fast}/{slow}"
   )
   return Response(content=png, media_type="image/png")