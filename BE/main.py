import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from google import genai

app = FastAPI(title="QA Memory Microservice")

# 1. Khởi tạo Qdrant Cloud & Gemini Client
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

COLLECTION_NAME = "qa_knowledge"

# Tạo Collection nếu chưa tồn tại (Vector 768 chiều cho text-embedding-004)
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

class SearchRequest(BaseModel):
    query_text: str
    top_k: int = 3

class SaveRequest(BaseModel):
    doc_id: str
    text: str

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