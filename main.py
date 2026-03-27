from fastapi import FastAPI, HTTPException
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

app = FastAPI(title="LROS Multi‑AI Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# API keys from environment
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Correct Gemini configuration
if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY")) if os.environ.get("ANTHROPIC_API_KEY") else None
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
cohere_client = cohere.Client(api_key=os.environ.get("COHERE_API_KEY")) if os.environ.get("COHERE_API_KEY") else None
WRITER_API_KEY = os.environ.get("WRITER_API_KEY")

PATTERN_FILE = "patterns.json"
def load_patterns():
    if os.path.exists(PATTERN_FILE):
        with open(PATTERN_FILE) as f:
            return json.load(f)
    return [
        {"id": "p1", "prompt": "Explain {topic} in simple terms.", "temperature": 0.7, "rating": 0.5, "uses": 0},
        {"id": "p2", "prompt": "Write a detailed technical article about {topic}.", "temperature": 0.5, "rating": 0.5, "uses": 0},
        {"id": "p3", "prompt": "Give a creative story about {topic}.", "temperature": 0.9, "rating": 0.5, "uses": 0},
    ]
def save_patterns(patterns):
    with open(PATTERN_FILE, "w") as f:
        json.dump(patterns, f, indent=2)

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

    # Fallback simulation
    return f"[Simulated] LROS would answer: {prompt[:100]}..."

# (The rest of the endpoints – feedback, orchestrated, state, evolution, etc. – remain unchanged)
# Be sure to include them as in the previous code. For brevity, I'm not repeating them here,
# but they must be present. Use the full code from the previous message.

# ...
