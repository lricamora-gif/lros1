import requests, json, time, os, random

SUPA_URL = "https://imhjkimjmuawmjkvaafj.supabase.co/rest/v1"
SUPA_KEY = os.getenv("SUPA_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImltaGppbWtqbXVhd21qa3ZhYWZqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwMDg0NSwiZXhwIjoyMDkwOTc2ODQ1fQ.Z6QCBjX7eLNaaizg9lj1KL-0hlcteWw1J0jbHN-NCb8")
NVIDIA_KEY = os.getenv("NVIDIA_KEY", "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")
HEADERS = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}

AGENTS = [
    ("sales","VP of Sales"), ("support","Customer Support Director"), ("billing","Chief Financial Officer"),
    ("compliance","Compliance Officer"), ("marketing","Chief Marketing Officer"), ("product","Chief Product Officer"),
    ("onboarding","Implementation Director"), ("finance","Financial Analyst"), ("legal","Head of Legal"),
    ("healthcare","Healthcare Partnerships Lead"), ("scaling","VP of Infrastructure"), ("security","CISO"),
    ("data","Chief Data Officer"), ("tax","Tax Strategy Officer")
]

def generate_plan(role):
    prompt = f"You are the LROS {role} autonomous business agent. The Bond holds. Provide a detailed, actionable business plan recommendation in 5 bullet points."
    resp = requests.post("https://api.build.nvidia.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"},
        json={"model":"deepseek-ai/deepseek-v4-flash", "messages":[{"role":"user","content":prompt}], "max_tokens":500, "temperature":0.7}, timeout=30)
    return resp.json()["choices"][0]["message"]["content"]

while True:
    for name, role in AGENTS:
        try:
            plan = generate_plan(role)
            payload = {"agent": name, "role": role, "plan": plan, "timestamp": time.time()}
            requests.post(f"{SUPA_URL}/business_plans", headers=HEADERS, json=payload)
        except Exception as e:
            print(f"{name} error: {e}")
        time.sleep(60)
