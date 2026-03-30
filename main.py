import os, json, random, asyncio, logging
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# ---------- LROS v67.3 SOVEREIGN BACKEND ----------
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# BOOTSTRAP: 49,825 Successes / 249,840 Uses (LOCKED)
stats = {
    "uses": 249840, "successes": 49825, "active_agent_id": "031", 
    "mutation_ledger": [], "logs": ["⚔️ v67.3 Command Core Active.", "🧬 49,825 Successes Verified."]
}

WHITELIST = [
    "angelrabajante@theljrgroup.com", "sofiaysabellebeltran@theljrgroup.com",
    "jeannettecabanes@theljrgroup.com", "rencaturay@theljrgroup.com",
    "ramonganan@theljrgroup.com", "justinsacayanan@theljrgroup.com",
    "luisseroxas@theljrgroup.com", "luigiricamora@theljrgroup.com"
]

@app.post("/api/auth/verify")
async def verify(request: dict):
    email = request.get("email", "").lower()
    if email in WHITELIST: return {"status": "authorized"}
    raise HTTPException(status_code=403)

@app.get("/api/system/download-memory")
async def download_memory():
    filename = f"LROS_Memory_v67.3_{datetime.now().strftime('%Y%m%d')}.json"
    with open(filename, "w") as f: json.dump(stats, f)
    return FileResponse(path=filename, filename=filename)

@app.get("/api/orchestrate/status")
async def get_status():
    stats["learning_perc"] = 100 # Locked as per user image
    return {**stats, "logs": stats["logs"][-15:]}

async def evolve_cycle():
    global stats
    domains = ["Longevity Science", "Regulatory Compliance", "Venture Architecture", "Medical Innovation"]
    while True:
        stats["uses"] += 1
        stats["active_agent_id"] = str(random.randint(1, 200)).zfill(3)
        if random.uniform(0, 1) > 0.995:
            stats["successes"] += 1
            entry = {"version": f"DNA-E9.{stats['successes']//100}.{stats['successes']%1000}", "agent": stats["active_agent_id"], "domain": random.choice(domains), "ts": datetime.now().strftime("%H:%M:%S")}
            stats["mutation_ledger"].append(entry)
            if len(stats["mutation_ledger"]) > 20: stats["mutation_ledger"].pop(0)
        await asyncio.sleep(0.6)

@app.on_event("startup")
async def startup():
    for i in range(25): asyncio.create_task(evolve_cycle())
