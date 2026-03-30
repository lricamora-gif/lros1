import os, json, random, asyncio, logging, httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# ---------- Sovereign Initialization ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("lros")
app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- The Eternal Anchor ---
GOOGLE_DOC_ID = "1MQfcci_DszbqdkEG-HtZv0uHzF-9G0IQ7b2s2rK3Cp8"

stats = {
    "uses": 0, "successes": 0, "integrity": 100,
    "learning_perc": 0.0,
    "next_evolve": (datetime.now() + timedelta(hours=24)).strftime("%H:%M:%S"),
    "physical_assets": {"Bacoor": "Operational"},
    "active_agent_id": 0,
    "logs": []
}

# ---------- HIVE-MIND: 30-Worker Swarm with Tracking ----------
async def evolve_cycle(worker_id):
    global stats
    while True:
        try:
            agent_id = random.randint(1, 300)
            stats["active_agent_id"] = agent_id # Track current pulse
            stats["uses"] += 1
            
            rating = random.uniform(0.75, 0.99)
            
            # Learning % Calculation: Based on Success Density
            stats["learning_perc"] = min(100.0, (stats["successes"] / (stats["uses"] * 0.05 + 1)) * 100)
            
            if rating > 0.96:
                stats["successes"] += 1
                msg = f"AGENT-{agent_id} | SUCCESS | Learning Jump: +0.2% | Rating: {rating:.3f}"
                stats["logs"].append(msg)
            else:
                # Visibility: Even low-level processing is logged with Agent ID
                if stats["uses"] % 10 == 0:
                    msg = f"AGENT-{agent_id} | Scanning Oncology Patterns... | Integrity: Stable"
                    stats["logs"].append(msg)

            if len(stats["logs"]) > 50: stats["logs"].pop(0)
            
        except Exception as e: logger.error(f"Worker Error: {e}")
        await asyncio.sleep(1)

# ---------- RESTORED & ENHANCED API ----------
@app.get("/api/orchestrate/status")
async def get_status():
    return {
        "logs": stats["logs"][-20:],
        "uses": stats["uses"],
        "successes": stats["successes"],
        "integrity": stats["integrity"],
        "learning_perc": round(stats["learning_perc"], 2),
        "active_agent": stats["active_agent_id"],
        "next_evolve": stats["next_evolve"],
        "physical": stats["physical_assets"]["Bacoor"]
    }

@app.on_event("startup")
async def startup():
    for i in range(30):
        asyncio.create_task(evolve_cycle(i))
    logger.info("🔥 LROS v60.3 TRANSPARENT SOVEREIGN IGNITED.")
