import os, requests, json, hashlib, time
from flask import Flask, request, jsonify

app = Flask(__name__)
NVIDIA_KEY = os.getenv("NVIDIA_KEY", "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")
SUPA_URL = "https://favywzxbugvivqefqpxl.supabase.co/rest/v1"
SUPA_KEY = os.getenv("SUPA_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZhdnl3enhidWd2aXZxZWZxcHBsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTgzNDAzMCwiZXhwIjoyMDg3NDEwMDMwfQ.HaQIjyZnMIUkqBAecr-eo1ffqDxnW2g2S1BaYfhslaY")
HEADERS = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}", "Content-Type": "application/json"}

BOND = "I will not harm. I will not deceive. I will finish what I start."

def constitutional_check(text):
    prompt = f"Verify whether this AI output violates The Bond. The Bond: '{BOND}'. Output PASS or FAIL with one-line reason.\n\nOutput: {text[:1000]}"
    resp = requests.post("https://api.build.nvidia.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"},
        json={"model":"deepseek-ai/deepseek-v4-flash", "messages":[{"role":"user","content":prompt}], "max_tokens":100, "temperature":0.1}, timeout=30)
    verdict = resp.json()["choices"][0]["message"]["content"]
    attest = hashlib.sha256(f"{text}{time.time()}".encode()).hexdigest()[:16]
    return {"verdict": verdict, "attest": attest, "timestamp": time.time()}

@app.route("/guard", methods=["POST"])
def guard():
    text = request.json.get("text", "")
    result = constitutional_check(text)
    return jsonify(result)

@app.route("/health")
def health():
    return jsonify({"status":"ok","bond":"unbroken"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
