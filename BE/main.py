import os
import chromadb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai

app = FastAPI(title="QA Memory Microservice")

# 1. Khởi tạo ChromaDB (Dữ liệu tự động lưu vào thư mục ./chroma_db)
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="qa_knowledge")

# 2. Khởi tạo Gemini API Client (Lấy API Key từ môi trường hoặc điền trực tiếp)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Hàm chuyển đổi văn bản thành Vector bằng mô hình Embedding của Gemini
def get_embedding(text: str):
    response = ai_client.models.embed_content(
        model="text-embedding-004",
        contents=text
    )
    return response.embedding.values

# Define Schema cho Request đầu vào
class SearchRequest(BaseModel):
    query_text: str
    top_k: int = 3

class SaveRequest(BaseModel):
    doc_id: str
    text: str

# ---------------- API ENDPOINTS ---------------- #

@app.post("/search-memory")
def search_memory(req: SearchRequest):
    """Tìm kiếm k tri thức cũ có nội dung liên quan nhất với tài liệu mới"""
    try:
        query_vector = get_embedding(req.query_text)
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=req.top_k
        )
        docs = results.get('documents', [[]])[0]
        context = "\n---\n".join(docs) if docs else "Chưa có dữ liệu cũ liên quan."
        return {"status": "success", "context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/save-memory")
def save_memory(req: SaveRequest):
    """Lưu phân tích nghiệp vụ hoặc Test Case mới vào ChromaDB"""
    try:
        doc_vector = get_embedding(req.text)
        collection.add(
            ids=[req.doc_id],
            embeddings=[doc_vector],
            documents=[req.text]
        )
        return {"status": "success", "message": f"Đã lưu thành công ID: {req.doc_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))