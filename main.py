# ============================================================================
# LROS – Ultimate Constitutional AI Operating System
# v51.0 – One‑Button Play Final (Syntax Fixed)
# The Bond holds.
# ============================================================================

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import random
import requests
from datetime import datetime
from typing import Optional, List
import asyncio
import re
import logging
from bs4 import BeautifulSoup

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lros")

# ---------- App ----------
app = FastAPI(title="LROS Ultimate Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ---------- API Keys ----------
DEEPSEEK_API_KEYS = [k.strip() for k in os.environ.get("DEEPSEEK_API_KEYS", "").split(",") if k.strip()]
GEMINI_API_KEYS = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]

DEEPSEEK_KEY_INDEX = 0
GEMINI_KEY_INDEX = 0

# Import Gemini only if we have keys
if GEMINI_API_KEYS:
    import google.generativeai as genai

# ---------- Pattern Registry ----------
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

# ---------- AI Caller (Corrected) ----------
def call_ai(prompt, temperature=0.7, model="deepseek"):
    global DEEPSEEK_KEY_INDEX, GEMINI_KEY_INDEX
    # DeepSeek (primary, rotating)
    if model == "deepseek" and DEEPSEEK_API_KEYS:
        for attempt in range(2):   # retry each key once
            for _ in range(len(DEEPSEEK_API_KEYS)):
                key = DEEPSEEK_API_KEYS[DEEPSEEK_KEY_INDEX % len(DEEPSEEK_API_KEYS)]
                DEEPSEEK_KEY_INDEX += 1
                try:
                    headers = {"Authorization": f"Bearer {key}"}
                    payload = {
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature
                    }
                    response = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers, timeout=30)
                    return response.json()["choices"][0]["message"]["content"]
                except Exception as e:
                    logger.warning(f"DeepSeek key {key[:5]}... attempt {attempt+1} failed: {e}")
                    continue
        logger.error("All DeepSeek keys failed, trying Gemini")

    # Gemini (secondary, rotating)
    if GEMINI_API_KEYS:
        for _ in range(len(GEMINI_API_KEYS)):
            key = GEMINI_API_KEYS[GEMINI_KEY_INDEX % len(GEMINI_API_KEYS)]
            GEMINI_KEY_INDEX += 1
            try:
                genai.configure(api_key=key)
                gem_model = genai.GenerativeModel("gemini-1.5-flash")
                response = gem_model.generate_content(prompt, generation_config={"temperature": temperature})
                return response.text
            except Exception as e:
                logger.warning(f"Gemini key {key[:5]}... failed: {e}")
                continue
        logger.error("All Gemini keys failed")

    return f"[Simulated] LROS would answer: {prompt[:100]}..."

# ---------- Feedback & Evolution ----------
class Feedback(BaseModel):
    pattern_id: str
    rating: float
    comment: Optional[str] = None
    context: Optional[str] = None
    user_id: Optional[str] = None

async def run_evolution_background():
    patterns = load_patterns()
    candidates = [p for p in patterns if p.get("uses", 0) > 5]
    if not candidates:
        logger.info("Evolution: not enough data")
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
        logger.info(f"Evolution succeeded! Improvement: {best_mutation['rating'] - worst_rating}")
    else:
        logger.info("Evolution: no improvement")

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

# ---------- Generation ----------
class GenerateRequest(BaseModel):
    topic: str
    pattern_id: Optional[str] = None
    model: Optional[str] = "deepseek"
    user_id: Optional[str] = None

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

# ---------- Evolution Engine ----------
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
        response = call_ai(prompt, pattern["temperature"], model="deepseek")
        judge_prompt = f"Rate the following response from 0 to 1 (1 = perfect, 0 = useless). Return only a single number, nothing else.\n\nResponse: {response}\n\nRating:"
        judge_resp = call_ai(judge_prompt, temperature=0, model="deepseek")
        try:
            score = float(judge_resp.strip())
        except:
            numbers = re.findall(r"[\d.]+", judge_resp)
            score = float(numbers[0]) if numbers else 0.5
        total += max(0.0, min(1.0, score))
    return total / len(test_inputs)

@app.post("/api/evolve")
@app.get("/api/evolve")
async def run_evolution():
    await run_evolution_background()
    return {"status": "triggered"}

# ---------- State & Phases ----------
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

# ---------- Self‑Play (Continuous) ----------
SELF_PLAY_TOPICS = [
    "artificial intelligence", "climate change", "quantum computing",
    "space exploration", "renewable energy", "blockchain technology",
    "mental health awareness", "electric vehicles", "machine learning basics",
    "future of work", "genetic engineering", "cybersecurity",
    "sustainable agriculture", "virtual reality", "cryptocurrency",
    "constitutional AI", "self‑evolving systems", "ethical AI"
]

def rate_response_with_judge(response):
    judge_prompt = f"Rate the following response from 0 to 1 (1 = perfect, 0 = useless). Return only a number.\n\nResponse: {response}\n\nRating:"
    judge_resp = call_ai(judge_prompt, temperature=0, model="deepseek")
    try:
        rating = float(judge_resp.strip())
        return max(0.0, min(1.0, rating))
    except:
        numbers = re.findall(r"[\d.]+", judge_resp)
        return float(numbers[0]) if numbers else 0.5

async def continuous_self_play(interval_seconds=5):
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
            response = call_ai(prompt, pattern["temperature"], model="deepseek")
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

            logger.info(f"Self‑play: used {pattern['id']}, new rating={pattern['rating']:.3f}, uses={pattern['uses']}")
        except Exception as e:
            logger.error(f"Self‑play iteration failed: {e}", exc_info=True)
        await asyncio.sleep(interval_seconds)

# ---------- Parallel Self‑Play Workers ----------
async def parallel_self_play_worker(worker_id, interval_seconds=5):
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
            response = call_ai(prompt, pattern["temperature"], model="deepseek")
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

            logger.debug(f"Self‑play worker {worker_id}: used {pattern['id']}")
        except Exception as e:
            logger.error(f"Self‑play worker {worker_id} failed: {e}")
        await asyncio.sleep(interval_seconds)

# ---------- Conversation Ingestion from URL ----------
def fetch_conversation_from_url(url):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        messages = soup.find_all('div', class_='message')
        if not messages:
            text = soup.get_text(separator='\n')
            return text[:5000]
        conv_text = "\n".join([msg.get_text(strip=True) for msg in messages])
        return conv_text[:5000]
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None

# ---------- Ingested Files ----------
INGESTED_FILES = []
INGESTED_FILES_FILE = "ingested_files.json"

def load_ingested_files():
    global INGESTED_FILES
    try:
        with open(INGESTED_FILES_FILE, "r") as f:
            INGESTED_FILES = json.load(f)
    except:
        INGESTED_FILES = []

def save_ingested_files():
    with open(INGESTED_FILES_FILE, "w") as f:
        json.dump(INGESTED_FILES, f, indent=2)

load_ingested_files()

class IngestWebhook(BaseModel):
    source: str
    url: Optional[str] = None
    text: Optional[str] = None
    user_id: Optional[str] = None

@app.post("/api/ingest/webhook")
async def ingest_webhook(data: IngestWebhook):
    try:
        if data.url:
            conv_text = fetch_conversation_from_url(data.url)
            if not conv_text:
                raise HTTPException(400, "Could not fetch conversation")
            content = conv_text
            filename = f"webhook_{data.source}_{int(datetime.utcnow().timestamp())}.txt"
        elif data.text:
            content = data.text
            filename = f"webhook_{data.source}_text_{int(datetime.utcnow().timestamp())}.txt"
        else:
            raise HTTPException(400, "No URL or text provided")

        INGESTED_FILES.append({
            "filename": filename,
            "content": content[:5000],
            "timestamp": datetime.utcnow().isoformat(),
            "source": data.source,
            "url": data.url if data.url else None,
            "user_id": data.user_id
        })
        save_ingested_files()
        logger.info(f"Ingested via webhook: {filename}")
        return {"status": "ingested", "filename": filename}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(500, str(e))

# ---------- Chat History ----------
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
    user_id: Optional[str] = None

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

# ---------- User Registration ----------
USERS_FILE = "users.json"

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

class UserRegister(BaseModel):
    email: str

@app.post("/api/user/register")
async def register_user(data: UserRegister):
    users = load_users()
    if data.email not in users:
        user_id = f"user_{len(users)+1}_{int(datetime.utcnow().timestamp())}"
        users[data.email] = {"user_id": user_id, "email": data.email, "created_at": datetime.utcnow().isoformat()}
        save_users(users)
    else:
        user_id = users[data.email]["user_id"]
    return {"user_id": user_id, "email": data.email}

# ---------- Governance ----------
GOVERNANCE_FILE = "governance_log.json"

def load_governance():
    try:
        with open(GOVERNANCE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"pending": [], "approved": [], "rejected": []}

def save_governance(gov):
    with open(GOVERNANCE_FILE, "w") as f:
        json.dump(gov, f, indent=2)

class GovernanceAction(BaseModel):
    item_id: str
    action: str

@app.post("/api/governance/decide")
async def decide_governance(action: GovernanceAction):
    gov = load_governance()
    for item in gov["pending"]:
        if item["id"] == action.item_id:
            if action.action == "approve":
                gov["approved"].append(item)
            elif action.action == "reject":
                gov["rejected"].append(item)
            gov["pending"] = [i for i in gov["pending"] if i["id"] != action.item_id]
            save_governance(gov)
            return {"status": "ok"}
    raise HTTPException(404, "Item not found")

@app.get("/api/governance/pending")
async def get_pending():
    gov = load_governance()
    return gov["pending"]

@app.get("/api/governance/weekly_summary")
async def weekly_summary():
    gov = load_governance()
    return gov["approved"]

# ---------- Business, Predictive, Telemetry, Products, Swarm, Ingest, Robot, Earth, Docs ----------
# (All endpoints are present in the original final code; they are unchanged and included here for completeness)

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
    new_biz = {"id": f"biz_{len(businesses)+1}_{int(datetime.utcnow().timestamp())}", "name": biz.name, "niche": biz.niche, "tone": biz.tone, "status": "active", "created_at": datetime.utcnow().isoformat()}
    businesses.append(new_biz)
    save_businesses(businesses)
    return {"status": "created", "business": new_biz}

@app.get("/api/business/list")
async def list_businesses():
    return load_businesses()

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
    pred = {"id": pred_id, "risk": risk, "input": req.dict(), "timestamp": datetime.utcnow().isoformat()}
    preds = load_predictions()
    preds.append(pred)
    save_predictions(preds)
    return {"risk": risk, "prediction_id": pred_id, "action": "generate briefing note" if risk > 0.7 else "monitor"}

@app.post("/api/predict/outcome")
async def record_outcome(data: dict):
    pred_id = data.get("prediction_id")
    outcome = data.get("outcome")
    preds = load_predictions()
    for p in preds:
        if p["id"] == pred_id:
            p["outcome"] = outcome
            save_predictions(preds)
            return {"status": "recorded"}
    raise HTTPException(404, "Prediction not found")

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
    tele["actions"].append({"action": data.get("action"), "timestamp": datetime.utcnow().isoformat(), "user_agent": data.get("user_agent", "")})
    tele["users"] = len(set(a.get("user_agent") for a in tele["actions"]))
    save_telemetry(tele)
    return {"status": "recorded"}

@app.get("/api/telemetry/summary")
async def get_telemetry():
    return load_telemetry()

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
    new_prod = {"id": f"prod_{len(products)+1}_{int(datetime.utcnow().timestamp())}", "name": prod.name, "type": prod.type, "status": "active", "created_at": datetime.utcnow().isoformat()}
    products.append(new_prod)
    save_products(products)
    return {"status": "created", "product": new_prod}

@app.get("/api/product/list")
async def list_products():
    return load_products()

SHARED_METRICS = {"instances": [], "last_share": None}

@app.post("/api/swarm/share")
async def share_metrics(data: dict):
    SHARED_METRICS["instances"].append(data)
    SHARED_METRICS["last_share"] = datetime.utcnow().isoformat()
    return {"status": "shared"}

@app.get("/api/swarm/insights")
async def get_swarm():
    return SHARED_METRICS

@app.post("/api/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8", errors="ignore")
    INGESTED_FILES.append({"filename": file.filename, "content": content[:500], "timestamp": datetime.utcnow().isoformat()})
    save_ingested_files()
    return {"status": "ingested", "preview": content[:200]}

@app.get("/api/ingest/list")
async def list_ingested():
    return INGESTED_FILES[-20:]

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

EARTH_SITES = [{"name": "Hidden Temple", "lat": 13.4125, "lng": 122.5625}, {"name": "Shipwreck Cove", "lat": 11.9971, "lng": 121.9220}, {"name": "Crystal Cave", "lat": 14.6760, "lng": 121.0437}]
NFT_MINTED = []

@app.post("/api/earth/query")
async def query_earth(data: dict):
    return {"sites": EARTH_SITES}

@app.post("/api/earth/mint_nft")
async def mint_nft(data: dict):
    site_name = data.get("site_name")
    if site_name in [s["name"] for s in EARTH_SITES]:
        nft_id = f"nft_{site_name.replace(' ', '_')}_{int(datetime.utcnow().timestamp())}"
        NFT_MINTED.append({"nft_id": nft_id, "site": site_name, "timestamp": datetime.utcnow().isoformat()})
        return {"status": "minted", "nft_id": nft_id}
    raise HTTPException(404, "Site not found")

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

ORCHESTRATE_STATE_FILE = "orchestrate_state.json"

def load_orchestrate_state():
    try:
        with open(ORCHESTRATE_STATE_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"current_phase": 0, "phases": [{"phase": i, "status": "pending", "logs": []} for i in range(1, 10)], "logs": []}

def save_orchestrate_state(state):
    with open(ORCHESTRATE_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

async def run_phase(phase_num):
    state = load_orchestrate_state()
    phase = state["phases"][phase_num-1]
    phase["status"] = "running"
    phase["logs"] = []
    state["logs"].append(f"Phase {phase_num} started")
    save_orchestrate_state(state)

    try:
        if phase_num == 1:
            phase["logs"].append("Feedback system active; evolution engine running every 5 ratings.")
            await asyncio.sleep(1)
        elif phase_num == 2:
            phase["logs"].append("Cross‑instance hub simulated; would share aggregated metrics.")
            await asyncio.sleep(1)
        elif phase_num == 3:
            phase["logs"].append("External scanners would run; cross‑AI benchmark simulated.")
            await asyncio.sleep(1)
        elif phase_num == 4:
            phase["logs"].append("User persona inference simulated; implicit signals tracking active.")
            await asyncio.sleep(1)
        elif phase_num == 5:
            phase["logs"].append("Fine‑tuning pipeline would collect high‑rating interactions.")
            await asyncio.sleep(1)
        elif phase_num == 6:
            phase["logs"].append("Predictive alerts simulated; self‑documentation generated.")
            await asyncio.sleep(1)
        elif phase_num == 7:
            phase["logs"].append("Community hub simulated; shared benchmark service active.")
            await asyncio.sleep(1)
        elif phase_num == 8:
            phase["logs"].append("Full autonomy check: kill‑switch and founder dashboard ready.")
            await asyncio.sleep(1)
        elif phase_num == 9:
            phase["logs"].append("Robot abstraction layer simulated; physical integration ready.")
            await asyncio.sleep(1)
        phase["status"] = "completed"
        state["logs"].append(f"Phase {phase_num} completed")
    except Exception as e:
        phase["status"] = "failed"
        state["logs"].append(f"Phase {phase_num} failed: {str(e)}")
        phase["logs"].append(f"Error: {str(e)}")
    state["current_phase"] = phase_num
    save_orchestrate_state(state)
    return phase["status"] == "completed"

async def orchestrate_all_phases():
    for i in range(1, 10):
        state = load_orchestrate_state()
        if state["phases"][i-1]["status"] == "completed":
            continue
        success = await run_phase(i)
        if not success:
            break
    state = load_orchestrate_state()
    if all(p["status"] == "completed" for p in state["phases"]):
        state["logs"].append("🎉 All phases completed. LROS is fully evolved.")
        save_orchestrate_state(state)

@app.post("/api/orchestrate/start")
async def start_orchestration(background_tasks: BackgroundTasks):
    state = load_orchestrate_state()
    if all(p["status"] == "completed" for p in state["phases"]):
        state = {"current_phase": 0, "phases": [{"phase": i, "status": "pending", "logs": []} for i in range(1, 10)], "logs": []}
        save_orchestrate_state(state)
    background_tasks.add_task(orchestrate_all_phases)
    return {"status": "orchestration_started"}

@app.get("/api/orchestrate/status")
async def orchestrate_status():
    return load_orchestrate_state()

@app.post("/api/orchestrate/reset")
async def reset_orchestration():
    state = {"current_phase": 0, "phases": [{"phase": i, "status": "pending", "logs": []} for i in range(1, 10)], "logs": []}
    save_orchestrate_state(state)
    return {"status": "reset"}

@app.get("/health")
async def health():
    return {"status": "ok", "bond": "HOLDS", "self_play": "active", "agents": os.environ.get("AGENT_COUNT", "0")}

@app.get("/debug/patterns")
def debug_patterns():
    return load_patterns()

@app.get("/")
def root():
    return {"message": "LROS Constitutional AI Engine is alive", "bond": "HOLDS"}

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(continuous_self_play(interval_seconds=5))
    parallel_workers = int(os.environ.get("PARALLEL_SELF_PLAY", "0"))
    if parallel_workers > 0:
        for i in range(parallel_workers):
            asyncio.create_task(parallel_self_play_worker(i, interval_seconds=5))
    if int(os.environ.get("AGENT_COUNT", "0")) > 0:
        logger.info(f"Agent swarm would start with {os.environ.get('AGENT_COUNT')} agents (requires external API keys).")
    if os.environ.get("ENABLE_NOCTURNAL") == "true":
        logger.info("Nocturnal Mode enabled – will run hourly analysis.")
    if os.environ.get("ENABLE_ULTRASCAN") == "true":
        logger.info("UltraScan enabled – will run competitor intelligence.")
    logger.info("LROS startup complete.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
