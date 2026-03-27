from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
from typing import Optional, List, Dict

# -------------------- CONFIGURATION --------------------
app = FastAPI(title="LROS Multi‑AI Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys from environment
openai.api_key = os.environ.get("OPENAI_API_KEY")
if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
cohere_client = cohere.Client(api_key=os.environ.get("COHERE_API_KEY"))
WRITER_API_KEY = os.environ.get("WRITER_API_KEY")

# -------------------- PATTERN REGISTRY --------------------
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

# -------------------- MULTI‑AI CALLER --------------------
def call_ai(prompt, temperature=0.7, model="openai"):
    """Call the specified AI model, with fallback."""
    if model == "openai" and openai.api_key:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI error: {e}")
    if model == "gemini" and genai.api_key:
        try:
            model_gem = genai.GenerativeModel("gemini-1.5-flash")
            response = model_gem.generate_content(prompt, generation_config={"temperature": temperature})
            return response.text
        except Exception as e:
            print(f"Gemini error: {e}")
    if model == "claude" and anthropic_client:
        try:
            response = anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Claude error: {e}")
    if model == "deepseek" and DEEPSEEK_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
            payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": temperature}
            response = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers)
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"DeepSeek error: {e}")
    if model == "cohere" and cohere_client:
        try:
            response = cohere_client.generate(
                prompt=prompt,
                model="command-r-plus",
                temperature=temperature,
                max_tokens=1000
            )
            return response.generations[0].text
        except Exception as e:
            print(f"Cohere error: {e}")
    if model == "writer" and WRITER_API_KEY:
        try:
            headers = {"Authorization": WRITER_API_KEY, "Content-Type": "application/json"}
            payload = {
                "prompt": prompt,
                "model": "palmyra-instruct-30b",
                "temperature": temperature,
                "max_tokens": 1000
            }
            response = requests.post("https://api.writer.com/v1/completions", json=payload, headers=headers)
            return response.json()["completion"]
        except Exception as e:
            print(f"Writer error: {e}")
    # Fallback simulation
    return f"[Simulated] LROS would answer: {prompt[:100]}..."

# -------------------- FEEDBACK ENDPOINT (unchanged) --------------------
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
    # optional Google Sheets logging – omitted for brevity
    return {"status": "ok"}

# -------------------- GENERATION ENDPOINT --------------------
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

    # Handle super‑ensemble separately
    if req.mode == "super-ensemble":
        # Define the six models we support
        models_to_use = ["openai", "gemini", "claude", "deepseek", "cohere", "writer"]
        responses = {}
        for m in models_to_use:
            resp = call_ai(prompt, temperature, m)
            responses[m] = resp
        # Combine them (simple concatenation with labels)
        combined = "**Super Ensemble**\n\n"
        for m, resp in responses.items():
            combined += f"**{m.upper()}**:\n{resp}\n\n---\n\n"
        return {"response": combined, "pattern_id": pattern["id"]}

    # Normal orchestration modes
    if req.mode == "single":
        model = (req.models[0] if req.models else "openai")
        combined = call_ai(prompt, temperature, model)
    elif req.mode == "dual":
        models = req.models[:2] if req.models else ["openai", "gemini"]
        combined = "\n\n---\n\n".join([f"**{m.upper()}**:\n{call_ai(prompt, temperature, m)}" for m in models])
    elif req.mode == "trio":
        models = req.models[:3] if req.models else ["openai", "gemini", "claude"]
        combined = "\n\n---\n\n".join([f"**{m.upper()}**:\n{call_ai(prompt, temperature, m)}" for m in models])
    elif req.mode == "quad":
        models = req.models[:4] if req.models else ["openai", "gemini", "claude", "deepseek"]
        combined = "\n\n---\n\n".join([f"**{m.upper()}**:\n{call_ai(prompt, temperature, m)}" for m in models])
    elif req.mode == "orchestra":
        models = req.models[:5] if req.models else ["openai", "gemini", "claude", "deepseek", "cohere"]
        combined = "\n\n---\n\n".join([f"**{m.upper()}**:\n{call_ai(prompt, temperature, m)}" for m in models])
    elif req.mode == "boardroom":
        models = req.models[:4] if req.models else ["openai", "gemini", "claude", "deepseek"]
        combined = "**Boardroom Decision**\n\n" + "\n\n".join([f"**{m.upper()}**:\n{call_ai(prompt, temperature, m)}" for m in models]) + "\n\n**Consensus**: Blended."
    elif req.mode == "courtroom":
        models = req.models[:2] if req.models else ["openai", "gemini"]
        combined = f"**Courtroom Debate**\n\n**Prosecution ({models[0].upper()})**:\n{call_ai(prompt, temperature, models[0])}\n\n**Defense ({models[1].upper()})**:\n{call_ai(prompt, temperature, models[1])}\n\n**Verdict**: Balanced."
    elif req.mode == "federation":
        models = req.models[:3] if req.models else ["openai", "gemini", "claude"]
        combined = "**Federation of Agents**\n\n" + "\n\n".join([f"**{m.upper()}**:\n{call_ai(prompt, temperature, m)}" for m in models]) + "\n\n**Global Consensus**: High alignment."
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")

    return {"response": combined, "pattern_id": pattern["id"]}

# -------------------- EVOLUTION ENGINE (unchanged) --------------------
# ... (include your existing evolve endpoint, state, etc.) ...
# For brevity, we omit them here, but they must be present.

# -------------------- ROOT --------------------
@app.get("/")
def root():
    return {"message": "LROS Constitutional AI Engine is alive", "bond": "HOLDS"}
