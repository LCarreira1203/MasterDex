# main.py — MasterDex backend (DexScreener integration)
# Desenvolvido por L. Carreira & Jarvis

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import List, Dict, Any
from setup_logic import compute_signals

DEX_API_BASE = "https://api.dexscreener.com"
app = FastAPI(title="MasterDex API", version="1.0.2")

# Configurações CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoint de status ---
@app.get("/status")
def get_status():
    return {"status": "MasterDex API running"}

# --- Endpoint para buscar memecoins ou pares ---
@app.get("/pairs")
async def fetch_pairs(query: str = Query("solana", description="Busca por token ou rede")) -> Dict[str, Any]:
    """
    Busca pares e tokens por nome ou símbolo.
    Exemplo: /pairs?query=solana
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{DEX_API_BASE}/latest/dex/search?q={query}"
            response = await client.get(url, timeout=20.0)
            response.raise_for_status()
            data = response.json()

        return {
            "success": True,
            "query": query,
            "results": len(data.get("pairs", [])),
            "data": data.get("pairs", [])
        }

    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"Erro HTTP {e.response.status_code} ao acessar {url}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- Endpoint de sinais técnicos (Setup Precioso) ---
@app.get("/signals")
async def get_signals(
    prices: List[float] = Query(..., description="Lista de preços"),
    fast: int = Query(7, description="Período EMA rápida"),
    slow: int = Query(21, description="Período EMA lenta"),
    pre_bars: int = Query(5, description="Pré-alerta em barras")
):
    try:
        result = compute_signals(prices, fast, slow, pre_bars)
        return {"success": True, "signals": result}
    except Exception as e:
        return {"success": False, "error": str(e)}