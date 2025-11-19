# routers/chat.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime
from pydantic import BaseModel

# ===== 상대 임포트 → 절대 임포트로 변경 =====
from model.schemas import ChatRequest, ChatResponse  # ← 수정
from services.rag_service import rag_service  # ← 수정
import asyncio

# ===== 모델 정의 =====
# class ChatRequest(BaseModel):
#     """채팅 요청"""
#     user_id: str
#     query: str
#
#
# class ChatResponse(BaseModel):
#     """채팅 응답"""
#     user_query: str
#     ai_response: str
#     source_chunks: List[Dict[str, Any]]
#     usage: Dict[str, int]


# ===== 서비스 import =====
from services.rag_service import rag_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """
    RAG 챗봇 쿼리 엔드포인트 (일반 응답)
    """
    try:
        # RAG 파이프라인 실행
        result = rag_service.process_query(
            user_id=request.user_id,
            query=request.query
        )

        return ChatResponse(
            user_query=result["user_query"],
            ai_response=result["ai_response"],
            source_chunks=result["source_chunks"],
            usage=result["usage"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"쿼리 처리 중 오류: {str(e)}")


# ===== 스트리밍 엔드포인트 (새로 추가) =====

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    RAG 챗봇 스트리밍 응답 엔드포인트
    """

    async def generate_stream():
        try:
            # 스트리밍 토큰 생성
            for token in rag_service.process_query_streaming(
                    user_id=request.user_id,
                    query=request.query
            ):
                # ✅ "data: " 접두사 추가
                yield f"data: {token}\n\n"
                await asyncio.sleep(0.01)

            # 스트림 종료 신호
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: ERROR: {str(e)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

