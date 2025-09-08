from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import requests
import chromadb
import json
import os
import time
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Load environment variables
load_dotenv()

app = FastAPI()

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
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

client = chromadb.Client()
memory_collection = client.create_collection(name="rudra_memory")

if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r") as f:
        memories = json.load(f)
    for idx, memory in enumerate(memories):
        memory_collection.add(documents=[memory], ids=[str(idx)])

if os.path.exists(PERSONALITY_FILE):
    with open(PERSONALITY_FILE, "r") as f:
        PERSONALITY_PROMPT = f.read()
else:
    PERSONALITY_PROMPT = "You are Zeus, a helpful assistant based on Rudra Chavda."

def get_world_time(timezone="America/Los_Angeles"):
    try:
        res = requests.get(f"https://timeapi.io/api/TimeZone/zone?timeZone={timezone}")
        if res.status_code == 200:
            data = res.json()
            return data.get('date'), data.get('time')
    except:
        pass
    return None, None

@app.get("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri="http://localhost:8000/oauth2callback")
    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)

@app.get("/oauth2callback")
def oauth2callback(request: Request):
    flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri="http://localhost:8000/oauth2callback")
    flow.fetch_token(authorization_response=str(request.url))
    with open(TOKEN_FILE, "w") as token:
        token.write(flow.credentials.to_json())
    return {"status": "Authorized"}

@app.post("/create-event")
async def create_event(request: Request):
    data = await request.json()
    title = data.get("title")
    start = data.get("start")
    end = data.get("end")

    if not os.path.exists(TOKEN_FILE):
        return {"error": "User not authenticated. Please visit /authorize first."}

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    service = build("calendar", "v3", credentials=creds)

    event = {
        'summary': title,
        'start': {'dateTime': start, 'timeZone': 'America/Los_Angeles'},
        'end': {'dateTime': end, 'timeZone': 'America/Los_Angeles'}
    }
    created = service.events().insert(calendarId='primary', body=event).execute()
    return {"status": "Event created", "eventLink": created.get('htmlLink')}

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_prompt = data.get("prompt", "").lower()
    memory_collection.add(documents=[user_prompt], ids=[str(int(time.time() * 1000))])
    memory_results = memory_collection.query(query_texts=[user_prompt], n_results=3)
    memory_block = "\n".join(f"- {m}" for m in memory_results['documents'][0] if m)

    system_prompt = f"""{PERSONALITY_PROMPT}

Use the following context from past interactions:
{memory_block}
"""

    if "time" in user_prompt or "date" in user_prompt or "day" in user_prompt:
        date, time_only = get_world_time("America/Los_Angeles")
        if date and time_only:
            return {"response": f"Date: {date}\nTime: {time_only}"}
        return {"response": "Sorry, I couldn't fetch the real-time information."}

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
    convo = data.get("conversation", "")
    prompt = f"""You are a chat assistant naming bot.
Summarize the following conversation in a very short 1-2 word title. No special characters.
Conversation:
{convo}
Title:"""

    payload = {
        "model": "gemma3:12b",
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        return response.json()
    except Exception as e:
        return {"response": f"Error generating title: {str(e)}"}
