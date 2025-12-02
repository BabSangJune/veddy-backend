# backend/routers/chat_router.py (✅ SSE 에러 핸들링 개선)

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from model.schemas import ChatRequest
from services.langchain_rag_service import langchain_rag_service
from services.supabase_service import SupabaseService
from services.microsoft_graph_service import microsoft_graph_service
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
        request_body: ChatRequest,
        request: Request,  # Request 추가 (연결 끊김 감지용)
        user: dict = Depends(verify_supabase_token)
):
    user_id = user["user_id"]
    email = user.get("email")
    name = user.get("name")
    azure_oid = user.get("azure_oid")
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
        full_response = ""
        source_chunk_ids = []

        try:
            logger.info(f"🌊 스트리밍 시작: {request_body.query[:50]}...")
            logger.info(f"👤 사용자: {user_id}")

            # ✅ 타임아웃 설정 (120초)
            async def rag_with_timeout():
                nonlocal full_response, source_chunk_ids

                # RAG 처리 전에 먼저 문서 검색하여 source_chunk_ids 추출
                from services.embedding_service import embedding_service
                from services.langchain_rag_service import SupabaseRetriever, CustomEmbeddings

                # 검색 수행
                embeddings = CustomEmbeddings()
                retriever = SupabaseRetriever(
                    embeddings=embeddings,
                    supabase_client=user_supabase,
                    k=5,
                    threshold=0.3
                )
                _, raw_chunks = retriever.search(request_body.query)
                source_chunk_ids = [chunk.get('id') for chunk in raw_chunks if chunk.get('id')]

                # RAG 처리 (순수 응답만 반환)
                for token in langchain_rag_service.process_query_streaming(
                        user_id=user_id,
                        query=request_body.query,
                        table_mode=request_body.table_mode,
                        supabase_client=user_supabase
                ):
                    # ✅ 클라이언트 연결 끊김 감지
                    if await request.is_disconnected():
                        logger.warning("⚠️ 클라이언트 연결 끊김 - 스트리밍 중단")
                        raise asyncio.CancelledError("Client disconnected")

                    if token:
                        full_response += token

            # 타임아웃 적용
            try:
                await asyncio.wait_for(rag_with_timeout(), timeout=120.0)
            except asyncio.TimeoutError:
                logger.error("❌ RAG 처리 타임아웃 (120초)")
                yield f" {json.dumps({'type': 'error', 'error': '요청 처리 시간이 초과되었습니다. 다시 시도해 주세요.'}, ensure_ascii=False)}\n\n"
                return

            logger.info(f"✅ 토큰 수집 완료 ({len(full_response)} chars)")

            # 포맷팅
            formatted = re.sub(r'(\d+\.)\s+', r'\1\n\n', full_response)
            formatted = re.sub(r'(#{1,3})\s+([^\n]+)', r'\1 \2\n\n', formatted)
            formatted = re.sub(r'(-\s+[^\n]+)', r'\1\n', formatted)

            if '참고 문서' not in formatted:
                formatted += '\n\n📚 참고 문서:\n'

            formatted = re.sub(r'\n{4,}', '\n\n', formatted)

            # ✅ 메시지 저장 (user_fk, source_chunk_ids, usage 포함!)
            try:
                user_supabase.client.table("messages").insert({
                    "user_id": user_id,
                    "user_fk": user_fk,
                    "user_query": request_body.query,
                    "ai_response": formatted,
                    "source_chunk_ids": source_chunk_ids if source_chunk_ids else None,
                    "usage": {},
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                logger.info(f"✅ 메시지 저장 완료 (1회) - user_fk: {user_fk}, chunks: {len(source_chunk_ids)}")
            except Exception as save_error:
                logger.error(f"⚠️ 메시지 저장 실패: {str(save_error)}")
                # 저장 실패해도 응답은 계속 진행

            # ✅ 토큰 전송 (연결 끊김 체크)
            for i, char in enumerate(formatted):
                # 주기적으로 연결 상태 체크 (100자마다)
                if i % 100 == 0 and await request.is_disconnected():
                    logger.warning("⚠️ 클라이언트 연결 끊김 - 전송 중단")
                    return

                data = json.dumps({"token": char, "type": "token"}, ensure_ascii=False)
                output = f" {data}\n\n"
                yield output
                await asyncio.sleep(0.001)

            # 완료 신호
            yield f" {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            logger.info(f"✅ 스트리밍 완료")

        except asyncio.CancelledError:
            logger.warning("⚠️ 스트리밍 취소됨 (클라이언트 연결 끊김)")
            # 클라이언트가 이미 끊겼으므로 에러 메시지 전송 불필요
            return

        except Exception as e:
            logger.error(f"❌ 스트리밍 오류: {str(e)}", exc_info=True)

            # ✅ 사용자 친화적 에러 메시지
            error_msg = "죄송합니다. 일시적인 오류가 발생했습니다."

            if "timeout" in str(e).lower():
                error_msg = "요청 처리 시간이 초과되었습니다."
            elif "connection" in str(e).lower():
                error_msg = "네트워크 연결에 문제가 발생했습니다."
            elif "embedding" in str(e).lower():
                error_msg = "문서 검색 중 오류가 발생했습니다."

            error_msg += " 잠시 후 다시 시도해 주세요."

            try:
                yield f" {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
            except:
                # yield 자체가 실패하면 로그만 남김
                logger.error("❌ 에러 메시지 전송 실패")

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
