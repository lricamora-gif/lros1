from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import random
import openai
import google.generativeai as genai
import anthropic
import requests
import cohere
from datetime import datetime
from typing import Optional, List
import asyncio

app = FastAPI(title="LROS Ultimate Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# -------------------- API KEYS --------------------
openai.api_key = os.environ.get("OPENAI_API_KEY")
if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY")) if os.environ.get("ANTHROPIC_API_KEY") else None
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
cohere_client = cohere.Client(api_key=os.environ.get("COHERE_API_KEY")) if os.environ.get("COHERE_API_KEY") else None
WRITER_API_KEY = os.environ.get("WRITER_API_KEY")

# -------------------- PATTERN REGISTRY --------------------
PATTERN_FILE = "patterns.json"

def load_patterns():
    try:
        with open(PATTERN_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return [
        {"id": "p1", "prompt": "Explain {topic} in simple terms.", "temperature": 0.7, "rating": 0.5, "uses": 0},
        {"id": "p2", "prompt": "Write a detailed technical article about {topic}.", "temperature": 0.5, "rating": 0.5, "uses": 0},
        {"id": "p3", "prompt": "Give a creative story about {topic}.", "temperature": 0.9, "rating": 0.5, "uses": 0},
        {"id": "p4", "prompt": "Provide a legal analysis of {topic}.", "temperature": 0.6, "rating": 0.5, "uses": 0},
        {"id": "p5", "prompt": "Write code to solve {topic}.", "temperature": 0.4, "rating": 0.5, "uses": 0},
    ]

def save_patterns(patterns):
    with open(PATTERN_FILE, "w") as f:
        json.dump(patterns, f, indent=2)

# -------------------- MULTI‑AI CALLER --------------------
def call_ai(prompt, temperature=0.7, model="openai"):
    if model == "openai" and openai.api_key:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI error: {e}")
    if model == "gemini" and genai.api_key:
        try:
            gem_model = genai.GenerativeModel("gemini-1.5-flash")
            response = gem_model.generate_content(prompt, generation_config={"temperature": temperature})
            return response.text
        except Exception as e:
            print(f"Gemini error: {e}")
    if model == "claude" and anthropic_client:
        try:
            response = anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Claude error: {e}")
    if model == "deepseek" and DEEPSEEK_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
            payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": temperature}
            response = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers)
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"DeepSeek error: {e}")
    if model == "cohere" and cohere_client:
        try:
            response = cohere_client.generate(
                prompt=prompt,
                model="command-r-plus",
                temperature=temperature,
                max_tokens=1000
            )
            return response.generations[0].text
        except Exception as e:
            print(f"Cohere error: {e}")
    if model == "writer" and WRITER_API_KEY:
        try:
            headers = {"Authorization": WRITER_API_KEY, "Content-Type": "application/json"}
            payload = {
                "prompt": prompt,
                "model": "palmyra-instruct-30b",
                "temperature": temperature,
                "max_tokens": 1000
            }
            response = requests.post("https://api.writer.com/v1/completions", json=payload, headers=headers)
            return response.json()["completion"]
        except Exception as e:
            print(f"Writer error: {e}")
    return f"[Simulated] LROS would answer: {prompt[:100]}..."

# -------------------- FEEDBACK & EVOLUTION --------------------
class Feedback(BaseModel):
    pattern_id: str
    rating: float
    comment: Optional[str] = None
    context: Optional[str] = None

async def run_evolution_background():
    patterns = load_patterns()
    candidates = [p for p in patterns if p.get("uses", 0) > 5]
    if not candidates:
        print("Evolution: not enough data")
        return

    worst = min(candidates, key=lambda p: p["rating"])
    worst_rating = worst["rating"]
    mutations = [mutate_pattern(worst) for _ in range(3)]

    for m in mutations:
        m["rating"] = evaluate_pattern(m)

    best_mutation = max(mutations, key=lambda m: m["rating"])
    if best_mutation["rating"] > worst_rating:
        idx = patterns.index(worst)
        patterns[idx] = best_mutation
        save_patterns(patterns)
        print(f"Evolution succeeded! Improvement: {best_mutation['rating'] - worst_rating}")
    else:
        print("Evolution: no improvement")

@app.post("/api/feedback")
async def submit_feedback(feedback: Feedback, background_tasks: BackgroundTasks):
    patterns = load_patterns()
    for p in patterns:
        if p["id"] == feedback.pattern_id:
            p["uses"] = p.get("uses", 0) + 1
            old_uses = p["uses"] - 1
            if old_uses > 0:
                p["rating"] = (p["rating"] * old_uses + feedback.rating) / p["uses"]
            else:
                p["rating"] = feedback.rating
            break
    save_patterns(patterns)

    total_uses = sum(p.get("uses", 0) for p in patterns)
    if total_uses > 0 and total_uses % 5 == 0:
        background_tasks.add_task(run_evolution_background)

    return {"status": "ok"}

# -------------------- GENERATION --------------------
class GenerateRequest(BaseModel):
    topic: str
    pattern_id: Optional[str] = None
    model: Optional[str] = "openai"

@app.post("/api/generate")
async def generate(req: GenerateRequest):
    patterns = load_patterns()
    if req.pattern_id:
        pattern = next((p for p in patterns if p["id"] == req.pattern_id), None)
        if not pattern:
            pattern = max(patterns, key=lambda p: p["rating"])
    else:
        pattern = max(patterns, key=lambda p: p["rating"])
    prompt = pattern["prompt"].format(topic=req.topic)
    temperature = pattern["temperature"]
    response = call_ai(prompt, temperature, req.model)
    return {"response": response, "pattern_id": pattern["id"]}

# -------------------- EVOLUTION ENGINE --------------------
def mutate_pattern(pattern):
    import copy
    new = copy.deepcopy(pattern)
    new["id"] = f"{pattern['id']}_mut_{random.randint(1000,9999)}"
    words = pattern["prompt"].split()
    if random.random() < 0.5 and len(words) > 2:
        adjectives = ["concise", "detailed", "creative", "technical", "funny", "professional"]
        pos = random.randint(1, len(words)-1)
        words.insert(pos, random.choice(adjectives))
        new["prompt"] = " ".join(words)
    else:
        new["temperature"] = min(1.0, max(0.0, pattern["temperature"] + random.uniform(-0.2, 0.2)))
    new["rating"] = 0.5
    new["uses"] = 0
    return new

def evaluate_pattern(pattern, test_inputs=None):
    if not test_inputs:
        test_inputs = ["What is machine learning?", "Explain quantum computing simply", "How do I start coding?"]
    total = 0
    for query in test_inputs:
        prompt = pattern["prompt"].format(topic=query)
        response = call_ai(prompt, pattern["temperature"])
        judge_prompt = f"Rate the following response from 0 to 1 (1 = perfect, 0 = useless):\n\nResponse: {response}\n\nRating (just a number):"
        judge_resp = call_ai(judge_prompt, 0)
        try:
            score = float(judge_resp.strip())
        except:
            score = 0.5
        total += score
    return total / len(test_inputs)

@app.post("/api/evolve")
@app.get("/api/evolve")
async def run_evolution():
    await run_evolution_background()
    return {"status": "triggered"}

# -------------------- STATE & PHASES --------------------
STATE_FILE = "state.json"

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"current_phase": 0, "completed_phases": [], "logs": [], "bond_status": "HOLDS"}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

@app.get("/api/state")
def get_state():
    return load_state()

@app.post("/api/evolution")
def evolve_phase(action: dict):
    state = load_state()
    act = action.get("action")
    if act == "start":
        state["logs"].append({"timestamp": datetime.utcnow().isoformat(), "message": "Evolution started", "type": "info"})
        save_state(state)
        return {"status": "started"}
    elif act == "reset":
        state = {"current_phase": 0, "completed_phases": [], "logs": [], "bond_status": "HOLDS"}
        save_state(state)
        return {"status": "reset"}
    elif act == "step":
        if state["current_phase"] < 9:
            state["completed_phases"].append(state["current_phase"])
            state["current_phase"] += 1
            state["logs"].append({"timestamp": datetime.utcnow().isoformat(), "message": f"Phase {state['current_phase']} completed", "type": "info"})
            save_state(state)
        return {"status": "advanced", "phase": state["current_phase"]}
    return {"status": "unknown"}

# -------------------- SELF‑PLAY (CONTINUOUS) --------------------
SELF_PLAY_TOPICS = [
    "artificial intelligence", "climate change", "quantum computing",
    "space exploration", "renewable energy", "blockchain technology",
    "mental health awareness", "electric vehicles", "machine learning basics",
    "future of work", "genetic engineering", "cybersecurity",
    "sustainable agriculture", "virtual reality", "cryptocurrency",
    "constitutional AI", "self‑evolving systems", "ethical AI"
]

def rate_response_with_judge(response):
    judge_prompt = f"Rate the following response from 0 to 1 (1 = perfect, 0 = useless):\n\nResponse: {response}\n\nRating (just a number):"
    judge_resp = call_ai(judge_prompt, 0, "deepseek")
    try:
        rating = float(judge_resp.strip())
        return max(0.0, min(1.0, rating))
    except:
        return 0.5

async def continuous_self_play(interval_seconds=2):
    while True:
        try:
            patterns = load_patterns()
            if not patterns:
                await asyncio.sleep(interval_seconds)
                continue
            if random.random() < 0.2 and len(patterns) > 1:
                pattern = random.choice(patterns)
            else:
                pattern = max(patterns, key=lambda p: p["rating"])
            topic = random.choice(SELF_PLAY_TOPICS)
            prompt = pattern["prompt"].format(topic=topic)
            response = call_ai(prompt, pattern["temperature"], "deepseek")
            rating = rate_response_with_judge(response)

            patterns = load_patterns()
            for p in patterns:
                if p["id"] == pattern["id"]:
                    p["uses"] = p.get("uses", 0) + 1
                    old_uses = p["uses"] - 1
                    if old_uses > 0:
                        p["rating"] = (p["rating"] * old_uses + rating) / p["uses"]
                    else:
                        p["rating"] = rating
                    break
            save_patterns(patterns)

            total_uses = sum(p.get("uses", 0) for p in patterns)
            if total_uses > 0 and total_uses % 5 == 0:
                await run_evolution_background()

        except Exception as e:
            print(f"Self‑play error: {e}")
        await asyncio.sleep(interval_seconds)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(continuous_self_play(interval_seconds=2))

# -------------------- CHAT HISTORY --------------------
CONVERSATIONS_FILE = "conversations.json"

def load_conversations():
    try:
        with open(CONVERSATIONS_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return [{"id": "default", "name": "Chat 1", "messages": []}]

def save_conversations(conversations):
    with open(CONVERSATIONS_FILE, "w") as f:
        json.dump(conversations, f, indent=2)

class ConversationCreate(BaseModel):
    name: str

@app.post("/api/conversation/create")
async def create_conversation(data: ConversationCreate):
    convos = load_conversations()
    new_id = f"conv_{len(convos)+1}_{int(datetime.utcnow().timestamp())}"
    convos.append({"id": new_id, "name": data.name, "messages": []})
    save_conversations(convos)
    return {"id": new_id, "name": data.name}

@app.get("/api/conversations")
async def get_conversations():
    convos = load_conversations()
    return [{"id": c["id"], "name": c["name"]} for c in convos]

class ChatMessage(BaseModel):
    conversation_id: str
    role: str
    content: str
    timestamp: Optional[str] = None

@app.post("/api/chat/save")
async def save_chat_message(msg: ChatMessage):
    convos = load_conversations()
    for conv in convos:
        if conv["id"] == msg.conversation_id:
            if not msg.timestamp:
                msg.timestamp = datetime.utcnow().isoformat()
            conv["messages"].append(msg.dict())
            save_conversations(convos)
            return {"status": "saved"}
    raise HTTPException(404, "Conversation not found")

@app.get("/api/chat/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    convos = load_conversations()
    for conv in convos:
        if conv["id"] == conversation_id:
            return conv["messages"]
    raise HTTPException(404, "Conversation not found")

# -------------------- BUSINESS --------------------
BUSINESS_FILE = "businesses.json"

def load_businesses():
    try:
        with open(BUSINESS_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []

def save_businesses(businesses):
    with open(BUSINESS_FILE, "w") as f:
        json.dump(businesses, f, indent=2)

class BusinessCreate(BaseModel):
    name: str
    niche: str
    tone: str

@app.post("/api/business/create")
async def create_business(biz: BusinessCreate):
    businesses = load_businesses()
    new_biz = {
        "id": f"biz_{len(businesses)+1}_{int(datetime.utcnow().timestamp())}",
        "name": biz.name,
        "niche": biz.niche,
        "tone": biz.tone,
        "status": "active",
        "created_at": datetime.utcnow().isoformat()
    }
    businesses.append(new_biz)
    save_businesses(businesses)
    return {"status": "created", "business": new_biz}

@app.get("/api/business/list")
async def list_businesses():
    return load_businesses()

# -------------------- PREDICTIVE --------------------
PREDICTIONS_FILE = "predictions.json"

def load_predictions():
    try:
        with open(PREDICTIONS_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []

def save_predictions(preds):
    with open(PREDICTIONS_FILE, "w") as f:
        json.dump(preds, f, indent=2)

class PredictionRequest(BaseModel):
    topic: str
    participants: List[str]
    pre_reading: bool

def calculate_risk(req: PredictionRequest):
    risk = 0.2
    if not req.pre_reading:
        risk += 0.3
    if len(req.participants) > 5:
        risk += 0.2
    if any(word in req.topic.lower() for word in ["critical", "urgent", "sensitive"]):
        risk += 0.2
    return min(1.0, risk)

@app.post("/api/predict")
async def predict(req: PredictionRequest):
    risk = calculate_risk(req)
    pred_id = f"pred_{len(load_predictions())+1}_{int(datetime.utcnow().timestamp())}"
    pred = {
        "id": pred_id,
        "risk": risk,
        "input": req.dict(),
        "timestamp": datetime.utcnow().isoformat()
    }
    preds = load_predictions()
    preds.append(pred)
    save_predictions(preds)
    return {"risk": risk, "prediction_id": pred_id, "action": "generate briefing note" if risk > 0.7 else "monitor"}

@app.post("/api/predict/outcome")
async def record_outcome(data: dict):
    pred_id = data.get("prediction_id")
    outcome = data.get("outcome")  # "success" or "failure"
    preds = load_predictions()
    for p in preds:
        if p["id"] == pred_id:
            p["outcome"] = outcome
            save_predictions(preds)
            return {"status": "recorded"}
    raise HTTPException(404, "Prediction not found")

# -------------------- TELEMETRY --------------------
TELEMETRY_FILE = "telemetry.json"

def load_telemetry():
    try:
        with open(TELEMETRY_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"users": 0, "versions": {"v50.0": 68}, "actions": []}

def save_telemetry(tele):
    with open(TELEMETRY_FILE, "w") as f:
        json.dump(tele, f, indent=2)

@app.post("/api/telemetry/action")
async def track_action(data: dict):
    tele = load_telemetry()
    tele["actions"].append({
        "action": data.get("action"),
        "timestamp": datetime.utcnow().isoformat(),
        "user_agent": data.get("user_agent", "")
    })
    tele["users"] = len(set(a.get("user_agent") for a in tele["actions"]))
    save_telemetry(tele)
    return {"status": "recorded"}

@app.get("/api/telemetry/summary")
async def get_telemetry():
    return load_telemetry()

# -------------------- PRODUCTS --------------------
PRODUCTS_FILE = "products.json"

def load_products():
    try:
        with open(PRODUCTS_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []

def save_products(products):
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=2)

class ProductCreate(BaseModel):
    name: str
    type: str

@app.post("/api/product/create")
async def create_product(prod: ProductCreate):
    products = load_products()
    new_prod = {
        "id": f"prod_{len(products)+1}_{int(datetime.utcnow().timestamp())}",
        "name": prod.name,
        "type": prod.type,
        "status": "active",
        "created_at": datetime.utcnow().isoformat()
    }
    products.append(new_prod)
    save_products(products)
    return {"status": "created", "product": new_prod}

@app.get("/api/product/list")
async def list_products():
    return load_products()

# -------------------- SWARM --------------------
SHARED_METRICS = {"instances": [], "last_share": None}

@app.post("/api/swarm/share")
async def share_metrics(data: dict):
    SHARED_METRICS["instances"].append(data)
    SHARED_METRICS["last_share"] = datetime.utcnow().isoformat()
    return {"status": "shared"}

@app.get("/api/swarm/insights")
async def get_swarm():
    return SHARED_METRICS

# -------------------- INGEST --------------------
INGESTED_FILES = []

@app.post("/api/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8", errors="ignore")
    INGESTED_FILES.append({
        "filename": file.filename,
        "content": content[:500],
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"status": "ingested", "preview": content[:200]}

@app.get("/api/ingest/list")
async def list_ingested():
    return INGESTED_FILES[-20:]

# -------------------- ROBOT --------------------
ROBOT_STATES = {}

@app.post("/api/robot/command")
async def robot_command(data: dict):
    robot_id = data.get("robot_id")
    command = data.get("command")
    ROBOT_STATES[robot_id] = {"last_command": command, "timestamp": datetime.utcnow().isoformat()}
    return {"status": "executed", "simulated": True}

@app.get("/api/robot/status/{robot_id}")
async def robot_status(robot_id: str):
    return ROBOT_STATES.get(robot_id, {"status": "unknown"})

# -------------------- EARTH --------------------
EARTH_SITES = [
    {"name": "Hidden Temple", "lat": 13.4125, "lng": 122.5625},
    {"name": "Shipwreck Cove", "lat": 11.9971, "lng": 121.9220},
    {"name": "Crystal Cave", "lat": 14.6760, "lng": 121.0437}
]
NFT_MINTED = []

@app.post("/api/earth/query")
async def query_earth(data: dict):
    lat = data.get("lat")
    lng = data.get("lng")
    # return all sites for simplicity
    return {"sites": EARTH_SITES}

@app.post("/api/earth/mint_nft")
async def mint_nft(data: dict):
    site_name = data.get("site_name")
    if site_name in [s["name"] for s in EARTH_SITES]:
        nft_id = f"nft_{site_name.replace(' ', '_')}_{int(datetime.utcnow().timestamp())}"
        NFT_MINTED.append({"nft_id": nft_id, "site": site_name, "timestamp": datetime.utcnow().isoformat()})
        return {"status": "minted", "nft_id": nft_id}
    raise HTTPException(404, "Site not found")

# -------------------- DOCS --------------------
@app.get("/api/docs/report")
async def generate_report():
    patterns = load_patterns()
    state = load_state()
    convos = load_conversations()
    report = f"""# LROS System Report
Date: {datetime.utcnow().isoformat()}

## Evolution Progress
- Current Phase: {state['current_phase']}/9
- Bond Status: {state['bond_status']}

## Patterns
| ID | Prompt | Rating | Uses |
|----|--------|--------|------|
"""
    for p in patterns:
        report += f"| {p['id']} | {p['prompt'][:50]} | {p['rating']:.2f} | {p['uses']} |\n"
    report += "\n## Recent Logs\n"
    for log in state.get("logs", [])[-20:]:
        report += f"- {log['timestamp']}: {log['message']}\n"
    report += "\n## Conversations\n"
    for c in convos:
        report += f"- {c['name']}: {len(c['messages'])} messages\n"
    return {"report": report}

# -------------------- DEBUG --------------------
@app.get("/debug/patterns")
def debug_patterns():
    return load_patterns()

@app.get("/")
def root():
    return {"message": "LROS Constitutional AI Engine is alive", "bond": "HOLDS"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
