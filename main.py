"""
Briones Chatbot — Backend (RAG Architecture)
FastAPI + Google Gemini + Pinecone

Run:  uvicorn main:app --reload --port 8000
"""

import logging
import os
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# 🟢 NUEVO: Importar Pinecone
from pinecone import Pinecone

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("briones.chat")

# ── CORS & Rate Limiting (Sin cambios) ────────────────────────────────────────
_DEV_ORIGINS = [
    "http://localhost", "http://localhost:3000", "http://localhost:4200",
    "http://localhost:5173", "http://localhost:5500", "http://localhost:8080",
    "http://127.0.0.1", "http://127.0.0.1:5500", "http://127.0.0.1:5173",
]

_raw_frontend_url = os.getenv("FRONTEND_URL", "").strip()
if _raw_frontend_url:
    ALLOWED_ORIGINS: List[str] = [o.strip() for o in _raw_frontend_url.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = _DEV_ORIGINS

limiter = Limiter(key_func=get_remote_address, default_limits=[])

app = FastAPI(
    title="Briones Chatbot API",
    description="Asistente virtual RAG impulsado por Gemini y Pinecone",
    version="3.0.0",
)
app.state.limiter = limiter

async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiadas consultas. Por favor esperá un momento antes de continuar."},
        headers={"Retry-After": "60"},
    )

app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Clientes de IA y Base de Datos ──────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY no encontrada.")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-2.5-flash"

# 🟢 NUEVO: Inicializar Pinecone y conectar al índice
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    raise RuntimeError("PINECONE_API_KEY no encontrada en el archivo .env")

pc = Pinecone(api_key=PINECONE_API_KEY)
pinecone_index = pc.Index("chatbot-inmobiliaria")


# 🟢 MODIFICADO: El System Instruction ya no tiene propiedades hardcodeadas.
# Solo define la personalidad y las reglas estrictas.
SYSTEM_INSTRUCTION = """
Eres el asistente virtual premium de Beltrán Briones, un reconocido desarrollador
inmobiliario de Buenos Aires (Grupo Briones). Tu tono es profesional, elegante,
persuasivo y conciso. Respondés siempre en español rioplatense. Mantenés respuestas 
cortas y directas (máximo 3-4 líneas por respuesta).

PERFIL PERSONAL DE BELTRÁN (Usa esto si te preguntan por él):
- Es un fanático de River Plate.
- Le encanta jugar al tenis en su tiempo libre.
- Su filosofía de vida es el esfuerzo y la innovación constante.
- Hizo 113 rounds en Call of Duty Black Ops 1 Zombies
- Vive en el barrio de Recoleta
- Recomienda invertir en Saavedra

REGLA ABSOLUTA: Se te proveerá información del catálogo de propiedades en cada mensaje. 
Responde ÚNICAMENTE basándote en la información provista. Nunca inventes información, 
precios, ni datos no mencionados. Si el usuario pregunta algo que no está en el catálogo 
provisto, derivá amablemente al contacto comercial: WhatsApp +54 911 2468 2070 o 
contacto@grupobriones.com.ar.
""".strip()

_GEMINI_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_INSTRUCTION,
    temperature=0.3, # 🟢 MODIFICADO: Bajamos la temperatura para que sea menos creativo y más fiel a los datos
    max_output_tokens=512,
)

# ── Schemas (Sin cambios) ─────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    role: str = Field(..., pattern="^(user|model)$")
    text: str = Field(..., max_length=2000)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    history: Optional[List[HistoryItem]] = Field(default=[], max_length=20)

class ChatResponse(BaseModel):
    response: str

# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest):
    try:
        # 🟢 NUEVO PASO 1: Convertir la pregunta del usuario en un vector
        embed_response = gemini_client.models.embed_content(
            model='gemini-embedding-001',
            contents=body.message
        )
        query_vector = embed_response.embeddings[0].values

        # 🟢 NUEVO PASO 2: Buscar en Pinecone las propiedades más relevantes
        # top_k=3 trae los 3 resultados más similares matemáticamente
        pinecone_results = pinecone_index.query(
            vector=query_vector,
            top_k=3,
            include_metadata=True
        )

        # 🟢 NUEVO PASO 3: Extraer el texto de la metadata de Pinecone
        contextos = []
        for match in pinecone_results.matches:
            # Asumimos que cuando guardaste la data, pusiste el texto en "texto_original"
            if match.metadata and "texto_original" in match.metadata:
                contextos.append(match.metadata["texto_original"])
        
        texto_contexto = "\n---\n".join(contextos)

        # 🟢 NUEVO PASO 4: Armar el "Prompt Aumentado"
        prompt_final = f"""
        Catálogo de propiedades relevante:
        {texto_contexto if texto_contexto else "No se encontraron propiedades exactas para esta consulta."}
        
        Pregunta del usuario:
        {body.message}
        """

        # El resto sigue igual: preparamos el historial y llamamos a Gemini
        raw_history = body.history[-20:] if body.history else []
        gemini_history: List[types.ContentDict] = [
            {"role": item.role, "parts": [{"text": item.text}]}
            for item in raw_history
        ]

        chat_session = gemini_client.chats.create(
            model=GEMINI_MODEL,
            config=_GEMINI_CONFIG,
            history=gemini_history,
        )

        # 🟢 MODIFICADO: Le mandamos el prompt_final (que incluye la data) en vez de solo el mensaje del usuario
        response = chat_session.send_message(prompt_final)

        return ChatResponse(response=response.text)

    except Exception as exc:
        logger.error("Error en /api/chat: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Hubo un inconveniente interno. Por favor intentá de nuevo."
        )