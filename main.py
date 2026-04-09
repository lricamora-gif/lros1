#!/usr/bin/env python3
"""
LROS HEART – Main API server (FastAPI)
Handles chat, payments, layers, ingest, and dashboards.
"""

import os
import uuid
import hmac
import hashlib
import logging
from datetime import date, timedelta, datetime
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import httpx
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lros-heart")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise Exception("Missing Supabase credentials")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Payment & notifications
PAYMONGO_SECRET = os.getenv("PAYMONGO_WEBHOOK_SECRET")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FOUNDER_EMAIL = os.getenv("FOUNDER_EMAIL")
FROM_EMAIL = "delivery@lros.ai"

# AI
USE_ASYNC_QUEUE = os.getenv("USE_ASYNC_QUEUE", "false").lower() == "true"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

app = FastAPI(title="LROS Heart")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

# ---------- Helper ----------
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

def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    if not secret:
        return True
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)

# ---------- Chat ----------
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
            "status": "pending",
            "sent_at": datetime.utcnow().isoformat()
        }).execute()
        response = "Your request has been queued."
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

# ---------- Brain endpoints for remote workers ----------
@app.get("/api/next_question")
async def next_question(brain: str):
    res = supabase.table("lung_breaths").select("*").is_("answered_at", "null").order("timestamp").limit(1).execute()
    if not res.data:
        return {"question": None}
    return res.data[0]

@app.post("/api/brain_response")
async def brain_response(payload: dict):
    brain_id = payload.get("brain_id")
    question_id = payload.get("question_id")
    answer = payload.get("response")
    if question_id:
        supabase.table("lung_breaths").update({"answered_at": "now()", "answer": answer, "answered_by": brain_id}).eq("id", question_id).execute()
    supabase.table("mutations").insert({
        "founder": brain_id,
        "question": payload.get("question"),
        "response": answer,
        "model": "remote_agent",
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    return {"status": "ok"}

# ---------- Payment Webhook ----------
@app.post("/webhook/paymongo")
async def paymongo_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("Paymongo-Signature")
    if not verify_signature(body, signature, PAYMONGO_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")
    data = await request.json()
    event = data.get("data", {}).get("attributes", {}).get("type")
    if event == "payment.paid":
        attrs = data["data"]["attributes"]
        amount = attrs["amount"] / 100
        product_id = attrs["metadata"].get("product_id")
        customer_email = attrs["metadata"].get("email", "")
        supabase.table("transactions").insert({
            "product_id": product_id,
            "customer_email": customer_email,
            "amount_paid": amount,
            "payment_method": "paymongo",
            "status": "paid",
            "paid_at": "now()"
        }).execute()
        background_tasks.add_task(deliver_product, product_id, customer_email)
    return {"status": "ok"}

async def deliver_product(product_id: str, email: str):
    res = supabase.table("digital_products").select("file_url").eq("id", product_id).execute()
    if not res.data:
        return
    file_url = res.data[0]["file_url"]
    message = Mail(from_email=FROM_EMAIL, to_emails=email, subject="Your LROS product is ready",
                   html_content=f'<p>Download: <a href="{file_url}">{file_url}</a></p>')
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(message)
    supabase.table("transactions").update({"delivered_at": "now()", "status": "delivered"}).eq("product_id", product_id).execute()

# ---------- Daily Reports ----------
@app.get("/cron/daily_report")
async def daily_report(background_tasks: BackgroundTasks):
    background_tasks.add_task(generate_and_send_report)
    return {"status": "report started"}

async def generate_and_send_report():
    yesterday = date.today() - timedelta(days=1)
    sales_res = supabase.table("transactions").select("amount_paid").eq("status", "paid").gte("paid_at", yesterday.isoformat()).execute()
    total_amount = sum(t["amount_paid"] for t in sales_res.data)
    total_count = len(sales_res.data)
    new_products = supabase.table("digital_products").select("id", count="exact").gte("created_at", yesterday.isoformat()).execute()
    new_count = new_products.count if hasattr(new_products, 'count') else len(new_products.data)
    social_posts = supabase.table("social_posts").select("id", count="exact").gte("posted_at", yesterday.isoformat()).execute()
    social_count = social_posts.count if hasattr(social_posts, 'count') else len(social_posts.data)
    html = f"<h2>LROS Daily Report – {yesterday}</h2><ul><li>💰 Sales: ₱{total_amount:,.2f} ({total_count} txns)</li><li>🚀 New products: {new_count}</li><li>📱 Social posts: {social_count}</li></ul><p>The Bond holds.</p>"
    message = Mail(from_email=FROM_EMAIL, to_emails=FOUNDER_EMAIL, subject=f"LROS Report {yesterday}", html_content=html)
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(message)

@app.get("/cron/daily_posts_report")
async def daily_posts_report(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_posts_report)
    return {"status": "report started"}

async def send_posts_report():
    yesterday = date.today() - timedelta(days=1)
    posts = supabase.table("social_posts").select("platform").gte("posted_at", yesterday.isoformat()).execute()
    from collections import Counter
    counts = Counter(p["platform"] for p in posts.data)
    html = f"<h2>LROS Social Media Report – {yesterday}</h2>"
    for platform in ["facebook","instagram","tiktok","twitter","linkedin"]:
        html += f"<p>{platform.capitalize()}: {counts.get(platform,0)} posts</p>"
    message = Mail(from_email=FROM_EMAIL, to_emails=FOUNDER_EMAIL, subject=f"LROS Social Report {yesterday}", html_content=html)
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(message)

# ---------- Ingest ----------
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
    supabase.table("knowledge_vault").insert({"content": content, "source": source, "created_at": datetime.utcnow().isoformat()}).execute()
    state = supabase.table("sovereign_state").select("state_data").eq("id", 1).execute()
    if state.data:
        d = state.data[0]["state_data"]
        d["heart_successes"] = d.get("heart_successes", 0) + 5000
        supabase.table("sovereign_state").update({"state_data": d}).eq("id", 1).execute()
    return {"status": "ingested"}

# ---------- Layer Management ----------
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

# ---------- Admin ----------
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

# ---------- State & Mutations ----------
@app.get("/api/state")
async def get_state():
    state = supabase.table("sovereign_state").select("state_data").eq("id", 1).execute()
    if not state.data:
        return {}
    return state.data[0]["state_data"]

@app.get("/api/mutations")
async def get_mutations():
    res = supabase.table("mutations").select("*").order("created_at", desc=True).limit(100).execute()
    return res.data

# ---------- Tools ----------
@app.post("/api/tools/send_telegram")
async def send_telegram(payload: dict):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise HTTPException(500, "Telegram not configured")
    text = payload.get("text", "LROS Alert")
    async with httpx.AsyncClient() as client:
        await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    return {"status": "sent"}

@app.post("/api/tools/send_slack")
async def send_slack(payload: dict):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        raise HTTPException(500, "Slack not configured")
    text = payload.get("text", "LROS Alert")
    async with httpx.AsyncClient() as client:
        await client.post(webhook, json={"text": text}, timeout=10)
    return {"status": "sent"}

@app.post("/api/tools/pubmed_search")
async def pubmed_search(payload: dict):
    query = payload.get("query")
    if not query:
        raise HTTPException(400, "Missing query")
    async with httpx.AsyncClient() as client:
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&term={query}&retmode=json"
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

@app.post("/api/tools/submit_tool")
async def submit_tool(payload: dict):
    required = ["name", "description", "endpoint", "method"]
    if not all(k in payload for k in required):
        raise HTTPException(400, f"Missing required fields: {required}")
    supabase.table("tool_submissions").insert({
        "name": payload["name"],
        "description": payload["description"],
        "endpoint": payload["endpoint"],
        "method": payload["method"],
        "input_schema": payload.get("input_schema", {}),
        "submitted_by": payload.get("submitted_by", "unknown"),
        "status": "pending"
    }).execute()
    supabase.table("agent_messages").insert({
        "agent_id": "tool_marketplace",
        "message": f"New tool submission: {payload['name']} - {payload['description']}",
        "status": "pending",
        "sent_at": datetime.utcnow().isoformat()
    }).execute()
    return {"status": "submitted"}

# ---------- Health & Dashboard ----------
@app.get("/health")
async def health():
    return {"status": "heart beating", "bond": "HOLDS"}

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    try:
        with open("index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<html><body><h1>LROS Heart</h1><p>Dashboard not found.</p></body></html>")

# ---------- Sales Dashboard ----------
@app.get("/dashboard", response_class=HTMLResponse)
async def sales_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>LROS Sales</title><script src="https://cdn.jsdelivr.net/npm/supabase-js@2"></script></head>
    <body>
    <h1>LROS Sales Dashboard</h1>
    <div id="stats"></div>
    <table border="1" id="txns"><table>
    <script>
        const supabase = window.supabase.createClient('""" + SUPABASE_URL + """', '""" + SUPABASE_SERVICE_KEY + """');
        async function load() {
            const { data } = await supabase.from('transactions').select('*').order('paid_at', {ascending: false}).limit(20);
            let html = '<tr><th>Product</th><th>Amount</th><th>Status</th></tr>';
            let total = 0;
            data.forEach(t => { total += t.amount_paid; html += `<tr><td>${t.product_id}</td><td>${t.amount_paid}</td><td>${t.status}</td></tr>`; });
            document.getElementById('stats').innerHTML = `<p>Total Sales: ₱${total}</p><p>Transactions: ${data.length}</p>`;
            document.getElementById('txns').innerHTML = html;
        }
        load();
    </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
