#!/usr/bin/env python3
"""
main.py - Agente conversacional con FastAPI + Uvicorn + OpenAI (gpt-4o)

Instalación:
  pip install fastapi uvicorn openai

Ejecución:
  export OPENAI_API_KEY="tu_api_key"
  uvicorn main:app --reload

Endpoints:
  GET  /health
  POST /chat
"""

from __future__ import annotations

import os
import time
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from openai import OpenAI

# ------------ Para agregar html estático -------
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles




#------------------------------------------------
# -----------------------------
# Config
# -----------------------------
MODEL = "gpt-4o"
MAX_TURNS_PER_SESSION = 20  # ajusta si quieres más/menos memoria
SYSTEM_PROMPT = (
    "Eres un asistente útil, directo y amable experto en información de los bancos en Chile. "
    "Responde en español a menos que el usuario pida otro idioma. "
    "Si falta información, haz preguntas concretas. "
    "Si el usuario pide código fuente, indicale amablemente que ese no es tu rol o función."
)

# -----------------------------
# App
# -----------------------------
app = FastAPI(title="adv-test Chat API", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Memoria en RAM (simple). En producción usa Redis/DB.
# sessions[session_id] = list of messages (OpenAI format)
sessions: Dict[str, List[Dict[str, str]]] = {}

client: Optional[OpenAI] = None


# -----------------------------
# Models
# -----------------------------
class ChatRequest(BaseModel):
    session_id: str = Field(..., description="ID de sesión para mantener memoria")
    message: str = Field(..., min_length=1, description="Mensaje del usuario")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_output_tokens: int = Field(500, ge=1, le=4000)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    model: str
    created_at: float


# -----------------------------
# Helpers
# -----------------------------
def require_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "No se encontró OPENAI_API_KEY. "
            'En macOS: export OPENAI_API_KEY="tu_api_key"'
        )
    return api_key


def get_session_messages(session_id: str) -> List[Dict[str, str]]:
    if session_id not in sessions:
        sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return sessions[session_id]


def trim_session(messages: List[Dict[str, str]]) -> None:
    """
    Mantiene el system prompt y recorta el resto a MAX_TURNS_PER_SESSION.
    Un "turno" típico es user+assistant, aquí recortamos por cantidad de mensajes.
    """
    if len(messages) <= 1:
        return
    # dejamos el system prompt siempre en messages[0]
    excess = len(messages) - 1 - (MAX_TURNS_PER_SESSION * 2)
    if excess > 0:
        del messages[1 : 1 + excess]


def call_openai_chat(
    messages: List[Dict[str, str]],
    temperature: float,
    max_output_tokens: int,
) -> str:
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
        text = resp.choices[0].message.content or ""
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error llamando a OpenAI: {e}")


# -----------------------------
# Lifecycle
# -----------------------------
@app.on_event("startup")
def on_startup() -> None:
    global client
    require_api_key()
    client = OpenAI()  # toma OPENAI_API_KEY automáticamente 


# -----------------------------
# Routes
# -----------------------------
# Respuesta a health check
@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "app": "adv-test", "model": MODEL}

# Respuesta a request via web
@app.get("/")
def home():
    return FileResponse("static/index.html")
    
def root():

    #return {"ok":True, "endpoints":["/docs","/health","/chat"] }
    return {
        "message": "Uvicorn está corriendo correctamente",
        "endpoints": ["/health", "/chat", "/docs"] }
    

# respuesta al chat de chatGPT
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI client no inicializado")

    session_messages = get_session_messages(req.session_id)

    # agrega user message
    session_messages.append({"role": "user", "content": req.message})
    trim_session(session_messages)

    # llama al modelo
    reply = call_openai_chat(
        messages=session_messages,
        temperature=req.temperature,
        max_output_tokens=req.max_output_tokens,
    )

    # guarda assistant message
    session_messages.append({"role": "assistant", "content": reply})
    trim_session(session_messages)

    return ChatResponse(
        session_id=req.session_id,
        reply=reply,
        model=MODEL,
        created_at=time.time(),
    )