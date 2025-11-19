# routers/chat.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from model.schemas import ChatRequest
from services.langchain_rag_service import langchain_rag_service
import asyncio
import logging
import re
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """RAG 챗봇 스트리밍 (✅ 표준 SSE 형식)"""

    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            logger.info(f"🌊 스트리밍 시작: {request.query[:50]}...")

            # 1. 모든 토큰 수집
            full_response = ""
            for token in langchain_rag_service.process_query_streaming(
                    user_id=request.user_id,
                    query=request.query
            ):
                if token:
                    full_response += token

            logger.info(f"✅ 토큰 수집 완료 (길이: {len(full_response)})")

            # 2. 정규화
            formatted = re.sub(r'(\d+\.)\s+', r'\1\n\n', full_response)
            formatted = re.sub(r'(#{1,3})\s+([^\n]+)', r'\1 \2\n\n', formatted)
            formatted = re.sub(r'(-\s+[^\n]+)', r'\1\n', formatted)

            if '참고 문서' not in formatted:
                formatted += '\n\n📚 참고 문서:\n'

            formatted = re.sub(r'\n{4,}', '\n\n', formatted)

            # 3. ✅ 표준 SSE 형식으로 전송 ( 접두사!)
            for i, char in enumerate(formatted):
                data = json.dumps({"token": char, "type": "token"}, ensure_ascii=False)
                output = f" {data}\n\n"  # ✅ " "로 수정!

                # 디버깅 (처음 3개)
                if i < 3:
                    logger.info(f"전송 [{i}]: {repr(output)}")

                yield output
                await asyncio.sleep(0.001)

            # 4. 완료 신호
            yield f"data: {json.dumps({'type': 'done'})}\n\n"  # ✅ " "로 수정!
            logger.info(f"✅ 스트리밍 완료")

        except Exception as e:
            logger.error(f"❌ 오류: {str(e)}")
            import traceback
            traceback.print_exc()

            yield f" {json.dumps({'type': 'error', 'error': str(e)})}\n\n"  # ✅ " "로 수정!

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
