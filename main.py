import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import SERVER_HOST, SERVER_PORT
from services.embedding_service import embedding_service
from services.supabase_service import supabase_service
from services.langchain_rag_service import langchain_rag_service

from routers import chat
from routers import teams_router  # 🆕 Teams 라우터 추가


# 앱 시작/종료 이벤트
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("🚀 베디(VEDDY) 백엔드 서버 시작!")
    print("   - 웹 챗봇 API 활성화")
    print("   - Teams 봇 활성화 🆕")  # 🆕
    print("=" * 50)
    yield
    print("🛑 베디 서버 종료!")


# FastAPI 앱 생성
app = FastAPI(
    title="VEDDY - Vessellink 내부 AI 챗봇",
    description="Confluence 기반 RAG 챗봇 API + Teams 봇",  # 🆕 수정
    version="0.2.0",  # 🆕 버전 업
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chat.router)
app.include_router(teams_router.router)  # 🆕 Teams 라우터 등록


# ==================== 기본 헬스 체크 ====================

@app.get("/api/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "message": "베디가 준비되었습니다! 🎉",
        "teams_enabled": True  # 🆕
    }


# ==================== 테스트 엔드포인트 ====================

@app.post("/api/test/embedding")
async def test_embedding(text: str):
    """테스트: 텍스트 임베딩 생성"""
    try:
        embedding = embedding_service.embed_text(text)
        return {
            "text": text,
            "embedding_dimension": len(embedding),
            "embedding_sample": embedding[:5],
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/test/supabase")
async def test_supabase():
    """테스트: Supabase 연결 확인"""
    try:
        is_connected = supabase_service.test_connection()

        if is_connected:
            documents = supabase_service.list_documents(limit=1)
            return {
                "status": "connected",
                "message": "Supabase 연결 성공!",
                "documents_count": len(documents)
            }
        else:
            raise HTTPException(status_code=500, detail="Supabase 연결 실패")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 🆕 Teams 테스트 엔드포인트
@app.get("/api/test/teams")
async def test_teams():
    """테스트: Teams 봇 설정 확인"""
    try:
        from services.teams_service import teams_service

        return {
            "status": "configured",
            "message": "Teams 봇이 설정되었습니다!",
            "app_id": teams_service.app_id[:8] + "...",
            "endpoint": "/api/teams/messages"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 에러 핸들링 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """전역 예외 처리"""
    logging.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"서버 오류: {str(exc)}",
            "status": "error"
        }
    )


# ==================== 서버 실행 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True
    )
