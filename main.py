from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import random
import openai
import google.generativeai as genai
import anthropic
import requests
import cohere
from datetime import datetime
from typing import Optional, List

app = FastAPI(title="LROS Multi‑AI Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# API keys from environment
openai.api_key = os.environ.get("OPENAI_API_KEY")
if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
cohere_client = cohere.Client(api_key=os.environ.get("COHERE_API_KEY"))
WRITER_API_KEY = os.environ.get("WRITER_API_KEY")

# Pattern registry (same as before)
PATTERN_FILE = "patterns.json"
def load_patterns():
    if os.path.exists(PATTERN_FILE):
        with open(PATTERN_FILE) as f:
            return json.load(f)
    return [
        {"id": "p1", "prompt": "Explain {topic} in simple terms.", "temperature": 0.7, "rating": 0.5, "uses": 0},
        {"id": "p2", "prompt": "Write a detailed technical article about {topic}.", "temperature": 0.5, "rating": 0.5, "uses": 0},
        {"id": "p3", "prompt": "Give a creative story about {topic}.", "temperature": 0.9, "rating": 0.5, "uses": 0},
    ]
def save_patterns(patterns):
    with open(PATTERN_FILE, "w") as f:
        json.dump(patterns, f, indent=2)

# Multi‑AI caller
def call_ai(prompt, temperature=0.7, model="openai"):
    # ... include all six branches (OpenAI, Gemini, Claude, DeepSeek, Cohere, Writer) ...
    # (Use the code from previous message, it's too long to repeat here but it's exactly what you need)

# Feedback endpoint
class Feedback(BaseModel):
    pattern_id: str
    rating: float
    comment: Optional[str] = None
    context: Optional[str] = None

@app.post("/api/feedback")
async def submit_feedback(feedback: Feedback):
    patterns = load_patterns()
    for p in patterns:
        if p["id"] == feedback.pattern_id:
            p["uses"] = p.get("uses", 0) + 1
            old_uses = p["uses"] - 1
            if old_uses > 0:
                p["rating"] = (p["rating"] * old_uses + feedback.rating) / p["uses"]
            else:
                p["rating"] = feedback.rating
            break
    save_patterns(patterns)
    return {"status": "ok"}

# Orchestration endpoint (with super‑ensemble)
class OrchestrationRequest(BaseModel):
    topic: str
    pattern_id: Optional[str] = None
    mode: str
    models: Optional[List[str]] = None

@app.post("/api/generate/orchestrated")
async def generate_orchestrated(req: OrchestrationRequest):
    patterns = load_patterns()
    if req.pattern_id:
        pattern = next((p for p in patterns if p["id"] == req.pattern_id), None)
        if not pattern:
            pattern = max(patterns, key=lambda p: p["rating"])
    else:
        pattern = max(patterns, key=lambda p: p["rating"])
    prompt = pattern["prompt"].format(topic=req.topic)
    temperature = pattern["temperature"]

    if req.mode == "super-ensemble":
        models_to_use = ["openai", "gemini", "claude", "deepseek", "cohere", "writer"]
        responses = {}
        for m in models_to_use:
            resp = call_ai(prompt, temperature, m)
            responses[m] = resp
        combined = "**Super Ensemble**\n\n"
        for m, resp in responses.items():
            combined += f"**{m.upper()}**:\n{resp}\n\n---\n\n"
        return {"response": combined, "pattern_id": pattern["id"]}

    # ... (rest of modes: single, dual, trio, etc.) ...
    # Use the same code as earlier

# State and evolution endpoints (unchanged)
STATE_FILE = "state.json"
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"current_phase": 0, "completed_phases": [], "logs": [], "bond_status": "HOLDS"}
def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

@app.get("/api/state")
def get_state():
    return load_state()

@app.post("/api/evolution")
def evolve_phase(action: dict):
    state = load_state()
    act = action.get("action")
    if act == "start":
        state["logs"].append({"timestamp": datetime.utcnow().isoformat(), "message": "Evolution started", "type": "info"})
        save_state(state)
        return {"status": "started"}
    elif act == "reset":
        state = {"current_phase": 0, "completed_phases": [], "logs": [], "bond_status": "HOLDS"}
        save_state(state)
        return {"status": "reset"}
    elif act == "step":
        if state["current_phase"] < 9:
            state["completed_phases"].append(state["current_phase"])
            state["current_phase"] += 1
            state["logs"].append({"timestamp": datetime.utcnow().isoformat(), "message": f"Phase {state['current_phase']} completed", "type": "info"})
            save_state(state)
        return {"status": "advanced", "phase": state["current_phase"]}
    return {"status": "unknown"}

@app.post("/api/evolve")
async def run_evolution():
    # ... (include your evolution code) ...
    return {"status": "simulated"}

@app.get("/")
def root():
    return {"message": "LROS Constitutional AI Engine is alive", "bond": "HOLDS"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
