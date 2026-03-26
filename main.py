from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from datetime import datetime

app = FastAPI(title="LROS Evolution Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
def evolve(action: dict):
    state = load_state()
    act = action.get("action")
    if act == "start":
        state["logs"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Evolution started",
            "type": "info"
        })
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
            state["logs"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Phase {state['current_phase']} completed",
                "type": "info"
            })
            save_state(state)
        return {"status": "advanced", "phase": state["current_phase"]}
    return {"status": "unknown"}
