from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import chromadb
import json
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434/api/generate"
PERSONALITY_FILE = "personality_prompt.txt"
MEMORY_FILE = "memory_data.json"

# Setup ChromaDB
client = chromadb.Client()
memory_collection = client.create_collection(name="rudra_memory")

# Load memory data
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r") as f:
        memories = json.load(f)
    for idx, memory in enumerate(memories):
        memory_collection.add(documents=[memory], ids=[str(idx)])

# Load personality
if os.path.exists(PERSONALITY_FILE):
    with open(PERSONALITY_FILE, "r") as f:
        PERSONALITY_PROMPT = f.read()
else:
    PERSONALITY_PROMPT = "You are Zeus, a helpful assistant based on Rudra Chavda."

# ✅ New World Time Fetching
def get_world_time(timezone="America/Los_Angeles"):
    try:
        res = requests.get(f"https://timeapi.io/api/TimeZone/zone?timeZone={timezone}")
        if res.status_code == 200:
            data = res.json()
            date = data.get('date')      # '2025-04-26'
            time_only = data.get('time')  # '21:38'
            return date, time_only
        else:
            print(f"TimeAPI error: {res.status_code}")
            return None, None
    except Exception as e:
        print(f"TimeAPI exception: {e}")
        return None, None

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_prompt = data.get("prompt", "").lower()

    # Add prompt to memory
    memory_collection.add(
        documents=[user_prompt],
        ids=[str(int(time.time() * 1000))]
    )

    # Search related memories
    memory_results = memory_collection.query(
        query_texts=[user_prompt],
        n_results=3
    )
    related_memories = memory_results['documents'][0]
    memory_block = "\n".join(f"- {m}" for m in related_memories if m)

    # 🧠 Smart system prompt
    system_prompt = f"""{PERSONALITY_PROMPT}

Use the following context from past interactions:
{memory_block}
"""

    # ⚡ Check if the prompt requires TIME or DATE manually
    if "time" in user_prompt or "date" in user_prompt or "day" in user_prompt:
        date, time_only = get_world_time("America/Los_Angeles")
        if date and time_only:
            return {
                "response": f"📅 Date: {date}\n🕒 Time: {time_only}"
            }
        else:
            return {
                "response": "❌ Sorry, I couldn't fetch the real-time information."
            }

    # Otherwise normal LLM generation
    payload = {
        "model": "gemma3:12b",
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        return response.json()
    except Exception as e:
        return {"response": f"Error communicating with Ollama: {str(e)}"}

@app.post("/title")
async def title(request: Request):
    data = await request.json()
    conversation = data.get("conversation", "")

    full_prompt = f"""You are a chat assistant naming bot.
Summarize the following conversation in a very short 1-2 word title. No special characters.

Conversation:
{conversation}

Title:"""

    payload = {
        "model": "gemma3:12b",
        "prompt": full_prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        return response.json()
    except Exception as e:
        return {"response": f"Error generating title: {str(e)}"}
