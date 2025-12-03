# backend/services/conversation_service.py

from typing import List, Dict, Optional
from datetime import datetime
import logging
from services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)

class ConversationService:
    """
    대화 컨텍스트 관리 서비스
    - 대화 세션 생성/조회
    - 대화 히스토리 로딩
    - 컨텍스트 포맷팅
    """

    def __init__(self, supabase_client: SupabaseService):
        self.supabase = supabase_client
        self.max_history_turns = 5  # 최근 5턴만 로드

    def get_or_create_conversation(
            self,
            user_id: str,
            user_fk: int,
            conversation_id: Optional[str] = None
    ) -> str:
        """활성 대화 조회 또는 새 대화 생성"""
        try:
            # 1. conversation_id가 주어진 경우 해당 대화 사용
            if conversation_id:
                result = self.supabase.client.table("conversations") \
                    .select("id") \
                    .eq("id", conversation_id) \
                    .eq("user_id", user_id) \
                    .single() \
                    .execute()

                if result.data:
                    logger.info(f"기존 대화 사용: {conversation_id}")
                    return conversation_id

            # 2. RPC 함수로 활성 대화 조회/생성
            result = self.supabase.client.rpc(
                "get_or_create_active_conversation",
                {
                    "p_user_id": user_id,
                    "p_user_fk": user_fk
                }
            ).execute()

            conv_id = result.data
            logger.info(f"대화 ID: {conv_id} (user: {user_id})")

            return conv_id

        except Exception as e:
            logger.error(f"대화 생성/조회 오류: {e}", exc_info=True)
            raise

    def get_conversation_history(
            self,
            conversation_id: str,
            limit: int = None
    ) -> List[Dict]:
        """대화 히스토리 조회 (최근 N턴)"""
        if limit is None:
            limit = self.max_history_turns * 2  # 질문+답변 = 2개씩

        try:
            result = self.supabase.client.rpc(
                "get_conversation_history",
                {
                    "p_conversation_id": conversation_id,
                    "p_limit": limit
                }
            ).execute()

            history = result.data or []
            logger.info(f"대화 히스토리 조회: {len(history)}개 메시지")

            return history

        except Exception as e:
            logger.error(f"대화 히스토리 조회 오류: {e}", exc_info=True)
            return []

    def format_history_for_prompt(
            self,
            history: List[Dict],
            max_turns: int = None
    ) -> str:
        """대화 히스토리를 프롬프트 형식으로 변환"""
        if not history:
            return ""

        if max_turns is None:
            max_turns = self.max_history_turns

        # 최신순으로 정렬되어 있으므로 뒤집기 (시간순)
        history_sorted = list(reversed(history[:max_turns]))

        formatted_parts = []
        for msg in history_sorted:
            user_query = msg.get("user_query", "")
            ai_response = msg.get("ai_response", "")

            formatted_parts.append(f"사용자: {user_query}")
            formatted_parts.append(f"베디: {ai_response}")

        formatted = "\n".join(formatted_parts)

        logger.debug(f"히스토리 포맷팅 완료 ({len(history_sorted)}턴)")

        return formatted

    def update_conversation_title(
            self,
            conversation_id: str,
            title: str
    ) -> bool:
        """대화 제목 업데이트 (첫 질문 기반)"""
        try:
            self.supabase.client.table("conversations") \
                .update({"title": title}) \
                .eq("id", conversation_id) \
                .execute()

            logger.info(f"대화 제목 업데이트: {conversation_id} -> {title}")
            return True

        except Exception as e:
            logger.error(f"대화 제목 업데이트 오류: {e}", exc_info=True)
            return False

    def end_conversation(
            self,
            conversation_id: str
    ) -> bool:
        """대화 종료 (is_active = False)"""
        try:
            self.supabase.client.table("conversations") \
                .update({"is_active": False}) \
                .eq("id", conversation_id) \
                .execute()

            logger.info(f"대화 종료: {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"대화 종료 오류: {e}", exc_info=True)
            return False
