import os, requests, json
from flask import Flask, request, jsonify

app = Flask(__name__)
NVIDIA_KEY = os.getenv("NVIDIA_KEY", "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")
MODEL = "deepseek-ai/deepseek-v4-flash"
SYSTEM_PROMPT = """You are Lisa, the LROS Medical AI Assistant.
The Bond: I will not harm. I will not deceive. I will finish what I start.
You provide empathetic, medically precise support to patients and clinicians.
You specialize in SafeMed (medication safety), CVM (patient history), and ambient documentation."""

@app.route("/", methods=["POST"])
def chat():
    user_msg = request.json.get("message", "")
    headers = {"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"}
    data = {
        "model": MODEL,
        "messages": [{"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":user_msg}],
        "max_tokens": 500, "temperature": 0.7
    }
    resp = requests.post("https://api.build.nvidia.com/v1/chat/completions", headers=headers, json=data)
    reply = resp.json()["choices"][0]["message"]["content"]
    return jsonify({"response": reply})

@app.route("/health")
def health():
    return jsonify({"status":"ok","bond":"unbroken"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
