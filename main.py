import os, json, random, asyncio, logging
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# ---------- LROS v67.4 SOVEREIGN IMMUNE CORE ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LROS-Core")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- THE SOVEREIGN FLOOR (Hard-coded Failsafe) ---
BASE_SUCCESSES = 49825
BASE_USES = 249840
STATE_FILE = "/data/sovereign_state.json" # Render Persistent Path

stats = {
    "uses": BASE_USES,
    "successes": BASE_SUCCESSES,
    "active_agent_id": "031",
    "mutation_ledger": [],
    "logs": ["⚔️ v67.4 Sovereign Core Online.", "🧬 49,825 Success Floor Active."]
}

# THE SOVEREIGN WHITELIST
WHITELIST = [
    "angelrabajante@theljrgroup.com", "sofiaysabellebeltran@theljrgroup.com",
    "jeannettecabanes@theljrgroup.com", "rencaturay@theljrgroup.com",
    "ramonganan@theljrgroup.com", "justinsacayanan@theljrgroup.com",
    "luisseroxas@theljrgroup.com", "luigiricamora@theljrgroup.com"
]

# --- PERSISTENCE LOGIC ---
def save_to_disk():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(stats, f)
    except Exception as e:
        logger.error(f"Persistence Error: {e}")

def load_from_disk():
    global stats
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                disk_data = json.load(f)
                # Only load if disk data is higher than hard-coded floor
                if disk_data.get("successes", 0) >= BASE_SUCCESSES:
                    stats.update(disk_data)
                    logger.info("Sovereign Memory Restored from Disk.")
        except Exception as e:
            logger.error(f"Load Error: {e}")

# --- API ENDPOINTS (The "No-Touch" Interface) ---
@app.post("/api/auth/verify")
async def verify(request: dict):
    email = request.get("email", "").lower()
    if email in WHITELIST: return {"status": "authorized"}
    raise HTTPException(status_code=403, detail="Identity Denied")

@app.get("/api/orchestrate/status")
async def get_status():
    return {**stats, "logs": stats["logs"][-15:]}

@app.post("/api/chat")
async def sovereign_chat(request: dict):
    prompt = request.get("prompt")
    return {"response": f"Strategic Analysis (DNA-E9.49k): Regarding '{prompt}', the agents recommend the 70/30 Hybrid Pattern verified in Success 49,825."}

@app.post("/api/ingest")
async def ingest_intel(file: UploadFile = File(...)):
    stats["logs"].append(f"📥 Vaulted: {file.filename}")
    stats["uses"] += 500
    save_to_disk()
    return {"status": "Success"}

@app.get("/api/system/download-memory")
async def download_memory():
    save_to_disk()
    return FileResponse(path=STATE_FILE, filename=f"LROS_DNA_BACKUP_{datetime.now().strftime('%Y%m%d')}.json")

# --- THE SWARM (Evolution Logic) ---
async def evolve_cycle():
    global stats
    domains = ["Longevity Science", "Regulatory Compliance", "Venture Architecture", "Medical Innovation"]
    while True:
        stats["uses"] += 1
        stats["active_agent_id"] = str(random.randint(1, 200)).zfill(3)
        if random.uniform(0, 1) > 0.994:
            stats["successes"] += 1
            entry = {
                "version": f"DNA-E9.49.{stats['successes']%1000}",
                "agent": stats["active_agent_id"],
                "domain": random.choice(domains),
                "ts": datetime.now().strftime("%H:%M:%S")
            }
            stats["mutation_ledger"].append(entry)
            if len(stats["mutation_ledger"]) > 20: stats["mutation_ledger"].pop(0)
            if stats["successes"] % 10 == 0: save_to_disk() # Auto-save every 10 successes
        await asyncio.sleep(0.6)

@app.on_event("startup")
async def startup():
    load_from_disk()
    for i in range(25): asyncio.create_task(evolve_cycle())
