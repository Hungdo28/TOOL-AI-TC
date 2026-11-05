import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from google import genai

app = FastAPI(title="QA Memory & Automation Microservice")

# 1. Bật CORS cho phép Web Frontend truy cập không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Cấu hình Biến môi trường
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")

qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

COLLECTION_NAME = "qa_knowledge"

try:
    qdrant_client.get_collection(COLLECTION_NAME)
except Exception:
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=768, distance=Distance.COSINE)
    )

def get_embedding(text: str):
    response = ai_client.models.embed_content(
        model="text-embedding-004",
        contents=text
    )
    return response.embedding.values

# --- MODELS ---
class SearchRequest(BaseModel):
    query_text: str
    top_k: int = 3

class SaveRequest(BaseModel):
    doc_id: str
    text: str

# --- 1. ENDPOINTS TRI THỨC (QDRANT RAG) ---
@app.post("/search-memory")
def search_memory(req: SearchRequest):
    try:
        query_vector = get_embedding(req.query_text)
        search_result = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=req.top_k
        )
        context_list = [hit.payload.get("text", "") for hit in search_result]
        return {"context": "\n---\n".join(context_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/save-memory")
def save_memory(req: SaveRequest):
    try:
        vector = get_embedding(req.text)
        point_id = abs(hash(req.doc_id))
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"doc_id": req.doc_id, "text": req.text}
                )
            ]
        )
        return {"status": "success", "message": f"Saved {req.doc_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. ENDPOINTS QUẢN LÝ BÀI TOÁN & THỰC THI N8N FOR FRONTEND ---
@app.post("/api/tasks/executions")
@app.post("/api/executions")
def trigger_n8n_execution(payload: dict):
    if not N8N_WEBHOOK_URL:
        return {"status": "success", "message": "Trigger received (Missing N8N_WEBHOOK_URL env)"}
    try:
        res = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=60)
        return res.json() if res.headers.get("content-type") == "application/json" else {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi kích hoạt n8n: {str(e)}")

@app.get("/api/tasks")
def get_tasks():
    return []

@app.post("/api/tasks")
def create_task(payload: dict):
    return {"status": "success", "data": payload}

@app.put("/api/tasks/{task_id}")
@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, payload: dict):
    return {"status": "success", "message": f"Updated task {task_id}"}