# routers/chat.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from model.schemas import ChatRequest, ChatResponse
from services.rag_custom_service import rag_service
import asyncio
import logging

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """
    RAG 챗봇 쿼리 엔드포인트 (일반 응답)
    """
    try:
        logger.info(f"📩 쿼리 수신: user_id={request.user_id}, query={request.query[:50]}...")

        # RAG 파이프라인 실행
        result = rag_service.process_query(
            user_id=request.user_id,
            query=request.query
        )

        logger.info(f"✅ 쿼리 처리 완료: tokens={result['usage']['total_tokens']}")

        return ChatResponse(
            user_query=result["user_query"],
            ai_response=result["ai_response"],
            source_chunks=result["source_chunks"],
            usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"❌ 쿼리 처리 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"쿼리 처리 중 오류: {str(e)}")


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    RAG 챗봇 스트리밍 응답 엔드포인트
    """
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            logger.info(f"🌊 스트리밍 시작: user_id={request.user_id}, query={request.query[:50]}...")

            # 스트리밍 토큰 생성
            for token in rag_service.process_query_streaming(
                    user_id=request.user_id,
                    query=request.query
            ):
                yield f" {token}\n\n"
                await asyncio.sleep(0.01)  # 너무 빠른 전송 방지

            # 스트림 종료 신호
            yield " [DONE]\n\n"
            logger.info("✅ 스트리밍 완료")

        except Exception as e:
            logger.error(f"❌ 스트리밍 중 오류: {str(e)}")
            yield f" [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

# ❌ 이 부분 삭제! (순환 import 원인)
# app.include_router(chat.router)
