# main.py

import sys
import os
import logging

# uvloop 적용
try:
    import uvloop
    import asyncio
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("✅ uvloop 활성화!")
except ImportError:
    print("⚠️  uvloop 미설치 - 기본 asyncio 사용")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ✅ 로깅 설정 (가장 먼저!)
from logging_config import setup_logging
setup_logging()

from config import (
    SERVER_HOST,
    SERVER_PORT,
    ALLOWED_ORIGINS,
    ENV,
    IS_PRODUCTION,
    LOG_LEVEL
)

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from services.embedding_service import embedding_service
from services.supabase_service import supabase_service
from services.langchain_rag_service import langchain_rag_service
from routers import chat_router
from routers import teams_router

logger = logging.getLogger(__name__)

TITLE = "=" * 50

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ==========================================
    # 시작 시 실행 (Startup)
    # ==========================================
    print(TITLE)
    print(f"🚀 VEDDY - Vessellink Buddy! [{ENV.upper()}]")
    print(TITLE)

    # ✅ DB 연결 테스트
    print("📊 Supabase 연결 확인 중...")
    try:
        is_connected = supabase_service.test_connection()
        if is_connected:
            print("✅ Supabase 연결 성공!")
            logger.info("Supabase 연결 성공")  # ✅ JSON 로그
        else:
            print("⚠️  Supabase 연결 실패 - 서비스가 제한될 수 있습니다")
            logger.warning("Supabase 연결 실패")
    except Exception as e:
        print(f"❌ Supabase 연결 오류: {e}")
        logger.error(f"Supabase 연결 오류: {e}", exc_info=True)

    # ✅ 임베딩 모델 워밍업 (선택)
    if ENV == "production":
        print("🤖 임베딩 모델 워밍업 중...")
        try:
            embedding_service.embed_text("테스트")
            print("✅ 임베딩 모델 준비 완료!")
            logger.info("임베딩 모델 워밍업 완료")
        except Exception as e:
            print(f"⚠️  임베딩 모델 워밍업 경고: {e}")
            logger.warning(f"임베딩 모델 워밍업 경고: {e}")

    print("- API 서버 시작")
    print("- Teams 봇 시작")
    if IS_PRODUCTION:
        print("- Swagger 문서 비활성화 (프로덕션 모드)")
    print(TITLE)

    logger.info("VEDDY 서버 시작 완료", extra={
        "environment": ENV,
        "workers": os.getenv("GUNICORN_WORKERS"),
        "swagger_enabled": not IS_PRODUCTION
    })

    yield  # 여기서 앱 실행

    # ==========================================
    # 종료 시 실행 (Shutdown)
    # ==========================================
    print(TITLE)
    print("🛑 VEDDY 서버 종료 중...")
    logger.info("VEDDY 서버 종료 시작")

    try:
        print("✅ 리소스 정리 완료")
        logger.info("리소스 정리 완료")
    except Exception as e:
        print(f"⚠️  종료 중 오류: {e}")
        logger.error(f"종료 중 오류: {e}", exc_info=True)

    print("👋 안녕히 가세요!")
    print(TITLE)

# FastAPI 앱 생성
app = FastAPI(
    title="VEDDY - Vessellink AI",
    description="Confluence RAG API & Teams Bot",
    version="0.2.0",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router.router)
app.include_router(teams_router.router)

@app.get("/api/health")
async def health_check():
    logger.info("Health check 요청", extra={"endpoint": "/api/health"})
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
        logger.info("임베딩 테스트 성공", extra={"text_length": len(text)})
        return {
            "text": text,
            "embedding_dimension": len(embedding),
            "embedding_sample": embedding[:5],
            "status": "success"
        }
    except Exception as e:
        logger.error(f"임베딩 테스트 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test/supabase")
async def test_supabase():
    """Supabase 연결 테스트"""
    try:
        is_connected = supabase_service.test_connection()
        if is_connected:
            documents = supabase_service.list_documents(limit=1)
            logger.info("Supabase 테스트 성공", extra={"documents_count": len(documents)})
            return {
                "status": "connected",
                "message": "✅ Supabase 연결 성공!",
                "documents_count": len(documents)
            }
        else:
            logger.error("Supabase 연결 실패")
            raise HTTPException(status_code=500, detail="Supabase 연결 실패")
    except Exception as e:
        logger.error(f"Supabase 테스트 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test/teams")
async def test_teams():
    """Teams 봇 설정 테스트"""
    try:
        from services.teams_service import teams_service
        logger.info("Teams 설정 확인", extra={"app_id": teams_service.app_id[:8]})
        return {
            "status": "configured",
            "message": "✅ Teams 봇 설정 완료!",
            "app_id": teams_service.app_id[:8] + "...",
            "endpoint": "/api/teams/messages"
        }
    except Exception as e:
        logger.error(f"Teams 테스트 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}", exc_info=True, extra={
        "path": request.url.path,
        "method": request.method
    })
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "status": "error"
        }
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn_config = {
        "app": "main:app",
        "host": SERVER_HOST,
        "port": SERVER_PORT,
        "reload": ENV == "development",
        "log_level": "info",
        "access_log": ENV == "development",  # 개발 모드에서만 access log
    }

    uvicorn.run(**uvicorn_config)
