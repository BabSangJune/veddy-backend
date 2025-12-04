
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Optional, Dict, List
from model.schemas import ChatRequest
from services.langchain_rag_service import langchain_rag_service
from services.supabase_service import SupabaseService
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

def detect_comparison_mode(query: str, history: str = "") -> Dict:
    """
    대화 히스토리를 활용한 스마트 비교 감지
    "두개 차이를 비교해줘" → history에서 IMO DCS, EU MRV 자동 추출
    """

    # 1. 비교 키워드 확인
    comparison_keywords = ["비교", "차이", "다른점", "공통점", "vs", "VS"]
    is_comparison = any(kw in query for kw in comparison_keywords)

    if not is_comparison:
        return {"is_comparison": False, "topics": []}

    # 2. 명시적 토픽 추출 (A vs B, A와 B 등)
    vsmatch = re.search(r'([^\s,]+?)\s*(?:vs|VS|와|vs)\s*([^\s,]+)', query, re.IGNORECASE)
    if vsmatch:
        topic1, topic2 = vsmatch.groups()
        return {
            "is_comparison": True,
            "topics": [topic1.strip(), topic2.strip()]
        }

    # 3. "두개", "둘" 등 대명사 → History에서 최근 2개 토픽 추출
    pronouns = ["두개", "둘", "양쪽", "이 두", "저 두"]
    if any(p in query for p in pronouns) and history:
        topics = extract_topics_from_history(history)
        if len(topics) >= 2:
            return {
                "is_comparison": True,
                "topics": topics[:2]  # 최근 2개만
            }

    # 4. 질문에서 직접 추출
    words = query.split()
    topics = [w for w in words
              if len(w) > 1 and w.isupper() and w not in [",", "와", "의", "는"]]

    if len(topics) >= 2:
        return {
            "is_comparison": True,
            "topics": topics[:2]
        }

    return {"is_comparison": False, "topics": []}

def extract_topics_from_history(history: str) -> List[str]:
    """
    History에서 주요 토픽 추출 (IMO DCS, EU MRV 등)
    """
    # 대문자 약어 패턴 (IMO DCS, EU MRV 등)
    acronym_pattern = r'\b[A-Z]{2,}(?:\s+[A-Z]{2,})?\b'
    matches = re.findall(acronym_pattern, history)

    # 중복 제거 & 최근 순
    seen = set()
    topics = []
    for match in reversed(matches):
        normalized = re.sub(r'[^\w\s]', '', match).strip()
        if normalized and normalized not in seen and len(topics) < 3:
            topics.append(match)
            seen.add(normalized)

    return list(reversed(topics))  # 원래 순서 복원



# ===== 메인 채팅 엔드포인트 =====

@router.post("/stream")
async def chat_stream(
        request_body: ChatRequest,
        request: Request,
        user: dict = Depends(verify_supabase_token)
):
    """
    ✨ VEDDY 채팅 스트리밍 엔드포인트 (Phase 3-A Final)

    📋 기능:
    1. 할루시네이션 방지 (문서 기반 답변만)
    2. 답변 포맷 강제 (번호 + 들여쓰기 + URL)
    3. 표 모드 (TABLE_MODE_PROMPT)
    4. 비교 모드 (자동 감지 또는 수동)
    5. History 지원 (이전 대화 자동 로드)
    6. URL 자동 추출 (documents metadata)

    📊 흐름:
    History 조회 → Comparison 감지 → 하이브리드 검색 → LLM → 포맷팅 → DB 저장 → 전송
    """

    user_id = user["user_id"]
    email = user.get("email")
    name = user.get("name")
    access_token = user["access_token"]

    # ✅ 요청 추적 ID 생성
    request_id = generate_request_id()
    logger = get_logger(__name__, user_id=user_id, request_id=request_id, email=email)

    logger.info("📨 채팅 요청 수신", extra={
        "query": request_body.query[:50],
        "table_mode": request_body.table_mode,
        "has_history": bool(request_body.history),
        "has_comparison": bool(request_body.comparison_info)
    })

    # ✅ 사용자 정보 확인/생성
    user_fk = await user_service.get_or_create_user(
        user_id=user_id,
        email=email,
        name=name,
        auth_type="general"
    )

    user_supabase = SupabaseService(access_token=access_token)

    # ===== PHASE 1: History 조회/전달 =====

    history_text = request_body.history or ""
    if not history_text:
        try:
            # 최근 10개의 대화 조회
            recent_messages = user_supabase.client.table("messages") \
                .select("user_query,ai_response") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .limit(10) \
                .execute()

            # 역순으로 정렬 (가장 오래된 것부터)
            messages = list(reversed(recent_messages.data)) if recent_messages.data else []

            history_parts = []
            for msg in messages:
                q = msg.get('user_query', '')[:100]
                a = msg.get('ai_response', '')[:150]
                if q and a:
                    history_parts.append(f"Q: {q}")
                    history_parts.append(f"A: {a}...")

            history_text = "\n\n".join(history_parts)
            logger.info("✅ History 로드 완료", extra={
                "history_messages": len(messages),
                "history_length": len(history_text)
            })
        except Exception as e:
            logger.warning(f"⚠️ History 조회 실패: {e}")
            history_text = ""

    # ===== PHASE 2: Comparison 감지/설정 =====

    comparison_info = request_body.comparison_info
    if comparison_info is None:
        # 자동 감지
        comparison_info = detect_comparison_mode(request_body.query)
        if comparison_info["is_comparison"]:
            logger.info("🔍 Comparison 자동 감지", extra={
                "topics": comparison_info["topics"]
            })
    else:
        logger.info("📊 Comparison 수동 설정", extra={
            "topics": comparison_info.get("topics", [])
        })

    # ===== PHASE 3: 스트리밍 응답 생성 =====

    async def generate_stream() -> AsyncGenerator[str, None]:
        full_response = ""
        source_chunk_ids = []

        try:
            logger.info("▶️ 스트리밍 시작")

            async def rag_with_timeout():
                nonlocal full_response, source_chunk_ids

                # 🎯 하이브리드 검색 + RAG 처리
                logger.info("🔎 하이브리드 검색 시작", extra={
                    "search_mode": "comparison" if comparison_info["is_comparison"] else "normal"
                })

                for token in langchain_rag_service.process_query_streaming(
                        user_id=user_id,
                        query=request_body.query,
                        table_mode=request_body.table_mode,
                        supabase_client=user_supabase,
                        history=history_text,  # ✅ History 전달
                        comparison_info=comparison_info  # ✅ Comparison 전달
                ):
                    if token:
                        full_response += token

            # ⏱️ 타임아웃 설정 (120초)
            try:
                await asyncio.wait_for(rag_with_timeout(), timeout=120.0)
            except asyncio.TimeoutError:
                logger.error("⏱️ RAG 처리 타임아웃 (120초)")
                yield f" {json.dumps({'type': 'error', 'error': '요청 처리 시간이 초과되었습니다.'}, ensure_ascii=False)}\n\n"
                return

            logger.info("✅ LLM 응답 생성 완료", extra={"length": len(full_response)})

            # ===== PHASE 4: 응답 포맷팅 =====

            # 1. 번호 리스트 정규화 (1. 뒤에 빈 줄 추가)
            formatted = re.sub(r'(\d+\.)\s+', r'\1\n\n', full_response)

            # 2. 제목 정규화 (# 뒤에 빈 줄)
            formatted = re.sub(r'(#{1,3})\s+([^\n]+)', r'\1 \2\n\n', formatted)

            # 3. 리스트 항목 정규화
            formatted = re.sub(r'(-\s+[^\n]+)', r'\1\n', formatted)

            # 4. 참고 문서 섹션 확인
            if '참고 문서' not in formatted and '📚' not in formatted:
                formatted += '\n\n📚 참고 문서:\n(검색 결과 없음)'

            # 5. 과다한 줄바꿈 정리
            formatted = re.sub(r'\n{4,}', '\n\n', formatted)

            logger.info("📝 응답 포맷팅 완료")

            # ===== PHASE 5: DB에 메시지 저장 =====

            try:
                user_supabase.client.table("messages").insert({
                    "user_id": user_id,
                    "user_fk": user_fk,
                    "user_query": request_body.query,
                    "ai_response": formatted,
                    "source_chunk_ids": source_chunk_ids if source_chunk_ids else None,
                    "table_mode": request_body.table_mode,
                    "comparison_mode": comparison_info["is_comparison"],
                    "comparison_topics": comparison_info.get("topics", []),
                    "has_history": bool(history_text),
                    "usage": {},
                    "created_at": datetime.utcnow().isoformat()
                }).execute()

                logger.info("💾 메시지 저장 완료", extra={
                    "chunks": len(source_chunk_ids),
                    "response_length": len(formatted)
                })
            except Exception as save_error:
                logger.error(f"❌ 메시지 저장 실패: {save_error}")

            # ===== PHASE 6: 클라이언트로 스트리밍 전송 =====

            logger.info("📤 클라이언트 전송 시작")

            for i, char in enumerate(formatted):
                # 주기적으로 연결 확인
                if i % 100 == 0 and await request.is_disconnected():
                    logger.warning(f"🔌 클라이언트 연결 끊김 ({i}글자 전송 후)")
                    return

                data = json.dumps({"token": char, "type": "token"}, ensure_ascii=False)
                output = f" {data}\n\n"
                yield output
                await asyncio.sleep(0.001)  # 약간의 지연으로 부하 분산

            # ✅ 완료 신호
            yield f" {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            logger.info("✨ 스트리밍 완료 (성공)", extra={"total_length": len(formatted)})

        except asyncio.CancelledError:
            logger.warning("🛑 스트리밍 취소됨 (클라이언트 연결 끊김)")
            return

        except Exception as e:
            logger.error(f"❌ 스트리밍 오류: {e}", exc_info=True)

            # 사용자 친화적 에러 메시지
            error_msg = "죄송합니다. 일시적인 오류가 발생했습니다."
            if "timeout" in str(e).lower():
                error_msg = "요청 처리 시간이 초과되었습니다."
            elif "connection" in str(e).lower():
                error_msg = "네트워크 연결에 문제가 발생했습니다."
            elif "embedding" in str(e).lower():
                error_msg = "문서 검색 중 오류가 발생했습니다."
            elif "hybrid" in str(e).lower():
                error_msg = "하이브리드 검색 중 오류가 발생했습니다."

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
