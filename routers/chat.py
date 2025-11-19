# routers/chat.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from model.schemas import ChatRequest
from services.langchain_rag_service import langchain_rag_service
import asyncio
import logging
import re

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """RAG 챗봇 스트리밍 (✅ 줄바꿈 강제 삽입)"""

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

            # 2. ✅ 강제로 줄바꿈 삽입 (핵심!)
            # 패턴: 번호 뒤에 줄바꿈 추가
            formatted = re.sub(r'(\d+\.)\s+', r'\1\n\n', full_response)

            # 3. 헤더(##) 뒤에 줄바꿈 추가
            formatted = re.sub(r'(#{1,3})\s+([^\n]+)', r'\1 \2\n\n', formatted)

            # 4. 리스트 항목(-) 뒤에 줄바꿈 추가
            formatted = re.sub(r'(-\s+[^\n]+)', r'\1\n', formatted)

            # 5. 참고 문서 섹션 추가
            if '참고 문서' not in formatted:
                formatted += '\n\n📚 참고 문서:\n'

            # 6. 과도한 공백 정리
            formatted = re.sub(r'\n{4,}', '\n\n', formatted)

            logger.info(f"✅ 정규화 완료")

            # 7. ✅ 정규화된 텍스트를 문자 단위로 전송
            for char in formatted:
                yield f" {char}\n\n"
                await asyncio.sleep(0.0001)

            yield f" [DONE]\n\n"
            logger.info(f"✅ 스트리밍 완료")

        except Exception as e:
            logger.error(f"❌ 스트리밍 중 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            yield f" [ERROR] {str(e)}\n\n"

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
