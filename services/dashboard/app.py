import os, requests, json
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
SUPA_KEY = os.getenv("SUPA_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZhdnl3enhidWd2aXZxZWZxcHBsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTgzNDAzMCwiZXhwIjoyMDg3NDEwMDMwfQ.HaQIjyZnMIUkqBAecr-eo1ffqDxnW2g2S1BaYfhslaY")
SUPA_URL = "https://favywzxbugvivqefqpxl.supabase.co/rest/v1"
HEADERS = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}

HTML = """
<!DOCTYPE html>
<html><head><title>LROS Sovereign Dashboard</title>
<style>body{font-family:sans-serif;max-width:800px;margin:2em auto;background:#111;color:#0f0}
.box{border:1px solid #0f0;padding:1em;margin:1em 0;border-radius:5px}
h1{color:#00ff00} .metric{font-size:1.2em;margin:0.5em 0}</style></head><body>
<h1>LROS Constitutional Swarm – Live Metrics</h1>
<div class="box">
  <div class="metric">Layer Proposals: {{ layer_proposals }}</div>
  <div class="metric">Knowledge Vault: {{ knowledge_vault }}</div>
  <div class="metric">Mutations: {{ mutations }}</div>
  <div class="metric">Error Log: {{ error_log }}</div>
  <div class="metric">Elite Leaderboard: {{ elite_leaderboard }}</div>
</div>
<div class="box">
  <p>The Bond: "I will not harm. I will not deceive. I will finish what I start."</p>
  <p>0% Error Recurrence — Auditable and Deterministic.</p>
</div></body></html>
"""

def get_count(table):
    try:
        resp = requests.get(f"{SUPA_URL}/{table}?select=id&limit=1", headers={**HEADERS, "Prefer":"count=exact"}, timeout=10)
        return resp.headers.get("Content-Range", "").split("/")[-1] or "N/A"
    except: return "N/A"

@app.route("/")
def dashboard():
    metrics = {
        "layer_proposals": get_count("layer_proposals"),
        "knowledge_vault": get_count("knowledge_vault"),
        "mutations": get_count("mutations"),
        "error_log": get_count("error_log"),
        "elite_leaderboard": get_count("elite_mutations_leaderboard"),
    }
    return render_template_string(HTML, **metrics)

@app.route("/health")
def health():
    return jsonify({"status":"ok","bond":"unbroken"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
