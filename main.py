import sys
import os
import logging

# ✅ uvloop 적용 (asyncio 성능 2배 향상)
try:
    import uvloop
    import asyncio
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("✅ uvloop 활성화!")
except ImportError:
    print("⚠️  uvloop 미설치 - 기본 asyncio 사용")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# ✅ config 임포트 (환경 변수 로드)
from config import (
    SERVER_HOST,
    SERVER_PORT,
    ALLOWED_ORIGINS,
    ENV,
    IS_PRODUCTION,
    LOG_LEVEL
)

from services.embedding_service import embedding_service
from services.supabase_service import supabase_service
from services.langchain_rag_service import langchain_rag_service
from routers import chat_router
from routers import teams_router

# ✅ 로깅 설정
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TITLE = "=" * 50

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(TITLE)
    print(f"🚀 VEDDY - Vessellink Buddy! [{ENV.upper()}]")
    print(TITLE)
    print("- API 서버 시작")
    print("- Teams 봇 시작")
    if IS_PRODUCTION:
        print("- Swagger 문서 비활성화 (프로덕션 모드)")
    print(TITLE)
    yield
    print("🛑 VEDDY 서버 종료!")

# ✅ FastAPI 앱 생성 (프로덕션에서는 Swagger 비활성화)
app = FastAPI(
    title="VEDDY - Vessellink AI",
    description="Confluence RAG API & Teams Bot",
    version="0.2.0",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 포함
app.include_router(chat_router.router)
app.include_router(teams_router.router)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "🏥 API 서버 정상 작동 중!",
        "environment": ENV,
        "teams_enabled": True
    }

@app.post("/api/test/embedding")
async def test_embedding(text: str):
    """임베딩 테스트"""
    try:
        embedding = embedding_service.embed_text(text)
        return {
            "text": text,
            "embedding_dimension": len(embedding),
            "embedding_sample": embedding[:5],
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Embedding test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test/supabase")
async def test_supabase():
    """Supabase 연결 테스트"""
    try:
        is_connected = supabase_service.test_connection()
        if is_connected:
            documents = supabase_service.list_documents(limit=1)
            return {
                "status": "connected",
                "message": "✅ Supabase 연결 성공!",
                "documents_count": len(documents)
            }
        else:
            raise HTTPException(status_code=500, detail="Supabase 연결 실패")
    except Exception as e:
        logger.error(f"Supabase test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test/teams")
async def test_teams():
    """Teams 봇 설정 테스트"""
    try:
        from services.teams_service import teams_service
        return {
            "status": "configured",
            "message": "✅ Teams 봇 설정 완료!",
            "app_id": teams_service.app_id[:8] + "...",
            "endpoint": "/api/teams/messages"
        }
    except Exception as e:
        logger.error(f"Teams test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "status": "error"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=(ENV == "development")  # ✅ 개발 모드만 자동 재시작
    )
