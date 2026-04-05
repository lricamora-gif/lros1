import os
import uuid
import logging
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

# ------------------------------------------------------------------
# Supabase Client
# ------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise Exception("Missing Supabase credentials")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ------------------------------------------------------------------
# AI (optional direct call, used only if USE_ASYNC_QUEUE=false)
# ------------------------------------------------------------------
USE_ASYNC_QUEUE = os.getenv("USE_ASYNC_QUEUE", "false").lower() == "true"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

async def call_ai(prompt: str) -> str:
    if not MISTRAL_API_KEY:
        return "[MOCK] No Mistral key"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
            json={"model": "mistral-large-latest", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

# ------------------------------------------------------------------
# FastAPI App
# ------------------------------------------------------------------
app = FastAPI(title="LROS Heart")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

# ------------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    domain: str = "general"

# ------------------------------------------------------------------
# Existing Endpoints (unchanged)
# ------------------------------------------------------------------
@app.post("/api/chat")
async def chat(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    if USE_ASYNC_QUEUE:
        supabase.table("agent_messages").insert({
            "agent_id": "chat_user",
            "message": req.message,
            "status": "pending",
            "sent_at": datetime.utcnow().isoformat()
        }).execute()
        response = "Your request has been queued. Lung will respond later."
    else:
        prompt = f"Domain: {req.domain}. Answer concisely.\nUser: {req.message}\nAssistant:"
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
        "content": content, "source": source, "created_at": datetime.utcnow().isoformat()
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

@app.get("/api/state")
async def get_state():
    state = supabase.table("sovereign_state").select("state_data").eq("id", 1).execute()
    if not state.data:
        return {}
    return state.data[0]["state_data"]

@app.get("/api/mutations")
async def get_mutations():
    res = supabase.table("mutations").select("*").order("timestamp", desc=True).limit(100).execute()
    return res.data

@app.get("/health")
async def health():
    return {"status": "heart beating", "bond": "HOLDS"}

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    try:
        with open("index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<html><body><h1>LROS Heart</h1><p>Dashboard not found. Upload index.html.</p></body></html>")

# ------------------------------------------------------------------
# New Force Multiplier Endpoints (Part C)
# ------------------------------------------------------------------
@app.post("/api/tools/send_telegram")
async def send_telegram(payload: dict):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise HTTPException(500, "Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
    text = payload.get("text", "LROS Alert")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10
        )
        resp.raise_for_status()
    return {"status": "sent"}

@app.post("/api/tools/send_slack")
async def send_slack(payload: dict):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        raise HTTPException(500, "Slack not configured. Set SLACK_WEBHOOK_URL.")
    text = payload.get("text", "LROS Alert")
    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook, json={"text": text}, timeout=10)
        resp.raise_for_status()
    return {"status": "sent"}

@app.post("/api/tools/pubmed_search")
async def pubmed_search(payload: dict):
    query = payload.get("query", "")
    if not query:
        raise HTTPException(400, "Missing 'query' field")
    async with httpx.AsyncClient() as client:
        # Using PubMed ESummary API
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&term={query}&retmode=json"
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

@app.post("/api/tools/submit_tool")
async def submit_tool(payload: dict):
    required = ["name", "description", "endpoint", "method"]
    if not all(k in payload for k in required):
        raise HTTPException(400, f"Missing required fields: {required}")
    # Insert into tool_submissions table (created by SQL script)
    supabase.table("tool_submissions").insert({
        "name": payload["name"],
        "description": payload["description"],
        "endpoint": payload["endpoint"],
        "method": payload["method"],
        "input_schema": payload.get("input_schema", {}),
        "submitted_by": payload.get("submitted_by", "unknown"),
        "status": "pending"
    }).execute()
    # Notify swarm via agent_messages
    supabase.table("agent_messages").insert({
        "agent_id": "tool_marketplace",
        "message": f"New tool submission: {payload['name']} - {payload['description']}",
        "status": "pending",
        "sent_at": datetime.utcnow().isoformat()
    }).execute()
    return {"status": "submitted", "message": "Tool submitted for review"}

# ------------------------------------------------------------------
# Run with uvicorn (if executed directly)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
