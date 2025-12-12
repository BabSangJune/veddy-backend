# services/history_service.py
"""
📚 History 관리 전담 서비스

역할:
- DB에서 대화 히스토리 로드
- 프롬프트 형식으로 변환
- 메시지 저장 및 조회

책임: History 기능만 담당 (독립적, 재사용 가능)
"""

from typing import List, Dict, Optional
from services.supabase_service import SupabaseService
from services.conversation_service import ConversationService
from logging_config import get_logger
from datetime import datetime

logger = get_logger(__name__)


class HistoryService:
    """대화 히스토리 관리 서비스"""

    # 최근 히스토리 개수 설정
    DEFAULT_LIMIT = 15
    MAX_QUERY_LENGTH = 100
    MAX_RESPONSE_LENGTH = 1000

    def __init__(self, supabase_client: Optional[SupabaseService] = None):
        """초기화"""
        self.supabase_client = supabase_client

    async def load_conversation_history(
        self,
        user_id: str,
        limit: int = DEFAULT_LIMIT,
        supabase_client: Optional[SupabaseService] = None
    ) -> str:
        """
        DB에서 최근 대화 히스토리 로드 및 포맷팅

        특징:
        - 최근 N개 메시지 조회
        - 자동 포맷팅 (Q: / A:)
        - 길이 제한으로 토큰 절약

        인자:
        - user_id: 사용자 ID
        - limit: 로드할 메시지 개수 (기본값: 10)
        - supabase_client: Supabase 클라이언트 (선택, 미제공 시 self.supabase_client 사용)

        반환:
        대화 히스토리 텍스트

        예시:
        history = await history_service.load_conversation_history("user123")
        print(history)
        Q: IMO DCS가 뭐야?
        A: IMO DCS는 국제해사기구...

        Q: EU MRV는?
        A: EU MRV는 유럽연합...
        """

        client = supabase_client or self.supabase_client

        if not client:
            logger.warning("⚠️ Supabase 클라이언트 없음")
            return ""

        try:
            logger.debug(f"📥 History 로드 시작: user_id={user_id}, limit={limit}")

            # 최근 메시지 조회 (역순)
            recent_messages = client.client.table("messages") \
                .select("user_query,ai_response") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()

            if not recent_messages.data:
                logger.debug("⚠️ History 데이터 없음")
                return ""

            # 메시지를 원래 순서로 정렬 (가장 오래된 것부터)
            messages = list(reversed(recent_messages.data))

            # 프롬프트 형식으로 변환
            history_parts = []
            for msg in messages:
                q = msg.get('user_query', '')[:self.MAX_QUERY_LENGTH]
                a = msg.get('ai_response', '')[:self.MAX_RESPONSE_LENGTH]

                if q and a:
                    history_parts.append(f"Q: {q}")
                    history_parts.append(f"A: {a}...")

            history_text = "\n\n".join(history_parts)

            logger.info("✅ History 로드 완료", extra={
                "message_count": len(messages),
                "total_length": len(history_text)
            })

            return history_text

        except Exception as e:
            logger.error(f"❌ History 로드 실패: {e}", exc_info=True)
            return ""

    @staticmethod
    def format_history_for_prompt(
        history: Optional[str],
        max_turns: int = 5,
        include_prefix: bool = True
    ) -> str:
        """
        히스토리를 LLM 프롬프트 형식으로 포맷팅

        특징:
        - 최근 N턴만 유지 (토큰 절약)
        - 선택적 프리픽스 추가
        - 빈 히스토리 처리

        인자:
        - history: 히스토리 텍스트
        - max_turns: 최대 턴 수 (기본값: 5)
        - include_prefix: 프리픽스 포함 여부

        반환:
        포맷된 히스토리 텍스트

        예시:
        formatted = format_history_for_prompt(history, max_turns=3)
        print(formatted)
        【이전 대화】
        Q: IMO DCS가 뭐야?
        A: IMO DCS는...
        ---
        Q: EU MRV는?
        A: EU MRV는...
        """

        if not history or not history.strip():
            return ""

        # 최근 N턴만 추출
        turns = history.split("\n\n")
        recent_turns = turns[-(max_turns * 2):]  # Q, A 2개씩
        limited_history = "\n\n".join(recent_turns)

        if not include_prefix:
            return limited_history

        # 프리픽스 추가
        return f"""【이전 대화】
{limited_history}
---"""

    async def save_message(
        self,
        user_id: str,
        user_fk: str,
        query: str,
        response: str,
        conversation_id: Optional[str] = None,
        table_mode: bool = False,
        comparison_mode: bool = False,
        source_chunk_ids: Optional[List[str]] = None,
        supabase_client: Optional[SupabaseService] = None
    ) -> bool:
        """
        사용자 질문과 AI 응답을 DB에 저장

        특징:
        - 메타데이터 함께 저장 (테이블 모드, 비교 모드 등)
        - 반복 실패 시 재시도
        - 자동 타임스탐프 추가

        인자:
        - user_id: 사용자 ID
        - user_fk: 사용자 외래키
        - query: 사용자 질문
        - response: AI 응답
        - conversation_id: 대화 ID (선택)
        - table_mode: 표 모드 사용 여부
        - comparison_mode: 비교 모드 사용 여부
        - source_chunk_ids: 검색 소스 청크 ID 목록
        - supabase_client: Supabase 클라이언트

        반환:
        저장 성공 여부

        예시:
        success = await history_service.save_message(
        ...     "user123",
        ...     "fk_123",
        ...     "IMO DCS vs EU MRV",
        ...     "IMO DCS는...",
        ...     comparison_mode=True
        ... )
        """

        client = supabase_client or self.supabase_client

        if not client:
            logger.error("❌ Supabase 클라이언트 없음")
            return False

        try:
            message_data = {
                "user_id": user_id,
                "user_fk": user_fk,
                "user_query": query,
                "ai_response": response,
                "table_mode": table_mode,
                "comparison_mode": comparison_mode,
                "source_chunk_ids": source_chunk_ids or [],
                "created_at": datetime.utcnow().isoformat()
            }

            # 선택적 필드
            if conversation_id:
                message_data["conversation_id"] = conversation_id

            # 재시도 로직 (최대 2회)
            for attempt in range(2):
                try:
                    client.client.table("messages").insert(message_data).execute()

                    logger.info("💾 메시지 저장 성공", extra={
                        "user_id": user_id,
                        "query_length": len(query),
                        "response_length": len(response)
                    })
                    return True

                except Exception as e:
                    if attempt == 0:
                        logger.warning(f"⚠️ 저장 실패 (재시도): {e}")
                        continue
                    else:
                        raise

        except Exception as e:
            logger.error(f"❌ 메시지 저장 최종 실패: {e}", exc_info=True)
            return False

    @staticmethod
    def extract_conversation_context(
        history: str,
        max_context_length: int = 500
    ) -> str:
        """
        히스토리에서 현재 질문 맥락 추출

        특징:
        - 최근 대화 맥락만 유지
        - 토큰 길이 제한
        - 자동 정리

        인자:
        - history: 전체 히스토리
        - max_context_length: 최대 맥락 길이

        반환:
        추출된 맥락
        """

        if not history:
            return ""

        # 최근 대화만 추출
        turns = history.split("\n\n")
        context_parts = []

        for turn in reversed(turns):
            if len("\n\n".join(context_parts)) + len(turn) > max_context_length:
                break
            context_parts.insert(0, turn)

        return "\n\n".join(context_parts)


# ✅ 싱글톤 인스턴스
history_service = HistoryService()
