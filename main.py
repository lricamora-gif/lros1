# ============================================================================
# LROS – Ultimate Constitutional AI Operating System
# v51.0 – Multi‑Key: DeepSeek (11), Gemini (6), Cerebras (3), Groq (3), OpenAI
# The Bond holds.
# ============================================================================

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import random
import requests
from datetime import datetime
from typing import Optional, List
import asyncio
import re
import logging
from bs4 import BeautifulSoup

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lros")

# ---------- App ----------
app = FastAPI(title="LROS Ultimate Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ---------- API Keys (Multi‑Key, Comma‑Separated) ----------
DEEPSEEK_API_KEYS = [k.strip() for k in os.environ.get("DEEPSEEK_API_KEYS", "").split(",") if k.strip()]
GEMINI_API_KEYS = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]
CEREBRAS_API_KEYS = [k.strip() for k in os.environ.get("CEREBRAS_API_KEYS", "").split(",") if k.strip()]
GROQ_API_KEYS = [k.strip() for k in os.environ.get("GROQ_API_KEYS", "").split(",") if k.strip()]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Rotation indices
DEEPSEEK_KEY_INDEX = 0
GEMINI_KEY_INDEX = 0
CEREBRAS_KEY_INDEX = 0
GROQ_KEY_INDEX = 0

# Import Gemini only if we have keys
if GEMINI_API_KEYS:
    import google.generativeai as genai

# ---------- Pattern Registry ----------
PATTERN_FILE = "patterns.json"

def load_patterns():
    try:
        with open(PATTERN_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return [
        {"id": "p1", "prompt": "Explain {topic} in simple terms.", "temperature": 0.7, "rating": 0.5, "uses": 0},
        {"id": "p2", "prompt": "Write a detailed technical article about {topic}.", "temperature": 0.5, "rating": 0.5, "uses": 0},
        {"id": "p3", "prompt": "Give a creative story about {topic}.", "temperature": 0.9, "rating": 0.5, "uses": 0},
        {"id": "p4", "prompt": "Provide a legal analysis of {topic}.", "temperature": 0.6, "rating": 0.5, "uses": 0},
        {"id": "p5", "prompt": "Write code to solve {topic}.", "temperature": 0.4, "rating": 0.5, "uses": 0},
    ]

def save_patterns(patterns):
    with open(PATTERN_FILE, "w") as f:
        json.dump(patterns, f, indent=2)

# ---------- AI Caller with Full Multi‑Key Rotation ----------
def call_ai(prompt, temperature=0.7, model="deepseek"):
    global DEEPSEEK_KEY_INDEX, GEMINI_KEY_INDEX, CEREBRAS_KEY_INDEX, GROQ_KEY_INDEX

    # 1. DeepSeek (primary, rotating)
    if model == "deepseek" and DEEPSEEK_API_KEYS:
        for attempt in range(2):  # retry each key once
            for _ in range(len(DEEPSEEK_API_KEYS)):
                key = DEEPSEEK_API_KEYS[DEEPSEEK_KEY_INDEX % len(DEEPSEEK_API_KEYS)]
                DEEPSEEK_KEY_INDEX += 1
                try:
                    headers = {"Authorization": f"Bearer {key}"}
                    payload = {
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature
                    }
                    response = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers, timeout=30)
                    return response.json()["choices"][0]["message"]["content"]
                except Exception as e:
                    logger.warning(f"DeepSeek key {key[:5]}... attempt {attempt+1} failed: {e}")
                    continue
        logger.error("All DeepSeek keys failed, trying Gemini")

    # 2. Gemini (secondary, rotating)
    if GEMINI_API_KEYS:
        for _ in range(len(GEMINI_API_KEYS)):
            key = GEMINI_API_KEYS[GEMINI_KEY_INDEX % len(GEMINI_API_KEYS)]
            GEMINI_KEY_INDEX += 1
            try:
                genai.configure(api_key=key)
                gem_model = genai.GenerativeModel("gemini-1.5-flash")
                response = gem_model.generate_content(prompt, generation_config={"temperature": temperature})
                return response.text
            except Exception as e:
                logger.warning(f"Gemini key {key[:5]}... failed: {e}")
                continue
        logger.error("All Gemini keys failed, trying Cerebras")

    # 3. Cerebras (tertiary, rotating)
    if CEREBRAS_API_KEYS:
        for _ in range(len(CEREBRAS_API_KEYS)):
            key = CEREBRAS_API_KEYS[CEREBRAS_KEY_INDEX % len(CEREBRAS_API_KEYS)]
            CEREBRAS_KEY_INDEX += 1
            try:
                headers = {"Authorization": f"Bearer {key}"}
                payload = {
                    "model": "cerebras-2.0",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature
                }
                response = requests.post("https://api.cerebras.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                return response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"Cerebras key {key[:5]}... failed: {e}")
                continue
        logger.error("All Cerebras keys failed, trying Groq")

    # 4. Groq (quaternary, rotating)
    if GROQ_API_KEYS:
        for _ in range(len(GROQ_API_KEYS)):
            key = GROQ_API_KEYS[GROQ_KEY_INDEX % len(GROQ_API_KEYS)]
            GROQ_KEY_INDEX += 1
            try:
                headers = {"Authorization": f"Bearer {key}"}
                payload = {
                    "model": "mixtral-8x7b-32768",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature
                }
                response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                return response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"Groq key {key[:5]}... failed: {e}")
                continue
        logger.error("All Groq keys failed, trying OpenAI")

    # 5. OpenAI fallback (single key)
    if OPENAI_API_KEY:
        try:
            import openai
            openai.api_key = OPENAI_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"OpenAI fallback failed: {e}")

    # Final simulation
    return f"[Simulated] LROS would answer: {prompt[:100]}..."

# ---------- All other endpoints (feedback, generate, evolve, state, self‑play, etc.) remain exactly as in the previous final version ----------
# They are unchanged and fully functional. For brevity, they are omitted here but must be included in the actual file.
# Ensure you copy the complete code from the previous final version (the one with all tabs, governance, orchestration, etc.)
# and replace only the call_ai function and the key definitions at the top.

# ---------- Health, Debug, Root ----------
@app.get("/health")
async def health():
    return {"status": "ok", "bond": "HOLDS", "self_play": "active", "agents": os.environ.get("AGENT_COUNT", "0")}

@app.get("/debug/patterns")
def debug_patterns():
    return load_patterns()

@app.get("/")
def root():
    return {"message": "LROS Constitutional AI Engine is alive", "bond": "HOLDS"}

# ---------- Startup ----------
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(continuous_self_play(interval_seconds=5))
    parallel_workers = int(os.environ.get("PARALLEL_SELF_PLAY", "0"))
    if parallel_workers > 0:
        for i in range(parallel_workers):
            asyncio.create_task(parallel_self_play_worker(i, interval_seconds=5))
    logger.info("LROS startup complete.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
