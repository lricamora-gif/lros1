from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import random
import requests
from datetime import datetime
from typing import Optional

app = FastAPI(title="LROS AI Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# DeepSeek API key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# Pattern registry
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

def call_ai(prompt, temperature=0.7):
    if DEEPSEEK_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
            payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": temperature}
            response = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers)
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"DeepSeek error: {e}")
    return f"[Simulated] LROS would answer: {prompt[:100]}..."

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

# Simple generate endpoint
class GenerateRequest(BaseModel):
    topic: str
    pattern_id: Optional[str] = None

@app.post("/api/generate")
async def generate(req: GenerateRequest):
    patterns = load_patterns()
    if req.pattern_id:
        pattern = next((p for p in patterns if p["id"] == req.pattern_id), None)
        if not pattern:
            pattern = max(patterns, key=lambda p: p["rating"])
    else:
        pattern = max(patterns, key=lambda p: p["rating"])
    prompt = pattern["prompt"].format(topic=req.topic)
    temperature = pattern["temperature"]
    response = call_ai(prompt, temperature)
    return {"response": response, "pattern_id": pattern["id"]}

# State endpoints
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

# Evolution engine (simplified)
def mutate_pattern(pattern):
    import copy
    new = copy.deepcopy(pattern)
    new["id"] = f"{pattern['id']}_mut_{random.randint(1000,9999)}"
    words = pattern["prompt"].split()
    if random.random() < 0.5 and len(words) > 2:
        adjectives = ["concise", "detailed", "creative", "technical", "funny", "professional"]
        pos = random.randint(1, len(words)-1)
        words.insert(pos, random.choice(adjectives))
        new["prompt"] = " ".join(words)
    else:
        new["temperature"] = min(1.0, max(0.0, pattern["temperature"] + random.uniform(-0.2, 0.2)))
    new["rating"] = 0.5
    new["uses"] = 0
    return new

def evaluate_pattern(pattern, test_inputs=None):
    if not test_inputs:
        test_inputs = ["What is machine learning?", "Explain quantum computing simply", "How do I start coding?"]
    total = 0
    for query in test_inputs:
        prompt = pattern["prompt"].format(topic=query)
        response = call_ai(prompt, pattern["temperature"])
        total += random.uniform(0.4, 0.9)  # simple simulation for now
    return total / len(test_inputs)

@app.post("/api/evolve")
async def run_evolution():
    patterns = load_patterns()
    candidates = [p for p in patterns if p.get("uses", 0) > 5]
    if not candidates:
        return {"status": "not enough data", "message": "Need at least 5 uses per pattern to evolve"}

    worst = min(candidates, key=lambda p: p["rating"])
    worst_rating = worst["rating"]
    mutations = [mutate_pattern(worst) for _ in range(3)]

    for m in mutations:
        m["rating"] = evaluate_pattern(m)

    best_mutation = max(mutations, key=lambda m: m["rating"])
    if best_mutation["rating"] > worst_rating:
        idx = patterns.index(worst)
        patterns[idx] = best_mutation
        save_patterns(patterns)
        return {
            "status": "evolved",
            "old_pattern": worst,
            "new_pattern": best_mutation,
            "improvement": best_mutation["rating"] - worst_rating
        }
    return {"status": "no improvement", "best_mutation_rating": best_mutation["rating"], "worst_rating": worst_rating}

@app.get("/")
def root():
    return {"message": "LROS AI Engine is alive", "bond": "HOLDS"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
