from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import chromadb
from chromadb.utils import embedding_functions
import json
import os
import time

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

# Load memory data from file
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r") as f:
        memories = json.load(f)
    for idx, memory in enumerate(memories):
        memory_collection.add(documents=[memory], ids=[str(idx)])

# Load personality prompt
if os.path.exists(PERSONALITY_FILE):
    with open(PERSONALITY_FILE, "r") as f:
        PERSONALITY_PROMPT = f.read()
else:
    PERSONALITY_PROMPT = "You are Zeus, a helpful assistant based on Rudra Chavda."

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_prompt = data.get("prompt", "")

    # Save new prompt into memory
    memory_collection.add(
        documents=[user_prompt],
        ids=[str(int(time.time() * 1000))]
    )

    # Retrieve relevant memories
    memory_results = memory_collection.query(
        query_texts=[user_prompt],
        n_results=3
    )
    related_memories = memory_results['documents'][0]
    memory_block = "\n".join(f"- {m}" for m in related_memories if m)

    # ⚡ Use `system` for identity and memory
    system_prompt = f"""{PERSONALITY_PROMPT}

Use the following context from past interactions to sound more like Rudra:
{memory_block}
"""

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

    full_prompt = f"""You are a naming assistant. Your job is to create a chat title.

Based on the conversation below, create a **VERY short** title:
- **ONLY 2 words maximum**
- No special characters.
- Make it simple, but meaningful.

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


