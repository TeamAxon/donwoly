import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient

app = FastAPI(title="My AI App Backend")

# React 프론트엔드(5173 포트)에서 백엔드로 요청을 보낼 수 있도록 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# .env에 적어둔 환경변수를 기반으로 Qdrant 클라이언트 초기화
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

try:
    qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
except Exception as e:
    qdrant_client = None
    print(f"Qdrant connection failed: {e}")

@app.get("/")
def read_root():
    return {"message": "FastAPI 백엔드 서버가 정상적으로 작동 중입니다!"}

@app.get("/qdrant-check")
def check_qdrant():
    if qdrant_client:
        try:
            # Qdrant 서버가 살아있는지 헬스체크
            collections = qdrant_client.get_collections()
            return {"status": "connected", "collections": str(collections)}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "not_initialized"}