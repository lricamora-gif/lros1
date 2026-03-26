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

app = FastAPI(title="LROS Evolution Engine")

# Allow all origins (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- PATTERN REGISTRY --------------------
PATTERN_FILE = "patterns.json"

def load_patterns():
    if os.path.exists(PATTERN_FILE):
        with open(PATTERN_FILE) as f:
            return json.load(f)
    # Default patterns – you can add more
    return [
        {"id": "pattern_1", "prompt": "Explain {topic} in simple terms.", "temperature": 0.7, "rating": 0.5, "uses": 0},
        {"id": "pattern_2", "prompt": "Write a detailed technical article about {topic}.", "temperature": 0.5, "rating": 0.5, "uses": 0},
        {"id": "pattern_3", "prompt": "Give a creative story about {topic}.", "temperature": 0.9, "rating": 0.5, "uses": 0}
    ]

def save_patterns(patterns):
    with open(PATTERN_FILE, "w") as f:
        json.dump(patterns, f, indent=2)

# -------------------- GOOGLE SHEETS SETUP --------------------
# Set up a service account and share your Google Sheet with its email.
# Place the credentials JSON file as "credentials.json" in your repo.
SHEET_NAME = "LROS_Feedback"
scope = ["https://www.googleapis.com/auth/spreadsheets"]
try:
    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    # Ensure headers
    if not sheet.get_all_values():
        sheet.append_row(["timestamp", "pattern_id", "rating", "comment", "context"])
except Exception as e:
    print("Google Sheets not configured. Feedback will be stored locally.")
    sheet = None

# -------------------- FEEDBACK MODEL --------------------
class Feedback(BaseModel):
    pattern_id: str
    rating: float  # 0.0 to 1.0
    comment: Optional[str] = None
    context: Optional[str] = None

@app.post("/api/feedback")
async def submit_feedback(feedback: Feedback):
    """Store feedback in Google Sheets (or local fallback)."""
    patterns = load_patterns()
    # Update pattern's average rating (simple moving average)
    for p in patterns:
        if p["id"] == feedback.pattern_id:
            p["uses"] = p.get("uses", 0) + 1
            # Simple moving average: new_rating = (old_rating * old_uses + new_rating) / (old_uses + 1)
            old_uses = p["uses"] - 1
            if old_uses > 0:
                p["rating"] = (p["rating"] * old_uses + feedback.rating) / p["uses"]
            else:
                p["rating"] = feedback.rating
            break
    save_patterns(patterns)

    # Store in Google Sheets if configured
    if sheet:
        sheet.append_row([
            datetime.utcnow().isoformat(),
            feedback.pattern_id,
            feedback.rating,
            feedback.comment or "",
            feedback.context or ""
        ])
    else:
        # Fallback to local file
        with open("feedback_log.txt", "a") as f:
            f.write(f"{datetime.utcnow()},{feedback.pattern_id},{feedback.rating}\n")

    return {"status": "ok"}

# -------------------- EVOLUTION ENGINE --------------------
class MutationRequest(BaseModel):
    pattern_id: str

def mutate_pattern(pattern):
    """Create a mutated version of a pattern."""
    import copy
    new_pattern = copy.deepcopy(pattern)
    new_pattern["id"] = f"{pattern['id']}_mut_{random.randint(1000,9999)}"
    # Mutate the prompt: add a word, change style, etc.
    words = pattern["prompt"].split()
    if random.random() < 0.5 and len(words) > 2:
        # Insert a random adjective
        adjectives = ["concise", "detailed", "creative", "technical", "funny", "professional"]
        pos = random.randint(1, len(words)-1)
        words.insert(pos, random.choice(adjectives))
        new_pattern["prompt"] = " ".join(words)
    else:
        # Change temperature slightly
        new_pattern["temperature"] = min(1.0, max(0.0, pattern["temperature"] + random.uniform(-0.2, 0.2)))
    new_pattern["rating"] = 0.5  # start neutral
    new_pattern["uses"] = 0
    return new_pattern

def evaluate_pattern(pattern, test_inputs):
    """
    Evaluate a pattern by asking a real LLM (or a mock) for quality.
    For now, we'll use a simple mock: return a random score.
    In production, call an LLM API (OpenAI, etc.) to rate the response.
    """
    # TODO: Replace with actual LLM call to judge response quality.
    # For demonstration, we simulate improvement if the pattern is mutated.
    # You can integrate OpenAI or another model here.
    # Example: response = call_openai(pattern["prompt"].format(topic="AI"))
    # Then evaluate with a judge LLM or heuristic.
    return random.uniform(0.4, 0.9)

@app.post("/api/evolve")
async def run_evolution():
    """Run one evolution cycle: identify worst patterns, mutate, test, promote."""
    patterns = load_patterns()
    if not patterns:
        return {"status": "no patterns"}

    # 1. Find patterns with lowest rating that have been used enough
    candidates = [p for p in patterns if p.get("uses", 0) > 5]
    if not candidates:
        return {"status": "not enough data"}

    worst = min(candidates, key=lambda p: p["rating"])
    worst_rating = worst["rating"]

    # 2. Generate mutations
    mutations = [mutate_pattern(worst) for _ in range(3)]

    # 3. Evaluate mutations (simulate with a dummy function; replace with real eval)
    for m in mutations:
        # For demo, we use a placeholder. In reality, you'd evaluate on a set of test queries.
        m["rating"] = evaluate_pattern(m, [])
        m["uses"] = 0

    # 4. If a mutation beats the worst pattern, promote it
    best_mutation = max(mutations, key=lambda m: m["rating"])
    if best_mutation["rating"] > worst_rating:
        # Replace the worst pattern with the best mutation
        idx = patterns.index(worst)
        patterns[idx] = best_mutation
        save_patterns(patterns)
        return {
            "status": "evolved",
            "old_pattern": worst,
            "new_pattern": best_mutation,
            "improvement": best_mutation["rating"] - worst_rating
        }
    else:
        return {"status": "no improvement", "best_mutation_rating": best_mutation["rating"], "worst_rating": worst_rating}

# -------------------- STATE (for phases) --------------------
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
    """Increment phase (for the one‑button play milestone)."""
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

# For local testing, run with: uvicorn main:app --reload
