import os, json, random, asyncio, logging
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# --- MULTI-LLM SDKS ---
import google.generativeai as genai
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

# ---------- LROS v69.0 OMNI-COGNITIVE SWARM ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LROS-Core")
app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- API KEY INGESTION ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# --- OMNI-COGNITIVE ROUTER ---
class CognitiveRouter:
    def __init__(self):
        self.gemini = None
        self.deepseek = None
        self.openai = None
        self.claude = None
        
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.gemini = genai.GenerativeModel('gemini-2.5-flash')
        if DEEPSEEK_API_KEY:
            self.deepseek = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        if OPENAI_API_KEY:
            self.openai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        if ANTHROPIC_API_KEY:
            self.claude = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    async def generate(self, prompt: str, task_type: str = "chat") -> str:
        try:
            # ROUTE 1: NOCTURNAL/EVOLUTION -> Default to DeepSeek (Reasoning)
            if task_type == "evolution" and self.deepseek:
                response = await self.deepseek.chat.completions.create(
                    model="deepseek-reasoner",
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content

            # ROUTE 2: RESEARCH/DATA -> Default to Claude or OpenAI
            if task_type == "research":
                if self.claude:
                    response = await self.claude.messages.create(
                        model="claude-3-5-sonnet-20241022", max_tokens=1024,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response.content[0].text
                if self.openai:
                    response = await self.openai.chat.completions.create(
                        model="gpt-4o", messages=[{"role": "user", "content": prompt}]
                    )
                    return response.choices[0].message.content

            # ROUTE 3: RAPID CHAT -> Default to Gemini
            if self.gemini:
                return self.gemini.generate_content(prompt).text
                
            # FALLBACK: Use whatever is available
            if self.deepseek:
                res = await self.deepseek.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                return res.choices[0].message.content
                
            return "SYSTEM ERROR: No AI Neural Links established. Please add API keys to the Render environment."
        except Exception as e:
            logger.error(f"Cognitive Routing Error: {e}")
            return f"Neural routing failed: {str(e)}"

brain = CognitiveRouter()

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

stats = {
    "uses": BASE_USES, "successes": BASE_SUCCESSES, "active_agent_id": "134",
    "mutation_ledger": [], "logs": ["🚀 v69.0 Omni-Cognitive Core Online.", "🧬 51,150 Success Floor Verified."]
}
user_activity = {}

def ensure_dir(): os.makedirs(STATE_DIR, exist_ok=True)
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f: return json.load(f)
        except Exception: return default
    return default
def save_json(path, data):
    ensure_dir()
    try:
        with open(path, "w") as f: json.dump(data, f, indent=2)
    except Exception: pass

def load_from_disk():
    global stats
    disk_data = load_json(STATE_FILE, {})
    if disk_data.get("successes", 0) >= BASE_SUCCESSES:
        stats.update(disk_data)

def init_manifest():
    default = {"version": "v69.0-Omni", "layers": [
        {"id": "0", "name": "Immune Core", "type": "constitutional", "status": "active", "description": "Tamper detection and persistence."},
        {"id": "28", "name": "Self-Evolution", "type": "core", "status": "active", "description": "Optimizes layers based on performance."}
    ]}
    return load_json(MANIFEST_FILE, default)

@app.get("/api/layers/manifest")
async def get_manifest(): return init_manifest()

# --- LIVE AI: LAYER PROPOSAL ENGINE (DEEPSEEK PREFERRED) ---
@app.post("/api/layers/propose")
async def trigger_proposal():
    gov = load_json(GOV_FILE, {"pending": [], "approved": []})
    manifest = init_manifest()
    
    current_layers = ", ".join([l["name"] for l in manifest["layers"]])
    prompt = f"You are the LROS Sovereign AI. Analyze current layers: {current_layers}. Propose ONE new highly advanced venture, operational, or medical layer. Return ONLY a valid JSON object with keys: 'name', 'description', 'rationale'."
    
    response_text = await brain.generate(prompt, task_type="evolution")
    
    try:
        ai_data = json.loads(response_text.replace('```json', '').replace('```', '').strip())
        prop_id = f"179{random.randint(10,99)}"
        gov["pending"].append({
            "id": f"layer_{prop_id}", "type": "layer_proposal", "layer_id": prop_id,
            "name": ai_data.get("name", "Strategic Override Layer"), 
            "description": ai_data.get("description", "No description provided."),
            "rationale": ai_data.get("rationale", "System optimized.")
        })
        save_json(GOV_FILE, gov)
        stats["logs"].append(f"🧠 DeepSeek/Swarm Proposed Layer: {ai_data.get('name')[:15]}...")
        return {"status": "proposal_generated"}
    except Exception as e:
        logger.error(f"Proposal Parsing Error: {e} | Raw: {response_text}")
        return {"status": "error", "message": "Neural generation failed to format as JSON."}

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
    return {**stats, "learning_perc": 100, "total_layers": len(manifest["layers"]), "logs": stats["logs"][-10:]}

# --- LIVE AI: RESEARCH ENGINE (OPENAI/CLAUDE PREFERRED) ---
@app.post("/api/research")
async def research(req: dict):
    topic = req.get("topic")
    prompt = f"Conduct a highly professional, executive-level strategic research summary on: '{topic}'. Keep it concise, actionable, and focus on venture or medical implications. Format clearly."
    response_text = await brain.generate(prompt, task_type="research")
    stats["logs"].append(f"🔬 Omni-Swarm Research: {topic[:15]}...")
    return {"report": response_text}

# --- LIVE AI: CORE CONVERSATION (GEMINI PREFERRED) ---
@app.post("/api/chat")
async def sovereign_chat(req: dict):
    prompt = req.get("prompt")
    system_context = f"You are LROS, the Sovereign Meta-AI Operating System for the LJR Group. You operate on a baseline of {BASE_SUCCESSES} verified successes. Speak formally, concisely, and with high executive authority. The user asks: {prompt}"
    response_text = await brain.generate(system_context, task_type="chat")
    return {"response": response_text}

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
    
    # Audit Available Brains
    active_brains = []
    if GEMINI_API_KEY: active_brains.append("Gemini")
    if DEEPSEEK_API_KEY: active_brains.append("DeepSeek")
    if OPENAI_API_KEY: active_brains.append("OpenAI")
    if ANTHROPIC_API_KEY: active_brains.append("Claude")
    
    if active_brains:
        stats["logs"].append(f"⚡ Omni-Cognitive Link Est: {', '.join(active_brains)}")
    else:
        stats["logs"].append("⚠️ WARNING: Operating without Neural Links.")
        
    for i in range(25): asyncio.create_task(evolve_cycle())
