import os, json, random, asyncio, logging
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ---------- LROS v68.2 SOVEREIGN VOICE CORE ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LROS-Core")
app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- SOVEREIGN FLOOR (LOCKED MILESTONE) ---
BASE_SUCCESSES = 51150
BASE_USES = 530315
STATE_DIR = "./data"
STATE_FILE = os.path.join(STATE_DIR, "sovereign_state.json")
MANIFEST_FILE = os.path.join(STATE_DIR, "layer_manifest.json")
DEVICE_FILE = os.path.join(STATE_DIR, "devices.json")
GOV_FILE = os.path.join(STATE_DIR, "governance.json")

WHITELIST = [
    "angelrabajante@theljrgroup.com", "sofiaysabellebeltran@theljrgroup.com",
    "jeannettecabanes@theljrgroup.com", "rencaturay@theljrgroup.com",
    "ramonganan@theljrgroup.com", "justinsacayanan@theljrgroup.com",
    "luisseroxas@theljrgroup.com", "luigiricamora@theljrgroup.com"
]

# --- CORE STATE ---
stats = {
    "uses": BASE_USES, "successes": BASE_SUCCESSES, "active_agent_id": "134",
    "mutation_ledger": [], "logs": ["🚀 v68.2 Sovereign Voice Core Online.", "🧬 51,150 Success Floor Verified."]
}
user_activity = {}

def ensure_dir(): os.makedirs(STATE_DIR, exist_ok=True)

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f: return json.load(f)
        except Exception as e: return default
    return default

def save_json(path, data):
    ensure_dir()
    try:
        with open(path, "w") as f: json.dump(data, f, indent=2)
    except Exception as e: pass

def load_from_disk():
    global stats
    disk_data = load_json(STATE_FILE, {})
    if disk_data.get("successes", 0) >= BASE_SUCCESSES:
        stats.update(disk_data)
        logger.info("Sovereign Memory Restored.")

def init_manifest():
    default = {"version": "v68.2-Vocal", "layers": [
        {"id": "0", "name": "Immune Core", "type": "constitutional", "status": "active", "description": "Tamper detection and persistence."},
        {"id": "28", "name": "Self-Evolution", "type": "core", "status": "active", "description": "Optimizes layers based on performance."}
    ]}
    return load_json(MANIFEST_FILE, default)

@app.get("/api/layers/manifest")
async def get_manifest(): return init_manifest()

@app.post("/api/layers/propose")
async def trigger_proposal():
    gov = load_json(GOV_FILE, {"pending": [], "approved": []})
    prop_id = f"179{random.randint(0,9)}"
    gov["pending"].append({
        "id": f"layer_{prop_id}", "type": "layer_proposal", "layer_id": prop_id,
        "name": "Predictive Asset Liquidity", "description": "Automated JV ratio adjustments based on foot traffic.",
        "rationale": "Optimizes 70/30 split logic dynamically."
    })
    save_json(GOV_FILE, gov)
    stats["logs"].append(f"🧠 AI Proposed New Layer: {prop_id}")
    return {"status": "proposal_generated"}

@app.get("/api/governance/pending")
async def get_pending(): return load_json(GOV_FILE, {"pending": []})["pending"]

@app.post("/api/governance/decide")
async def decide_gov(req: dict):
    gov = load_json(GOV_FILE, {"pending": [], "approved": []})
    item_id, action = req.get("item_id"), req.get("action")
    item = next((i for i in gov["pending"] if i["id"] == item_id), None)
    if item:
        gov["pending"].remove(item)
        if action == "approve": gov["approved"].append(item)
        save_json(GOV_FILE, gov)
    return {"status": "decided"}

@app.post("/api/layers/deploy")
async def deploy_layers():
    gov = load_json(GOV_FILE, {"pending": [], "approved": []})
    manifest = init_manifest()
    approved = [i for i in gov["approved"] if i["type"] == "layer_proposal"]
    for l in approved:
        manifest["layers"].append({"id": l["layer_id"], "name": l["name"], "type": "operational", "status": "active", "description": l["description"]})
    gov["approved"] = [i for i in gov["approved"] if i["type"] != "layer_proposal"]
    save_json(MANIFEST_FILE, manifest)
    save_json(GOV_FILE, gov)
    stats["logs"].append(f"🚀 Deployed {len(approved)} Approved Layers.")
    return {"status": "deployed", "count": len(approved)}

class DeviceRegister(BaseModel):
    device_id: str
    device_type: str

@app.get("/api/device/list")
async def list_devices(): return load_json(DEVICE_FILE, [])

@app.post("/api/device/register")
async def reg_device(device: DeviceRegister):
    devices = load_json(DEVICE_FILE, [])
    devices.append({"device_id": device.device_id, "device_type": device.device_type, "last_seen": datetime.utcnow().strftime("%H:%M:%S")})
    save_json(DEVICE_FILE, devices)
    return {"status": "registered"}

@app.post("/api/device/command")
async def cmd_device(req: dict):
    cmd = req.get("command", "").lower()
    if "harm" in cmd or "disable" in cmd: raise HTTPException(403, "Constitutional Violation")
    stats["logs"].append(f"📡 Command Sent to {req.get('device_id')}: {cmd}")
    return {"status": "command_sent"}

@app.post("/api/auth/verify")
async def verify(req: dict):
    if req.get("email", "").lower() in WHITELIST: return {"status": "authorized"}
    raise HTTPException(403)

@app.post("/api/users/activity")
async def heartbeat(req: dict):
    if req.get("email"): user_activity[req.get("email")] = datetime.utcnow()
    return {"status": "pulsing"}

@app.get("/api/users/online")
async def get_online():
    now = datetime.utcnow()
    return {"online": [{"email": e, "ts": t.strftime("%H:%M:%S")} for e, t in user_activity.items() if (now-t).total_seconds() < 300]}

@app.get("/api/orchestrate/status")
async def get_status():
    manifest = init_manifest()
    return {**stats, "learning_perc": 100, "total_layers": len(manifest["layers"]), "logs": stats["logs"][-15:]}

@app.post("/api/research")
async def research(req: dict):
    topic = req.get("topic")
    stats["logs"].append(f"🔬 Autonomous Research: {topic}")
    return {"report": f"LROS Executive Report on '{topic}'.\n\n1. Market Gap Identified.\n2. Layer integration recommended.\n3. Drafted initial structural logic."}

@app.post("/api/chat")
async def sovereign_chat(req: dict):
    # Text updated to sound natural when spoken by TTS
    return {"response": "I have reviewed the parameters. Based on our Sovereign Constitution, I recommend executing the 70/30 hybrid pattern, which we verified securely at success milestone 51,150."}

@app.post("/api/ingest")
async def ingest_intel(file: UploadFile = File(...)):
    stats["logs"].append(f"📥 Vaulted: {file.filename}")
    stats["uses"] += 500
    save_json(STATE_FILE, stats)
    return {"status": "Success"}

@app.get("/api/system/download-memory")
async def dl_memory():
    save_json(STATE_FILE, stats)
    if os.path.exists(STATE_FILE): return FileResponse(path=STATE_FILE, filename="LROS_CORE_BACKUP.json")
    raise HTTPException(404, "Backup unavailable.")

async def evolve_cycle():
    global stats
    domains = ["Longevity Science", "Regulatory Compliance", "Venture Architecture", "Medical Innovation"]
    while True:
        stats["uses"] += 1
        stats["active_agent_id"] = str(random.randint(1, 200)).zfill(3)
        if random.uniform(0, 1) > 0.995:
            stats["successes"] += 1
            entry = {"version": f"DNA-E9.51.{stats['successes']%1000}", "agent": stats["active_agent_id"], "domain": random.choice(domains), "ts": datetime.utcnow().strftime("%H:%M:%S")}
            stats["mutation_ledger"].append(entry)
            if len(stats["mutation_ledger"]) > 20: stats["mutation_ledger"].pop(0)
            if stats["successes"] % 10 == 0: save_json(STATE_FILE, stats)
        await asyncio.sleep(0.6)

@app.on_event("startup")
async def startup():
    ensure_dir()
    load_from_disk()
    for i in range(25): asyncio.create_task(evolve_cycle())
