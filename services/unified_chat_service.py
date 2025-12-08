"""
🎯 통합 채팅 서비스 (Web + Teams 공용)

역할:
- History 로드
- 비교 모드 감지 (향상된 자동 감지)
- RAG 처리
- 메시지 저장
- 조율만 담당! (구체적 로직은 각 service에 위임)

책임: 각 service를 조율하는 오케스트레이터 역할
"""

from typing import AsyncGenerator, Dict, Optional, List
from services.langchain_rag_service import langchain_rag_service
from services.supabase_service import SupabaseService
from services.comparison_service import comparison_service
from services.history_service import history_service
from auth.user_service import user_service
from logging_config import get_logger
import asyncio
import json
import time

logger = get_logger(__name__)


class UnifiedChatService:
    """Web + Teams 공용 채팅 서비스 (테이블 모드 + 비교 모드 조합 가능)"""

    async def process_chat(
            self,
            user_id: str,
            query: str,
            table_mode: bool = False,
            client_type: str = "web",  # "web" | "teams"
            supabase_client: Optional[SupabaseService] = None,
            email: Optional[str] = None,
            name: Optional[str] = None,
            conversation_context: Optional[List[Dict]] = None  # ✅ 추가
    ) -> AsyncGenerator[str, None]:
        """
        통합 채팅 처리 (Web + Teams 모두 사용, 테이블 모드 + 비교 모드 조합 가능)

        흐름:
        1. 사용자 정보 확인/생성
        2. History 로드 (DB에서 최근 대화)
        3. 비교 모드 감지 (향상된 자동 감지)
        4. RAG 처리 (하이브리드 검색 + LLM)
        5. 메시지 저장 (DB)

        인자:
        - user_id: 사용자 ID
        - query: 사용자 질문
        - table_mode: 표 모드 사용 여부 (다른 모드와 조합 가능)
        - client_type: 클라이언트 타입 ("web" | "teams")
        - supabase_client: Supabase 클라이언트
        - email: 사용자 이메일 (선택)
        - name: 사용자 이름 (선택)
        - conversation_context: 구조화된 대화 히스토리 (List[Dict])

        생성(yield):
        스트리밍 토큰 (각 문자)

        예시:
        async for token in unified_chat_service.process_chat(
        ...     "user123",
        ...     "IMO DCS vs EU MRV",
        ...     table_mode=True,
        ...     client_type="web"
        ... ):
        ...     print(token, end="", flush=True)
        """

        # 📋 Step 1: 사용자 정보 확인/생성
        logger.info(f"👤 사용자 확인: {user_id}", extra={
            "client_type": client_type,
            "email": email
        })

        user_fk = await user_service.get_or_create_user(
            user_id=user_id,
            email=email,
            name=name,
            auth_type=client_type
        )

        # 📚 Step 2: History 로드
        logger.info("📥 History 로드 시작")

        history_text = await history_service.load_conversation_history(
            user_id=user_id,
            supabase_client=supabase_client
        )

        if history_text:
            logger.info(f"✅ History 로드 완료: {len(history_text)} 글자")
        else:
            logger.info("ℹ️ History 없음 (첫 대화)")

        # 🔍 Step 3: 비교 모드 감지 (향상된 버전)
        logger.info("🔍 비교 모드 감지 시작")

        comparison_info = comparison_service.detect_comparison_mode(
            query=query,
            history=history_text,
            conversation_context=conversation_context  # ✅ 구조화된 history 전달
        )

        if comparison_info.get("is_comparison"):
            logger.info(f"✅ 비교 모드 감지", extra={
                "topics": comparison_info.get("topics"),
                "confidence": comparison_info.get("confidence"),
                "method": comparison_info.get("detection_method")
            })
        else:
            logger.info("ℹ️ 일반 모드")

        # 🎯 Step 4: RAG 처리 (스트리밍)
        logger.info("🔎 RAG 처리 시작", extra={
            "table_mode": table_mode,
            "is_comparison": comparison_info.get("is_comparison"),
            "detection_method": comparison_info.get("detection_method")
        })

        full_response = ""
        source_chunk_ids = []

        try:
            start_time = time.time()

            logger.info("🔎 검색 시작", extra={
                "search_mode": "comparison" if comparison_info.get("is_comparison") else "normal",
                "table_mode": table_mode
            })

            for token in langchain_rag_service.process_query_streaming(
                    user_id=user_id,
                    query=query,
                    table_mode=table_mode,  # ✅ 독립적으로 전달
                    supabase_client=supabase_client,
                    history=history_text,
                    comparison_info=comparison_info,
                    conversation_context=conversation_context  # ✅ 추가
            ):
                # ⏱️ 수동 타임아웃 체크 (120초)
                elapsed = time.time() - start_time
                if elapsed > 120.0:
                    logger.error(f"⏱️ RAG 타임아웃 ({elapsed:.1f}초 경과)")
                    error_msg = "요청 처리 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
                    yield f" {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
                    return

                # 🔥 토큰 처리 및 스트리밍
                if token:
                    full_response += token
                    yield token

                # 이벤트 루프에 양보 (응답성 향상)
                await asyncio.sleep(0)

            logger.info(f"✅ RAG 완료", extra={
                "length": len(full_response),
                "elapsed": f"{time.time() - start_time:.1f}초"
            })

        except asyncio.TimeoutError:
            logger.error("⏱️ RAG 타임아웃 (120초)")
            error_msg = "요청 처리 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
            yield f" {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
            return

        except Exception as e:
            logger.error(f"❌ RAG 처리 오류: {e}", exc_info=True)
            error_msg = f"검색 처리 중 오류가 발생했습니다: {str(e)[:100]}"
            yield f" {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
            return

        # 💾 Step 5: 메시지 저장
        logger.info("💾 메시지 저장", extra={
            "table_mode": table_mode,
            "is_comparison": comparison_info.get("is_comparison")
        })

        save_success = await history_service.save_message(
            user_id=user_id,
            user_fk=user_fk,
            query=query,
            response=full_response,
            table_mode=table_mode,
            comparison_mode=comparison_info.get("is_comparison"),
            source_chunk_ids=source_chunk_ids,
            supabase_client=supabase_client
        )

        if save_success:
            logger.info("✅ 메시지 저장 완료")
        else:
            logger.warning("⚠️ 메시지 저장 실패 (비치명적)")

        # ✨ 스트리밍 완료
        logger.info(f"✨ 채팅 처리 완료", extra={
            "client_type": client_type,
            "length": len(full_response),
            "table_mode": table_mode,
            "is_comparison": comparison_info.get("is_comparison")
        })
        yield f" {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    async def process_chat_non_streaming(
            self,
            user_id: str,
            query: str,
            table_mode: bool = False,
            client_type: str = "web",
            supabase_client: Optional[SupabaseService] = None,
            email: Optional[str] = None,
            name: Optional[str] = None,
            conversation_context: Optional[List[Dict]] = None  # ✅ 추가
    ) -> Dict[str, any]:
        """
        비스트리밍 채팅 처리 (Teams 봇용, 전체 응답을 한 번에 반환)

        장점:
        - 전체 응답 한 번에 수신
        - Teams 적응형 카드 등 구성된 응답에 적합

        반환:
        {
            "response": "전체 응답 텍스트",
            "source_chunk_ids": ["chunk1", "chunk2"],
            "is_comparison": True/False,
            "topics": ["A", "B"],
            "table_mode": bool
        }
        """

        full_response = ""

        # 스트리밍 토큰 수집
        async for token in self.process_chat(
                user_id=user_id,
                query=query,
                table_mode=table_mode,
                client_type=client_type,
                supabase_client=supabase_client,
                email=email,
                name=name,
                conversation_context=conversation_context  # ✅ 전달
        ):
            # 에러나 완료 메시지는 제외
            if token.startswith(" "):
                try:
                    data = json.loads(token[1:].strip())
                    if data.get("type") == "done":
                        break
                except:
                    pass
            else:
                full_response += token

        # 비교 모드 재감지 (이미 감지되었지만 반환용)
        comparison_info = comparison_service.detect_comparison_mode(query, "")

        return {
            "response": full_response,
            "is_comparison": comparison_info.get("is_comparison"),
            "topics": comparison_info.get("topics"),
            "user_id": user_id,
            "client_type": client_type,
            "table_mode": table_mode  # ✅ 추가
        }


# ✅ 싱글톤 인스턴스
unified_chat_service = UnifiedChatService()
