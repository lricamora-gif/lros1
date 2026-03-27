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
anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY")) if os.environ.get("ANTHROPIC_API_KEY") else None
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
cohere_client = cohere.Client(api_key=os.environ.get("COHERE_API_KEY")) if os.environ.get("COHERE_API_KEY") else None
WRITER_API_KEY = os.environ.get("WRITER_API_KEY")

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

def call_ai(prompt, temperature=0.7, model="openai"):
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
            gem_model = genai.GenerativeModel("gemini-1.5-flash")
            response = gem_model.generate_content(prompt, generation_config={"temperature": temperature})
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

    return f"[Simulated] LROS would answer: {prompt[:100]}..."

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
            responses[m] = call_ai(prompt, temperature, m)
        combined = "**Super Ensemble**\n\n" + "\n\n---\n\n".join([f"**{m.upper()}**:\n{resp}" for m, resp in responses.items()])
        return {"response": combined, "pattern_id": pattern["id"]}

    # Normal modes
    if req.mode == "single":
        model = (req.models[0] if req.models else "openai")
        combined = call_ai(prompt, temperature, model)
    elif req.mode in ["dual", "trio", "quad", "orchestra", "boardroom", "courtroom", "federation"]:
        num = {"dual":2, "trio":3, "quad":4, "orchestra":5, "boardroom":4, "courtroom":2, "federation":3}[req.mode]
        models = (req.models[:num] if req.models else ["openai", "gemini", "claude", "deepseek", "cohere"][:num])
        combined = "\n\n---\n\n".join([f"**{m.upper()}**:\n{call_ai(prompt, temperature, m)}" for m in models])
        if req.mode == "boardroom":
            combined = "**Boardroom Decision**\n\n" + combined + "\n\n**Consensus**: Blended."
        elif req.mode == "courtroom":
            combined = f"**Courtroom Debate**\n\n**Prosecution ({models[0].upper()})**:\n{call_ai(prompt, temperature, models[0])}\n\n**Defense ({models[1].upper()})**:\n{call_ai(prompt, temperature, models[1])}\n\n**Verdict**: Balanced."
        elif req.mode == "federation":
            combined = "**Federation of Agents**\n\n" + combined + "\n\n**Global Consensus**: High alignment."
    else:
        raise HTTPException(400, "Invalid mode")

    return {"response": combined, "pattern_id": pattern["id"]}

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
        judge_prompt = f"Rate the following response from 0 to 1 (1 = perfect, 0 = useless):\n\nResponse: {response}\n\nRating (just a number):"
        judge_resp = call_ai(judge_prompt, 0)
        try:
            score = float(judge_resp.strip())
        except:
            score = 0.5
        total += score
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
    return {"message": "LROS Constitutional AI Engine is alive", "bond": "HOLDS"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
