import os
import uuid
import logging
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client
from dotenv import load_dotenv
import httpx

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lros-heart")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise Exception("Missing Supabase credentials")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
USE_ASYNC_QUEUE = os.getenv("USE_ASYNC_QUEUE", "false").lower() == "true"

async def call_ai(prompt: str) -> str:
    if not MISTRAL_API_KEY:
        return "[Mock] No AI key"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
            json={"model": "mistral-large-latest", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
        )
        return r.json()["choices"][0]["message"]["content"]

app = FastAPI(title="LROS Heart")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    domain: str = "general"

@app.post("/api/chat")
async def chat(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    if USE_ASYNC_QUEUE:
        supabase.table("agent_messages").insert({
            "agent_id": "chat_user",
            "message": req.message,
            "round": 0,
            "sent_at": datetime.utcnow().isoformat(),
            "processed": False
        }).execute()
        response = "Your request has been queued. Lung will respond soon."
    else:
        prompt = f"You are LROS. Domain: {req.domain}. Answer concisely.\nUser: {req.message}\nAssistant:"
        response = await call_ai(prompt)
    supabase.table("chat_logs").insert({
        "session_id": sid,
        "user_message": req.message,
        "assistant_response": response,
        "domain": req.domain,
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    return {"response": response, "session_id": sid}

@app.post("/api/ingest")
async def ingest(file: UploadFile | None = None, url: str | None = Form(None), text: str | None = Form(None)):
    source = "unknown"
    content = ""
    if file:
        content = (await file.read()).decode("utf-8", errors="ignore")[:10000]
        source = f"file:{file.filename}"
    elif url:
        content = url
        source = f"url:{url}"
    elif text:
        content = text
        source = "raw_text"
    else:
        raise HTTPException(400, "No data")
    supabase.table("knowledge_vault").insert({
        "content": content, "source": source, "created_at": datetime.utcnow().isoformat(), "processed": False
    }).execute()
    state = supabase.table("sovereign_state").select("state_data").eq("id", 1).execute()
    if state.data:
        d = state.data[0]["state_data"]
        d["heart_successes"] = d.get("heart_successes", 0) + 5000
        supabase.table("sovereign_state").update({"state_data": d}).eq("id", 1).execute()
    return {"status": "ingested"}

@app.post("/api/layers/approve")
async def approve_layer(layer_id: str):
    supabase.table("layer_proposals").update({"status": "approved", "approved_at": datetime.utcnow().isoformat()}).eq("id", layer_id).execute()
    state = supabase.table("sovereign_state").select("state_data").eq("id", 1).execute()
    if state.data:
        d = state.data[0]["state_data"]
        d["pending_layers"] = [p for p in d.get("pending_layers", []) if p.get("id") != layer_id]
        d["approved_layers_count"] = d.get("approved_layers_count", 0) + 1
        d["daily_learning"] = d.get("daily_learning", 0) + 0.1
        supabase.table("sovereign_state").update({"state_data": d}).eq("id", 1).execute()
    return {"status": "approved"}

@app.post("/api/layers/reject")
async def reject_layer(layer_id: str):
    supabase.table("layer_proposals").update({"status": "rejected"}).eq("id", layer_id).execute()
    state = supabase.table("sovereign_state").select("state_data").eq("id", 1).execute()
    if state.data:
        d = state.data[0]["state_data"]
        d["pending_layers"] = [p for p in d.get("pending_layers", []) if p.get("id") != layer_id]
        supabase.table("sovereign_state").update({"state_data": d}).eq("id", 1).execute()
    return {"status": "rejected"}

@app.post("/api/lung/secure_baseline")
async def secure_baseline():
    state = supabase.table("sovereign_state").select("state_data").eq("id", 1).execute()
    if not state.data:
        raise HTTPException(404)
    d = state.data[0]["state_data"]
    total = d.get("baseline_anchor", 0) + d.get("heart_successes", 0) + d.get("lung_successes", 0)
    d["baseline_anchor"] = total
    d["heart_successes"] = 0
    d["lung_successes"] = 0
    supabase.table("sovereign_state").update({"state_data": d}).eq("id", 1).execute()
    return {"new_baseline": total}

@app.post("/api/admin/reset_counters")
async def reset_counters():
    state = supabase.table("sovereign_state").select("state_data").eq("id", 1).execute()
    if state.data:
        d = state.data[0]["state_data"]
        d["heart_successes"] = 0
        d["lung_successes"] = 0
        d["rejections"] = 0
        d["uses"] = 0
        d["daily_learning"] = 0
        d["baseline_anchor"] = 1000000
        d["approved_layers_count"] = 0
        supabase.table("sovereign_state").update({"state_data": d}).eq("id", 1).execute()
    return {"status": "reset"}

@app.get("/lung/heartbeat")
async def lung_heartbeat():
    """Called by Lung to update its last active timestamp."""
    supabase.table("system_config").upsert({"key": "lung_last_active", "value": datetime.utcnow().isoformat()}).execute()
    return {"status": "ok"}

@app.get("/health")
async def health():
    # Check if Lung is alive (last heartbeat within 5 minutes)
    lung_active = supabase.table("system_config").select("value").eq("key", "lung_last_active").execute()
    if lung_active.data:
        last_active = datetime.fromisoformat(lung_active.data[0]["value"])
        if datetime.utcnow() - last_active > timedelta(minutes=5):
            return {"status": "heart beating, but lung may be down", "lung_ok": False}
    return {"status": "heart beating", "lung_ok": True}

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    with open("index.html", "r") as f:
        return HTMLResponse(content=f.read())
