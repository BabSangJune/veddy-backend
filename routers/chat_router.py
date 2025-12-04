# routers/chat_router.py
"""
🌐 Web 채팅 라우터 (간소화)
- unified_chat_service만 호출
- 인증/로깅/에러처리만 담당
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from model.schemas import ChatRequest
from services.unified_chat_service import unified_chat_service
from services.supabase_service import SupabaseService
from auth.auth_service import verify_supabase_token
from logging_config import get_logger, generate_request_id
import json

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(
        request_body: ChatRequest,
        request: Request,
        user: dict = Depends(verify_supabase_token)
):
    """
    ✨ Web 채팅 스트리밍 엔드포인트

    역할:
    - 인증 확인
    - 통합 서비스 호출
    - 스트리밍 응답 반환
    """

    request_id = generate_request_id()
    logger = get_logger(__name__, request_id=request_id, user_id=user["user_id"])

    user_supabase = SupabaseService(access_token=user["access_token"])

    logger.info("📨 Web 채팅 요청 수신", extra={
        "query": request_body.query[:50],
        "table_mode": request_body.table_mode
    })

    async def generate():
        """스트리밍 응답 생성"""
        try:
            # ✨ 모든 로직은 unified_chat_service가 담당!
            async for token in unified_chat_service.process_chat(
                    user_id=user["user_id"],
                    query=request_body.query,
                    table_mode=request_body.table_mode,
                    client_type="web",
                    supabase_client=user_supabase,
                    email=user.get("email"),
                    name=user.get("name")
            ):
                # 🔥 토큰을 JSON으로 감싸서 전송
                if token.startswith(" {"):
                    # 이미 JSON 형식 (error, done 메시지)
                    yield token
                else:
                    # 일반 텍스트 토큰 → JSON으로 감싸기
                    data = json.dumps({"type": "token", "token": token}, ensure_ascii=False)
                    yield f" {data}\n\n"

        except Exception as e:
            logger.error(f"❌ 채팅 처리 오류: {e}", exc_info=True)
            error_msg = "처리 중 오류가 발생했습니다"
            yield f" {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8"
        }
    )
