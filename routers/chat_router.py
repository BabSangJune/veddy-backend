# backend/routers/chat_router.py
# ✅ 대화 컨텍스트 통합 완료

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from model.schemas import ChatRequest
from services.langchain_rag_service import langchain_rag_service
from services.supabase_service import SupabaseService
from services.conversation_service import ConversationService  # 🆕 추가
from auth.auth_service import verify_supabase_token
from auth.user_service import user_service
import asyncio
import re
import json
from datetime import datetime

from logging_config import get_logger, generate_request_id
import logging

base_logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.post("/stream")
async def chat_stream(
        request_body: ChatRequest,
        request: Request,
        user: dict = Depends(verify_supabase_token)
):
    user_id = user["user_id"]
    email = user.get("email")
    name = user.get("name")
    access_token = user["access_token"]

    request_id = generate_request_id()
    logger = get_logger(__name__, user_id=user_id, request_id=request_id, email=email)

    logger.info("채팅 요청 수신", extra={
        "query_length": len(request_body.query),
        "table_mode": request_body.table_mode
    })

    user_fk = await user_service.get_or_create_user(
        user_id=user_id,
        email=email,
        name=name,
        auth_type="general"
    )
    logger.info("사용자 정보 확인", extra={"user_fk": user_fk})

    user_supabase = SupabaseService(access_token=access_token)

    async def generate_stream() -> AsyncGenerator[str, None]:
        full_response = ""
        source_chunk_ids = []
        conversation_id = None  # 🆕

        try:
            logger.info("스트리밍 시작", extra={
                "query_preview": request_body.query[:50]
            })

            async def rag_with_timeout():
                nonlocal full_response, source_chunk_ids, conversation_id

                # 🆕 Step 1: 대화 컨텍스트 로드
                conversation_service = ConversationService(user_supabase)

                conversation_id = conversation_service.get_or_create_conversation(
                    user_id=user_id,
                    user_fk=user_fk,
                    conversation_id=getattr(request_body, 'conversation_id', None)
                )

                history = conversation_service.get_conversation_history(
                    conversation_id=conversation_id,
                    limit=10
                )

                history_text = conversation_service.format_history_for_prompt(
                    history=history,
                    max_turns=5
                )

                logger.info("대화 컨텍스트 로드", extra={
                    "conversation_id": conversation_id,
                    "history_turns": len(history) // 2 if history else 0
                })

                # 🆕 Step 2: 컨텍스트 포함 쿼리 생성
                if history_text:
                    contextual_query = f'''이전 대화:
                    {history_text}
                    
                    현재 질문: {request_body.query}
                    
                    위 대화 맥락을 고려하여 현재 질문에 답변해주세요.'''
                else:
                    contextual_query = request_body.query

                # Step 3: 하이브리드 검색
                from services.embedding_service import embedding_service
                from services.langchain_rag_service import SupabaseRetriever, CustomEmbeddings

                logger.info("하이브리드 검색 시작 (PGroonga + pgvector)")

                embeddings = CustomEmbeddings()
                retriever = SupabaseRetriever(
                    embeddings=embeddings,
                    supabase_client=user_supabase,
                    k=5,
                    threshold=0.3
                )

                _, raw_chunks = retriever.search_hybrid(request_body.query)
                source_chunk_ids = [chunk.get('id') for chunk in raw_chunks if chunk.get('id')]

                logger.info("하이브리드 검색 완료", extra={
                    "chunks_found": len(source_chunk_ids),
                    "search_mode": "PGroonga + pgvector + Reranking"
                })

                # Step 4: LLM 응답 생성
                logger.info("LLM 응답 생성 시작")

                for token in langchain_rag_service.process_query_streaming(
                        user_id=user_id,
                        query=contextual_query,  # 🆕 컨텍스트 포함
                        table_mode=request_body.table_mode,
                        supabase_client=user_supabase
                ):
                    if await request.is_disconnected():
                        logger.warning("클라이언트 연결 끊김")
                        raise asyncio.CancelledError("Client disconnected")

                    if token:
                        full_response += token

                logger.info("LLM 응답 생성 완료", extra={
                    "response_length": len(full_response)
                })

            try:
                await asyncio.wait_for(rag_with_timeout(), timeout=120.0)
            except asyncio.TimeoutError:
                logger.error("RAG 처리 타임아웃", extra={"timeout_seconds": 120})
                yield f" {json.dumps({'type': 'error', 'error': '요청 처리 시간이 초과되었습니다.'}, ensure_ascii=False)}\n\n"
                return

            # Step 5: 포맷팅
            formatted = re.sub(r'(\d+\.)\s+', r'\1\n\n', full_response)
            formatted = re.sub(r'(#{1,3})\s+([^\n]+)', r'\1 \2\n\n', formatted)
            formatted = re.sub(r'(-\s+[^\n]+)', r'\1\n', formatted)

            if '참고 문서' not in formatted:
                formatted += '\n\n📚 참고 문서:\n'

            formatted = re.sub(r'\n{4,}', '\n\n', formatted)

            # Step 6: 메시지 저장
            try:
                user_supabase.client.table("messages").insert({
                    "user_id": user_id,
                    "user_fk": user_fk,
                    "user_query": request_body.query,
                    "ai_response": formatted,
                    "conversation_id": conversation_id,  # 🆕
                    "source_chunk_ids": source_chunk_ids if source_chunk_ids else None,
                    "usage": {},
                    "created_at": datetime.utcnow().isoformat()
                }).execute()

                # 🆕 첫 메시지면 제목 업데이트
                if conversation_id:
                    conversation_service = ConversationService(user_supabase)
                    history = conversation_service.get_conversation_history(
                        conversation_id=conversation_id,
                        limit=2
                    )

                    if len(history) <= 1:
                        title = request_body.query[:50] + "..." if len(request_body.query) > 50 else request_body.query
                        conversation_service.update_conversation_title(
                            conversation_id=conversation_id,
                            title=title
                        )

                logger.info("메시지 저장 완료", extra={
                    "chunks_count": len(source_chunk_ids),
                    "conversation_id": conversation_id
                })
            except Exception as save_error:
                logger.error("메시지 저장 실패", extra={"error": str(save_error)})

            # Step 7: 전송
            logger.info("클라이언트로 전송 시작")

            for i, char in enumerate(formatted):
                if i % 100 == 0 and await request.is_disconnected():
                    logger.warning("클라이언트 연결 끊김", extra={"sent_chars": i})
                    return

                data = json.dumps({"token": char, "type": "token"}, ensure_ascii=False)
                output = f" {data}\n\n"
                yield output
                await asyncio.sleep(0.001)

            yield f" {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

            logger.info("스트리밍 완료", extra={
                "total_chars": len(formatted),
                "status": "success"
            })

        except asyncio.CancelledError:
            logger.warning("스트리밍 취소됨")
            return

        except Exception as e:
            logger.error("스트리밍 오류", extra={
                "error": str(e),
                "error_type": type(e).__name__
            }, exc_info=True)

            error_msg = "죄송합니다. 일시적인 오류가 발생했습니다."

            if "timeout" in str(e).lower():
                error_msg = "요청 처리 시간이 초과되었습니다."
            elif "connection" in str(e).lower():
                error_msg = "네트워크 연결에 문제가 발생했습니다."

            error_msg += " 잠시 후 다시 시도해 주세요."

            try:
                yield f" {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
            except:
                logger.error("에러 메시지 전송 실패")

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
            "X-Request-ID": request_id
        }
    )
