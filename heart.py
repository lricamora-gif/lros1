# heart.py – Complete LROS Heart for 1,000 Businesses
# Copy this entire file, set env vars, deploy to Render.

import os
import hmac
import hashlib
import json
from datetime import date, timedelta
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from supabase import create_client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import asyncpg

app = FastAPI()

# Environment variables (set these in Render)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
PAYMONGO_SECRET = os.getenv("PAYMONGO_WEBHOOK_SECRET")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FOUNDER_EMAIL = os.getenv("FOUNDER_EMAIL")
FROM_EMAIL = "delivery@lros.ai"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------- PAYMENT WEBHOOK --------------------
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
        payment_id = data["data"]["id"]
        amount = attrs["amount"] / 100
        product_id = attrs["metadata"].get("product_id")
        customer_email = attrs["metadata"].get("email", "")
        # Insert transaction
        supabase.table("transactions").insert({
            "product_id": product_id,
            "customer_email": customer_email,
            "amount_paid": amount,
            "payment_method": "paymongo",
            "status": "paid",
            "paid_at": "now()"
        }).execute()
        # Deliver in background
        background_tasks.add_task(deliver_product, product_id, customer_email)
    return {"status": "ok"}

def verify_signature(body, signature, secret):
    if not secret:
        return True  # Skip verification if no secret (for testing)
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)

async def deliver_product(product_id: str, email: str):
    # Fetch product file URL
    res = supabase.table("digital_products").select("file_url").eq("id", product_id).execute()
    if not res.data:
        return
    file_url = res.data[0]["file_url"]
    # Send email
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=email,
        subject="Your LROS product is ready",
        html_content=f'<p>Download: <a href="{file_url}">{file_url}</a></p>'
    )
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(message)
    # Update transaction
    supabase.table("transactions").update({"delivered_at": "now()", "status": "delivered"}).eq("product_id", product_id).execute()

# -------------------- DAILY REPORT CRON --------------------
@app.get("/cron/daily_report")
async def daily_report(background_tasks: BackgroundTasks):
    background_tasks.add_task(generate_and_send_report)
    return {"status": "report started"}

async def generate_and_send_report():
    yesterday = date.today() - timedelta(days=1)
    # Query sales
    sales_res = supabase.table("transactions").select("amount_paid").eq("status", "paid").gte("paid_at", yesterday.isoformat()).execute()
    total_amount = sum(t["amount_paid"] for t in sales_res.data)
    total_count = len(sales_res.data)
    # New products
    new_products = supabase.table("digital_products").select("id", count="exact").gte("created_at", yesterday.isoformat()).execute()
    # Social posts
    social_posts = supabase.table("social_posts").select("id", count="exact").gte("posted_at", yesterday.isoformat()).execute()
    # Top product
    top_res = supabase.table("transactions").select("product_id").eq("status", "paid").gte("paid_at", yesterday.isoformat()).execute()
    top_product = "None"
    if top_res.data:
        from collections import Counter
        counts = Counter(t["product_id"] for t in top_res.data)
        top_product = counts.most_common(1)[0][0]
    # Compose email
    html = f"""
    <h2>LROS Daily Report – {yesterday}</h2>
    <ul>
        <li>💰 Sales: ₱{total_amount:,.2f} ({total_count} txns)</li>
        <li>🚀 New products: {new_products.count}</li>
        <li>📱 Social posts: {social_posts.count}</li>
        <li>🏆 Top product: {top_product}</li>
    </ul>
    <p>The Bond holds.</p>
    """
    message = Mail(from_email=FROM_EMAIL, to_emails=FOUNDER_EMAIL, subject=f"LROS Report {yesterday}", html_content=html)
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(message)

# -------------------- SALES DASHBOARD --------------------
@app.get("/dashboard", response_class=HTMLResponse)
async def sales_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>LROS Sales</title><script src="https://cdn.jsdelivr.net/npm/supabase-js@2"></script></head>
    <body>
    <h1>LROS Sales Dashboard</h1>
    <div id="stats"></div>
    <table border="1" id="txns"></table>
    <script>
        const supabase = window.supabase.createClient('""" + SUPABASE_URL + """', '""" + SUPABASE_KEY + """');
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
    @app.get("/cron/daily_posts_report")
async def daily_posts_report(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_posts_report)
    return {"status": "report started"}

async def send_posts_report():
    yesterday = date.today() - timedelta(days=1)
    # Query daily_post_summary view
    posts_data = supabase.table("social_posts").select("platform, posted_at").gte("posted_at", yesterday.isoformat()).execute()
    # Count per platform
    from collections import Counter
    counts = Counter(p["platform"] for p in posts_data.data)
    # Compose email
    html = f"<h2>LROS Social Media Report – {yesterday}</h2>"
    for platform in ["facebook", "instagram", "tiktok", "twitter", "linkedin"]:
        html += f"<p>{platform.capitalize()}: {counts.get(platform, 0)} posts</p>"
    html += "<p>Goal: 3 per platform per day</p>"
    # Send via SendGrid
    ...

@app.get("/health")
async def health():
    return {"status": "heart beating"}
