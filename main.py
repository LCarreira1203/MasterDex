# main.py — MasterDex backend (DexScreener integration)
# Desenvolvido por L. Carreira & Jarvis

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import List, Dict, Any
from setup_logic import compute_signals

# Base da API da Dexscreener
DEX_API_BASE = "https://api.dexscreener.com"

# Inicialização da aplicação FastAPI
app = FastAPI(title="MasterDex API", version="1.0.0")

# Middleware CORS (permite acesso de qualquer origem)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoint de status (verificação do servidor) ---
@app.get("/status")
def get_status():
    return {"status": "MasterDex API running"}


# --- Cadeias suportadas ---
CHAINS_ALL = [
    "solana", "bsc", "eth", "base",
    "polygon", "arbitrum", "avax",
    "fantom", "optimism", "ton"
]


# --- Endpoint: buscar pares por rede ---
@app.get("/pairs")
async def fetch_pairs(chain: str = Query("solana", description="Nome da blockchain")) -> Dict[str, Any]:
    """
    Retorna os pares (tokens) mais recentes de uma blockchain específica,
    puxados da API Dexscreener.
    """
    async with httpx.AsyncClient() as client:
        url = f"{DEX_API_BASE}/latest/dex/pairs/{chain}"
        response = await client.get(url, timeout=20.0)
        response.raise_for_status()
        data = response.json()
    return {"chain": chain, "pairs": data}


# --- Endpoint: aplicar sinais técnicos (Setup Precioso) ---
@app.get("/signals")
async def get_signals(
    prices: List[float] = Query(..., description="Lista de preços do ativo"),
    fast: int = Query(7, description="Período da média rápida"),
    slow: int = Query(21, description="Período da média lenta"),
    pre_bars: int = Query(5, description="Barras de pré-alerta")
):
    """
    Retorna os sinais do Setup Precioso baseados nos preços informados.
    """
    try:
        result = compute_signals(prices, fast, slow, pre_bars)
        return {"success": True, "signals": result}
    except Exception as e:
        return {"success": False, "error": str(e)}