from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import random
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional, List
import openai

app = FastAPI(title="LROS Evolution Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- CONFIGURATION --------------------
openai.api_key = os.environ.get("OPENAI_API_KEY")
PATTERN_FILE = "patterns.json"
STATE_FILE = "state.json"
SHEET_NAME = "LROS_Feedback"

# -------------------- GOOGLE SHEETS --------------------
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds_json = os.environ.get("GOOGLE_CREDENTIALS")
if creds_json:
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
else:
    try:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
    except Exception:
        sheet = None

if sheet and not sheet.get_all_values():
    sheet.append_row(["timestamp", "pattern_id", "rating", "comment", "context"])

# -------------------- PATTERN REGISTRY --------------------
def load_patterns():
    if os.path.exists(PATTERN_FILE):
        with open(PATTERN_FILE) as f:
            return json.load(f)
    # Default patterns
    return [
        {"id": "pattern_1", "prompt": "Explain {topic} in simple terms.", "temperature": 0.7, "rating": 0.5, "uses": 0},
        {"id": "pattern_2", "prompt": "Write a detailed technical article about {topic}.", "temperature": 0.5, "rating": 0.5, "uses": 0},
        {"id": "pattern_3", "prompt": "Give a creative story about {topic}.", "temperature": 0.9, "rating": 0.5, "uses": 0}
    ]

def save_patterns(patterns):
    with open(PATTERN_FILE, "w") as f:
        json.dump(patterns, f, indent=2)

# -------------------- OPENAI HELPERS --------------------
def call_openai(prompt, temperature=0.7):
    if not openai.api_key:
        return "[OpenAI API key missing]"
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature
    )
    return response.choices[0].message.content

def evaluate_pattern(pattern, test_inputs=None):
    """Use OpenAI to judge the quality of a pattern on test queries."""
    if not test_inputs:
        test_inputs = [
            "What is machine learning?",
            "Explain quantum computing simply",
            "How do I start coding?"
        ]
    total = 0
    for query in test_inputs:
        try:
            prompt = pattern["prompt"].format(topic=query)
            response = call_openai(prompt, temperature=pattern["temperature"])
            judge_prompt = f"Rate the following response from 0 to 1 (1 = perfect, 0 = useless):\n\nResponse: {response}\n\nRating (just a number):"
            judge_resp = call_openai(judge_prompt, temperature=0)
            score = float(judge_resp.strip())
        except Exception:
            score = 0.5
        total += score
    return total / len(test_inputs)

# -------------------- FEEDBACK --------------------
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
            f.write(f"{datetime.utcnow()},{feedback.pattern_id},{feedback.rating}\n")
    return {"status": "ok"}

# -------------------- GENERATION --------------------
@app.get("/api/generate")
async def generate(topic: str, pattern_id: Optional[str] = None):
    patterns = load_patterns()
    if pattern_id:
        pattern = next((p for p in patterns if p["id"] == pattern_id), None)
        if not pattern:
            raise HTTPException(status_code=404, detail="Pattern not found")
    else:
        pattern = max(patterns, key=lambda p: p["rating"])
    prompt = pattern["prompt"].format(topic=topic)
    response = call_openai(prompt, temperature=pattern["temperature"])
    return {"response": response, "pattern_id": pattern["id"]}

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

@app.post("/api/evolve")
@app.get("/api/evolve")
async def run_evolution():
    patterns = load_patterns()
    candidates = [p for p in patterns if p.get("uses", 0) > 5]
    if not candidates:
        return {"status": "not enough data", "message": "Need at least 5 uses per pattern to evolve"}

    worst = min(candidates, key=lambda p: p["rating"])
    worst_rating = worst["rating"]
    mutations = [mutate_pattern(worst) for _ in range(3)]

    # Evaluate each mutation using real LLM
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

# -------------------- PHASE PROGRESSION --------------------
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
