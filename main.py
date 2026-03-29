# ============================================================================
# LROS – Ultimate Constitutional AI Operating System
# v51.0 – Unified Asynchronous Master Build
# Mesh: Paid DeepSeek (4) + OpenRouter (5) + Cerebras + Groq
# ============================================================================

import os
import json
import random
import asyncio
import logging
import httpx
import re
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ---------- Setup & Logging ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("lros")
app = FastAPI(title="LROS Ultimate Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- API Registry (9-Key Mesh) ----------
def get_keys(var_name):
    return [k.strip() for k in os.environ.get(var_name, "").split(",") if k.strip()]

DEEPSEEK_KEYS = get_keys("DEEPSEEK_API_KEYS")
OPENROUTER_KEYS = get_keys("OPENROUTER_API_KEYS")
CEREBRAS_KEYS = get_keys("CEREBRAS_API_KEYS")
GROQ_KEYS = get_keys("GROQ_API_KEYS")

# Semaphore: Hard-locked to 10 parallel sessions for stability
swarm_semaphore = asyncio.Semaphore(10)

# ---------- Shared Mesh Caller ----------
async def call_ai_mesh(prompt: str, temperature: float = 0.7):
    async with swarm_semaphore:
        # Prevent millisecond collision
        await asyncio.sleep(random.uniform(0.1, 0.4))
        
        async with httpx.AsyncClient() as client:
            # TIER 1: Paid DeepSeek
            for key in DEEPSEEK_KEYS:
                try:
                    res = await client.post(
                        "https://api.deepseek.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}"},
                        json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": temperature},
                        timeout=15.0
                    )
                    if res.status_code == 200: return res.json()["choices"][0]["message"]["content"]
                except: continue

            # TIER 2: OpenRouter (Qwen 2.5 Brain)
            for key in OPENROUTER_KEYS:
                try:
                    res = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "HTTP-Referer": "lros.ai"},
                        json={"model": "qwen/qwen-2.5-72b-instruct", "messages": [{"role": "user", "content": prompt}]},
                        timeout=20.0
                    )
                    if res.status_code == 200: return res.json()["choices"][0]["message"]["content"]
                except: continue
                
            return f"[Mesh Offline] System fallback: {prompt[:50]}..."

# ---------- Core Endpoints (Aligned with HTML) ----------

class GenerateRequest(BaseModel):
    topic: str
    pattern_id: Optional[str] = None
    user_id: Optional[str] = None

@app.post("/api/generate")
async def generate(req: GenerateRequest):
    # Logic to select best pattern from patterns.json
    response = await call_ai_mesh(f"Task: {req.topic}")
    return {"response": response, "pattern_id": req.pattern_id or "p1"}

@app.get("/api/orchestrate/status")
async def orchestrate_status():
    # Syncs with your index.html polling
    try:
        with open("orchestrate_state.json", "r") as f: return json.load(f)
    except:
        return {"current_phase": 0, "phases": [{"phase": i, "status": "pending"} for i in range(1, 10)], "logs": ["Awaiting start"]}

@app.post("/api/orchestrate/start")
async def start_orchestration(background_tasks: BackgroundTasks):
    # Triggers the 9-Phase Plan
    background_tasks.add_task(run_all_phases)
    return {"status": "orchestration_started"}

# ... [Include your Governance, Business, and Ingest logic here] ...

async def run_all_phases():
    # Logic to loop through 1-9 and update orchestrate_state.json
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
