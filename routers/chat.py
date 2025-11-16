from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

# ===== 모델 직접 정의 (import 안 함) =====
class ChatRequest(BaseModel):
    """채팅 요청"""
    user_id: str
    query: str


class ChatResponse(BaseModel):
    """채팅 응답"""
    user_query: str
    ai_response: str
    source_chunks: List[Dict[str, Any]]
    usage: Dict[str, int]


# ===== 서비스 import =====
from services.rag_service import rag_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """
    RAG 챗봇 쿼리 엔드포인트

    - user_id: 사용자 ID
    - query: 사용자 질문

    반환:
    - user_query: 사용자 질문
    - ai_response: AI 답변
    - source_chunks: 참고한 청크들
    - usage: 토큰 사용량
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
