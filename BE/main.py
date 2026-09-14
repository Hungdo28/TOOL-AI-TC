import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from google import genai

# --- [1] IMPORT CÁC ROUTER CŨ CỦA ANH Ở ĐÂY ---
# Nếu code cũ anh tách ra file router (ví dụ router.py), anh cần giữ lại dòng import nhé.
# Ví dụ: from router import task_router 

app = FastAPI(title="Tool Kiểm Thử AI & QA Memory")

# --- [2] CẤU HÌNH CORS (Bắt buộc để Frontend gọi không bị lỗi Failed to fetch) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép mọi nguồn (hoặc điền cụ thể ["https://quanlv.io.vn"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [3] KHỞI TẠO QDRANT & GEMINI ---
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

COLLECTION_NAME = "qa_knowledge"

# Tạo Collection nếu chưa tồn tại
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

# --- [4] ĐỊNH NGHĨA DỮ LIỆU ---
class SearchRequest(BaseModel):
    query_text: str
    top_k: int = 3

class SaveRequest(BaseModel):
    doc_id: str
    text: str

# --- [5] API XỬ LÝ MEMORY ---
# (Em đã thêm tiền tố /api để khớp với BACKEND_API_BASE trên Frontend của anh)
@app.post("/api/search-memory")
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

@app.post("/api/save-memory")
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


# --- [6] GẮN LẠI CÁC API TASKS CŨ ---
# NẾU TRƯỚC ĐÂY ANH DÙNG ROUTER: 
# Bỏ comment dòng dưới để nối lại các API `/api/tasks` cũ vào app
# app.include_router(task_router, prefix="/api")

# NẾU TRƯỚC ĐÂY ANH VIẾT THẲNG CÁC HÀM @app.post("/api/tasks") VÀO FILE NÀY:
# Anh dán tất cả các hàm cũ đó xuống dưới dòng này là xong nhé!