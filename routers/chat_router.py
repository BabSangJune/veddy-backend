# backend/routers/chat_router.py (수정)

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from model.schemas import ChatRequest
from services.langchain_rag_service import langchain_rag_service
from services.supabase_service import SupabaseService
from services.microsoft_graph_service import microsoft_graph_service  # ✅ 추가
from auth.auth_service import verify_supabase_token
from auth.user_service import user_service
import asyncio
import logging
import re
import json
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.post("/stream")
async def chat_stream(
        request: ChatRequest,
        user: dict = Depends(verify_supabase_token)
):
    user_id = user["user_id"]
    email = user.get("email")
    name = user.get("name")
    azure_oid = user.get("azure_oid")  # ✅ 추가
    access_token = user["access_token"]

    logger.info(f"[chat.py] user_id: {user_id}, email: {email}, name: {name}")

    # ✅ 사용자 정보 저장 (users 테이블)
    user_fk = await user_service.get_or_create_user(
        user_id=user_id,
        email=email,
        name=name,
        auth_type="general"
    )
    logger.info(f"[chat.py] user_fk: {user_fk}")

    # ✅ 사용자별 Supabase 클라이언트
    user_supabase = SupabaseService(access_token=access_token)

    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            logger.info(f"🌊 스트리밍 시작: {request.query[:50]}...")
            logger.info(f"👤 사용자: {user_id}")

            # RAG 처리
            full_response = ""
            for token in langchain_rag_service.process_query_streaming(
                    user_id=user_id,
                    query=request.query,
                    table_mode=request.table_mode,
                    supabase_client=user_supabase
            ):
                if token:
                    full_response += token

            logger.info(f"✅ 토큰 수집 완료")

            # 포맷팅
            formatted = re.sub(r'(\d+\.)\s+', r'\1\n\n', full_response)
            formatted = re.sub(r'(#{1,3})\s+([^\n]+)', r'\1 \2\n\n', formatted)
            formatted = re.sub(r'(-\s+[^\n]+)', r'\1\n', formatted)

            if '참고 문서' not in formatted:
                formatted += '\n\n📚 참고 문서:\n'

            formatted = re.sub(r'\n{4,}', '\n\n', formatted)

            # ✅ 메시지 저장 (user_fk 포함)
            try:
                user_supabase.client.table("messages").insert({
                    "user_id": user_id,
                    "user_fk": user_fk,
                    "user_query": request.query,
                    "ai_response": formatted,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                logger.info(f"✅ 메시지 저장 완료")
            except Exception as e:
                logger.error(f"⚠️ 메시지 저장 실패: {str(e)}")

            # 토큰 전송
            for i, char in enumerate(formatted):
                data = json.dumps({"token": char, "type": "token"}, ensure_ascii=False)
                output = f" {data}\n\n"
                yield output
                await asyncio.sleep(0.001)

            # 완료 신호
            yield f" {json.dumps({'type': 'done'})}\n\n"
            logger.info(f"✅ 스트리밍 완료")

        except Exception as e:
            logger.error(f"❌ 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            yield f" {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
        }
    )
