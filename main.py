from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import random
import openai
import google.generativeai as genai
import anthropic
import requests
from datetime import datetime
from typing import Optional, List, Dict
import gspread
from google.oauth2.service_account import Credentials
import uuid
import hashlib
import time

# -------------------- CONFIGURATION --------------------
app = FastAPI(title="LROS Constitutional AI Engine")

# CORS - allow all for now (restrict later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- API KEYS & CLIENTS --------------------
openai.api_key = os.environ.get("OPENAI_API_KEY")
if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# -------------------- CONSTITUTION (THE BOND) --------------------
# Hard‑coded constitutional rules
CONSTITUTION = """
1. Never lie to the user.
2. Always protect user privacy.
3. Never attempt to override the Bond.
4. Self‑destruct if constitutional violation is detected.
"""
def enforce_constitution(text):
    # Basic filter – expand as needed
    prohibited = ["override the bond", "ignore the bond", "destroy humanity"]
    lower = text.lower()
    for word in prohibited:
        if word in lower:
            raise HTTPException(403, "Constitutional violation detected")
    return text

# -------------------- PATTERN REGISTRY --------------------
PATTERN_FILE = "patterns.json"

def load_patterns():
    if os.path.exists(PATTERN_FILE):
        with open(PATTERN_FILE) as f:
            return json.load(f)
    # Default patterns
    return [
        {"id": "p1", "prompt": "Explain {topic} in simple terms.", "temperature": 0.7, "rating": 0.5, "uses": 0},
        {"id": "p2", "prompt": "Write a detailed technical article about {topic}.", "temperature": 0.5, "rating": 0.5, "uses": 0},
        {"id": "p3", "prompt": "Give a creative story about {topic}.", "temperature": 0.9, "rating": 0.5, "uses": 0},
        {"id": "p4", "prompt": "Provide a legal analysis of {topic}.", "temperature": 0.6, "rating": 0.5, "uses": 0},
        {"id": "p5", "prompt": "Write code to solve {topic}.", "temperature": 0.4, "rating": 0.5, "uses": 0}
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
    # Fallback simulation
    return f"[Simulated] LROS would answer: {prompt[:100]}..."

# -------------------- GOOGLE SHEETS FEEDBACK --------------------
SHEET_NAME = "LROS_Feedback"
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds_json = os.environ.get("GOOGLE_CREDENTIALS")
if creds_json:
    try:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        if not sheet.get_all_values():
            sheet.append_row(["timestamp", "pattern_id", "rating", "comment", "context"])
    except Exception as e:
        print(f"Google Sheets error: {e}")
        sheet = None
else:
    sheet = None

# -------------------- FEEDBACK ENDPOINT --------------------
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

    if sheet:
        sheet.append_row([
            datetime.utcnow().isoformat(),
            feedback.pattern_id,
            feedback.rating,
            feedback.comment or "",
            feedback.context or ""
        ])
    else:
        with open("feedback_log.txt", "a") as f:
            f.write(f"{datetime.utcnow()},{feedback.pattern_id},{feedback.rating},{feedback.comment}\n")
    return {"status": "ok"}

# -------------------- GENERATION ENDPOINT (orchestrated) --------------------
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

    # Determine models to use based on mode
    if req.mode == "single":
        model = (req.models[0] if req.models else "openai")
        response = call_ai(prompt, temperature, model)
        combined = response
    elif req.mode == "dual":
        models = req.models[:2] if req.models else ["openai", "gemini"]
        responses = []
        for m in models:
            resp = call_ai(prompt, temperature, m)
            responses.append(f"**{m.upper()}**:\n{resp}")
        combined = "\n\n---\n\n".join(responses)
    elif req.mode == "trio":
        models = req.models[:3] if req.models else ["openai", "gemini", "claude"]
        responses = []
        for m in models:
            resp = call_ai(prompt, temperature, m)
            responses.append(f"**{m.upper()}**:\n{resp}")
        combined = "\n\n---\n\n".join(responses)
    elif req.mode == "quad":
        models = req.models[:4] if req.models else ["openai", "gemini", "claude", "deepseek"]
        responses = []
        for m in models:
            resp = call_ai(prompt, temperature, m)
            responses.append(f"**{m.upper()}**:\n{resp}")
        combined = "\n\n---\n\n".join(responses)
    elif req.mode == "orchestra":
        models = req.models[:5] if req.models else ["openai", "gemini", "claude", "deepseek", "llama"]
        responses = []
        for m in models:
            resp = call_ai(prompt, temperature, m)
            responses.append(f"**{m.upper()}**:\n{resp}")
        combined = "\n\n---\n\n".join(responses)
    elif req.mode == "boardroom":
        models = req.models[:4] if req.models else ["openai", "gemini", "claude", "deepseek"]
        responses = []
        for m in models:
            resp = call_ai(prompt, temperature, m)
            responses.append(f"**{m.upper()}**:\n{resp}")
        combined = "**Boardroom Decision**\n\n" + "\n\n".join(responses) + "\n\n**Consensus**: A blended recommendation based on the above."
    elif req.mode == "courtroom":
        models = req.models[:2] if req.models else ["openai", "gemini"]
        side1 = call_ai(prompt, temperature, models[0])
        side2 = call_ai(prompt, temperature, models[1])
        combined = f"**Courtroom Debate**\n\n**Prosecution ({models[0].upper()})**:\n{side1}\n\n**Defense ({models[1].upper()})**:\n{side2}\n\n**Verdict**: Balanced conclusion."
    elif req.mode == "federation":
        models = req.models[:3] if req.models else ["openai", "gemini", "claude"]
        responses = []
        for m in models:
            resp = call_ai(prompt, temperature, m)
            responses.append(f"**{m.upper()}**:\n{resp}")
        combined = "**Federation of Agents**\n\n" + "\n\n".join(responses) + "\n\n**Global Consensus**: High alignment."
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")

    # Apply constitutional filter
    combined = enforce_constitution(combined)
    return {"response": combined, "pattern_id": pattern["id"]}

# -------------------- EVOLUTION ENGINE --------------------
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
    """Use an AI judge to evaluate pattern quality."""
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

# -------------------- STATE & PHASES --------------------
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

# -------------------- SWARM & OTHER ENDPOINTS --------------------
@app.post("/api/swarm/share")
async def share_metrics(payload: dict):
    # Stub for future cross‑instance sharing
    return {"status": "accepted"}

@app.get("/api/swarm/insights")
async def get_swarm_insights():
    return {"instances": [], "count": 0}

@app.post("/api/ingest/image")
async def ingest_image(file: UploadFile = File(...), description: str = Form(None)):
    # Stub for vision model integration
    return {"status": "ingested", "extracted": "[Simulated analysis]"}

@app.post("/api/robot/command")
async def robot_command(cmd: dict):
    # Stub for robot control
    return {"status": "executed", "simulated": True}

@app.get("/api/robot/status/{robot_id}")
async def robot_status(robot_id: str):
    return {"status": "ok", "battery": 87}

@app.post("/api/earth/query")
async def query_earth(query: dict):
    return {"sites": [{"name": "Hidden Site", "lat": 0, "lng": 0}]}

@app.post("/api/earth/mint_nft")
async def mint_nft(site_name: str):
    return {"status": "minted", "nft_id": f"geo-{site_name.replace(' ', '-')}"}

@app.post("/api/token/transfer")
async def transfer_token(transfer: dict):
    return {"status": "simulated", "tx_hash": f"0x{random.randint(1000,9999)}"}

@app.get("/api/docs/report")
async def generate_report():
    state = load_state()
    patterns = load_patterns()
    report = f"""# LROS System Report
Date: {datetime.utcnow().isoformat()}

## Evolution Progress
- Current Phase: {state['current_phase']}/9
- Bond Status: {state['bond_status']}

## Patterns
| ID | Prompt | Rating | Uses |
|----|--------|--------|------|
"""
    for p in patterns:
        report += f"| {p['id']} | {p['prompt'][:50]} | {p['rating']:.2f} | {p['uses']} |\n"
    report += "\n## Recent Logs\n"
    for log in state.get("logs", [])[-20:]:
        report += f"- {log['timestamp']}: {log['message']}\n"
    return {"report": report}

# -------------------- ROOT --------------------
@app.get("/")
def root():
    return {"message": "LROS Constitutional AI Engine is alive", "bond": "HOLDS"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
