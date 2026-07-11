import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from qdrant_client import QdrantClient

from auth.router import router as auth_router
from chat.router import router as chat_router
from users.router import router as users_router

app = FastAPI(title="My AI App Backend")
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(users_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "details": jsonable_encoder(exc.errors(), custom_encoder={ValueError: str}),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# React 프론트엔드(5173 포트)에서 백엔드로 요청을 보낼 수 있도록 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# spec.md 3.5의 환경변수를 기반으로 Qdrant 클라이언트 초기화
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")

try:
    qdrant_client = QdrantClient(
        url=QDRANT_URL, check_compatibility=False
    )
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
