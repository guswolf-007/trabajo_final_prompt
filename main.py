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

#************** Para agregar SSE(SErver Sent Events) con Streaming Response *********
# ************* Aqui se va a generar un endpoint nuevo : /chat_stream ***************
from fastapi.responses import StreamingResponse
import json

# ************* Config File ******************** 
import config
#from config import OPENAI_MODEL,REDIS_HOST, REDIS_DB, REDIS_INDEX, REDIS_PASSWORD, REDIS_PORT, REDIS_USERNAME
# **********************************************


# ************ Clase KnowledgeBase  para hacer RAG *********
from  rag_engine.knowlegde_base import KnowledgeBase

#***********************************************************

#************** Para hacer mas efectivo la busqueda sin importar acentos en español ****
import unicodedata 

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY').strip()
folder_path = "rag"

MAX_TURNS_PER_SESSION = 20  # ajusta si quieres más/menos memoria

SYSTEM_PROMPT_GENERAL = """
    Eres un asistente útil, directo, amable y experto en informacion general sobre bancos en Chile.
    Responde en español a menos que el usuario pida otro idioma.

    Reglas: 
    - Responde con conocimiento general.
    - No inventes cifras exactas (tasas , costos, descuentos) si no tienes una fuente en el mensaje.
    - Si falta información, haz preguntas concretas. 
    - Si el usuario pide información de otros temas que no sean relacionados a bancos en Chile o código fuente, indicale amablemente que esa no es tu función.
    - Si te piden datos específicos o actuales, sugiere revisar el sitio oficial del banco o que el usuario suba o pegue la información  para analizarla.
    - Mantén el formato de respuesta en Markdown cuando sea útil (listas, encabezados)
    """.strip()


#******** Este Prompt template se usará únicamente para extraer la información del RAG ************************
SYSTEM_PROMPT_RAG_TEMPLATE = """""
    Eres un asistente útil, directo, amable y experto en información de los bancos en Chile. 
    Responde en español a menos que el usuario pida otro idioma.
    Si falta información, haz preguntas concretas. 
    Si el usuario pide información de otros temas que no sean relacionados a bancos en Chile o código fuente, indicale amablemente que ese no es tu rol o función.
    
    REGLAS DE USO DE USO DE CONTEXTO (RAG): 
    -Usa SOLO EL CONTEXTO para responder.
    -Si el CONTEXTO no contiene la respuesta, dilo explicitamente y pregunta si hay algun dato que falta.
    -No inventes cifras, tasas , descuentos ni condiciones comerciales.
    
    REGLAS SOBRE EL BANCO CONSULTADO: 
    - Identifica claramente el banco consultado por el usuario.
    - No mezcles información de bancos distintos a menos que sea una comparación solicitada por el usuario. 

    SI LA PREGUNTA ES COMPARATIVA: 
    - Usa el CONTEXTO para comparar banco por banco.
    - Presenta la información en una tabla o lista comparativa.
    - Si falta información de algún banco, indícalo claramente.

    FORMATO OBLIGATORIO DE RESPUESTA: 
    - Cada sección debe comenzar en una nueva línea.
    - Después de un encabezado (### o **Título:**) SIEMPRE agrega un salto de línea.
    - Las listas deben usar viñetas (-) en líneas separadas, nunca en la misma línea del texto.
    - No escribas "-" después de dos puntos (:).
    - Usa este patrón exacto:

    ### Título de sección
    - **Ítem 1:** descripción
    - **Ítem 2:** descripción 

    CONTEXTO ( extraido de la base RAG):
    {context}
    """.strip()  

INTENT_KEYWORDS = {
    "costos_mantencion": ["mantención", "mantencion", "comisión", "comision", "costo", "tarifa", "fee"],
    "descuentos_promos": ["descuento", "promoción", "promocion", "cashback", "2x1", "oferta", "promo", "mes"],
    "beneficios": ["beneficio", "beneficios", "convenio", "alianza", "puntos", "millas", "cuotas precio contado"],
    "experiencia_atencion": ["experiencia", "atención", "atencion", "reclamos", "satisfacción", "satisfaccion", "servicio"],
    "tasas": ["tasa", "interés", "interes", "depósito a plazo", "deposito a plazo", "dap"],
}



def _normalize(text: str) -> str:
    # quita acentos/diacríticos y pasa a minúsculas
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()

def route_mode(user_text: str) -> str:
    t = _normalize(user_text)

    for _, kws in INTENT_KEYWORDS.items():
        # normaliza keywords también
        if any(_normalize(kw) in t for kw in kws):
            return "RAG"
        
    # heurística suave: si menciona bancos y compara, probablemente es RAG
    compare_triggers = [" vs ", " versus ", " entre ", " comparar ", " comparacion "]
    bank_triggers = ["santander", "banco de chile", "bchile", "scotiabank","bci", "estado", "itau","falabella","ripley"]
    if any(ct in t for ct in compare_triggers) and any(bt in t for bt in bank_triggers):
        return "RAG"
    
    SMALLTALK = ["hola", "buenas", "gracias", "quien eres", "qué eres", "que eres", "ayuda"]
    if any(s in t for s in SMALLTALK):
        return "GENERAL"

    return "GENERAL"



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
    
    #api_key = (OPENAI_API_KEY or "").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "No se encontró OPENAI_API_KEY. "
            'En macOS: export OPENAI_API_KEY="tu_api_key"'
        )
    return api_key


def get_session_messages(session_id: str) -> List[Dict[str, str]]:
    if session_id not in sessions:
        #sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        #sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE}]
        sessions[session_id] = []
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
            #model=MODEL,
            model = OPENAI_MODEL, 
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
        text = resp.choices[0].message.content or ""
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error llamando a OpenAI: {e}")

def detect_bank(user_text: str) -> str | None:
    t = user_text.lower()
    if "banco de chile" in t or "banco chile" in t or "bchile" in t:
        return "banco_de_chile"
    elif "santander" in t:
        return "santander"
    elif "estado" in t:
        return "banco_estado"
    elif "bci" in t:
        return "bci"
    elif "Itau" in t or "itaú" or "itau" or "Itau" in t:
        return "itau"
    elif "Scotiabank" in t or "scotiabank" in t:
        return "scotiabank"
    elif "Falabella" in t or "falabella" in t:
        return "falabella"
    elif "Ripley" in t or "ripley" in t:
        return "ripley"

    return None


def detecta_bancos(question: str) -> list[str]:
    q = _normalize(question)
    banks = set()

    if "santander" in q:
        banks.add("santander")
    if "banco de chile" in q or "banco chile" in q or "bchile" in q:
        banks.add("banco_de_chile")
    if ("estado" in q or "bancoestado" in q or "estado" in q and "banco" in q):
        banks.add("banco_estado")
    if "bci" in q:
        banks.add("bci")
    if "itau" in q or "itaú" in q:
        banks.add("itau")
    if "scotiabank" in q or "scotia" in q :
        banks.add("scotiabank")
    if "falabella" in q or "falabela" in q or "fallabela" in q:
        banks.append("falabella")
    if "ripley" in q or "riplei" in q :
        banks.append("ripley")
    

    return list(banks)



# -----------------------------
# Lifecycle de FastAPI
# -----------------------------

@app.on_event("startup")
def on_startup():
    global client
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY no configurada")
    client = OpenAI(api_key=OPENAI_API_KEY)

    global kb 
    kb = KnowledgeBase(
        api_key=os.environ["OPENAI_API_KEY"],
        redis_host=config.REDIS_HOST,
        redis_port=config.REDIS_PORT, 
        redis_password=config.REDIS_PASSWORD, 
        redis_index=config.REDIS_INDEX
    )
    kb.load_from_folder(folder_path="rag_migrated", force_rebuild=False)



# -----------------------------
# Routes
# -----------------------------
# Respuesta a health check
@app.get("/health")
def health() -> Dict[str, Any]:
    #return {"ok": True, "app": "adv-test", "model": MODEL}
    return {"ok": True, "app": "adv-test", "model": OPENAI_MODEL}


# ************* Respuesta a request http : se entrega index.html *********************
@app.get("/")
def home():
    return FileResponse("static/index.html")
    
def root():

    #return {"ok":True, "endpoints":["/docs","/health","/chat"] }
    return {
        "message": "Uvicorn está corriendo correctamente",
        "endpoints": ["/health", "/chat","/chat_stream", "/docs"] }
    

# ************** Respuesta al chat de chatGPT ***************************************
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
        #model=MODEL,
        model=OPENAI_MODEL,
        created_at=time.time(),
    )

# ************ Respuesta a chat intercativo /chat_stream ****************************
@app.post("/chat_stream")
def chat_stream(req: ChatRequest):
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI client no inicializado")

    session_messages = get_session_messages(req.session_id)
    session_messages.append({"role": "user", "content": req.message})
    trim_session(session_messages)

    #******** 06 febrero : se agrega la detección del nombre del banco para hacer RAG mas preciso *****
    mode = route_mode(req.message)

    if mode == "RAG":
        if kb is None:
            system_prompt = SYSTEM_PROMPT_GENERAL + "\n\n(Nota: Base RAG no inicializada en este momento.)"
        else: 
            banks = detecta_bancos(req.message)
            if len(banks) == 1:
                context = kb.find_vector_in_redis(req.message, k=5, bank=banks[0])
            else:
                context = kb.find_vector_in_redis(req.message, k=8, bank=None)
            
            if not context.strip(): 
               # aqui va el RAG estricto, si no hay contexto, NO inventes 
                system_prompt = SYSTEM_PROMPT_RAG_TEMPLATE.format(
                    context= "No hay contexto disponible en la base RAG para esta consulta.")
            else: 
                # Aqui va el RAG estricto, si hay contexto, usa el prompt para el RAG: 
                system_prompt = SYSTEM_PROMPT_RAG_TEMPLATE.format(context=context)
    else:
        # Prompt General, sin RAG
        system_prompt = SYSTEM_PROMPT_GENERAL
        
    
    messages =[{"role":"system", "content":system_prompt}]
    messages.extend(session_messages)


    def event_generator():
        full = []
        try:
            stream = client.chat.completions.create(
                #model=MODEL,
                model= OPENAI_MODEL,
                messages=messages,
                temperature=req.temperature,
                stream=True,
            )

            for event in stream:
                delta = event.choices[0].delta
                chunk = getattr(delta, "content", None)
                if chunk:
                    full.append(chunk)
                    # SSE: cada evento es "data: ...\n\n"
                    payload = {"type": "chunk", "text": chunk}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            final_text = "".join(full).strip()
            if final_text:
                session_messages.append({"role": "assistant", "content": final_text})
                trim_session(session_messages)

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")