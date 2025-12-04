# routers/teams_router.py - 【완전한 버전】

"""
👥 Teams 봇 라우터 (완전 스트리밍 + Typing Indicator)
- Azure Bot Framework 호환
- unified_chat_service 호출
- REST API 스트리밍 지원
"""

import asyncio
import logging
from fastapi import APIRouter, Request, HTTPException
from botbuilder.schema import Activity, ActivityTypes
from services.unified_chat_service import unified_chat_service
from services.supabase_service import supabase_service
from services.teams_service import teams_service
from services.microsoft_graph_service import microsoft_graph_service
from logging_config import get_logger, generate_request_id

# ✅ 중요: router 객체 생성
router = APIRouter(prefix="/api", tags=["teams"])

logger = logging.getLogger(__name__)


@router.post("/messages")
async def handle_teams_message(request: Request):
    """
    👥 Teams Bot Framework 메시지 핸들러 (완전 스트리밍)

    흐름:
    1️⃣ streamId 생성 (informative)
    2️⃣ 진행 상황 업데이트 (informative)
    3️⃣ 실시간 토큰 스트리밍 (streaming)
    4️⃣ 최종 응답 (final)
    """

    request_id = generate_request_id()
    logger = get_logger(__name__, request_id=request_id)

    activity = None

    try:
        # 📥 요청 파싱
        activity_data = await request.json()
        activity = Activity.deserialize(activity_data)

        # 메시지 확인
        if activity.type != ActivityTypes.message:
            return {"status": "ok"}

        user_message = activity.text
        if not user_message or not user_message.strip():
            return {"status": "ok"}

        # 👤 사용자 정보 추출
        teams_user_id = activity.from_property.id if activity.from_property else "unknown"
        user_id = f"teams_{teams_user_id}"
        user_name = activity.from_property.name if activity.from_property else "Unknown"
        service_url = activity.service_url
        conversation_id = activity.conversation.id

        logger.info("👥 Teams 메시지 수신", extra={
            "user_id": user_id,
            "user_name": user_name,
            "user_message": user_message[:50],
            "conversation_id": conversation_id
        })

        # Microsoft Graph에서 이메일 조회 (선택)
        user_email = None
        try:
            if hasattr(activity.from_property, 'aad_object_id'):
                graph_info = await microsoft_graph_service.get_user_by_id(
                    activity.from_property.aad_object_id
                )
                user_email = graph_info.get("email") if graph_info else None
        except Exception as e:
            logger.debug(f"⚠️ Graph API 조회 실패: {e}")

        # 📊 테이블 모드 감지
        table_keywords = ["테이블", "표", "데이터", "통계", "chart", "graph"]
        table_mode = any(kw in user_message for kw in table_keywords)

        # ============ 【스트리밍 시작】 ============

        logger.info("🔄 스트리밍 준비 시작")

        # 【1️⃣】streamId 생성 + 초기 메시지
        stream_id = await teams_service.stream_message_start(
            conversation_id=conversation_id,
            service_url=service_url,
            message="🔍 검색 중..."
        )

        if not stream_id:
            logger.error("❌ streamId 생성 실패")
            raise HTTPException(status_code=500, detail="Stream initialization failed")

        sequence = 2  # 다음 sequence

        # 【2️⃣】Informative 업데이트 (RAG 처리 중)
        logger.info("⏳ Informative 업데이트: RAG 처리 중...")
        await teams_service.stream_message_informative(
            conversation_id=conversation_id,
            service_url=service_url,
            stream_id=stream_id,
            message="📄 문서 검색 중...",
            sequence=sequence
        )
        sequence += 1
        await asyncio.sleep(0.5)

        # 【3️⃣】Response Streaming 준비
        logger.info("✍️ Response Streaming 시작")

        full_response = ""
        token_buffer = ""
        last_update_time = asyncio.get_event_loop().time()
        BUFFER_INTERVAL = 1.5  # 1.5초마다 업데이트 (Teams 권장사항)

        async for token in unified_chat_service.process_chat(
                user_id=user_id,
                query=user_message,
                table_mode=table_mode,
                client_type="teams",
                supabase_client=supabase_service,
                email=user_email,
                name=user_name
        ):
            # ✅ 【추가】 done 시그널 필터링
            if token and isinstance(token, str):
                # JSON 형태의 done 시그널 무시
                if '{"type":' in token or '"type": "done"' in token:
                    continue

                # 정규식으로 더 확실하게 필터링 (선택)
                import re
                if re.search(r'\{["\']type["\']\s*:\s*["\']done["\']\}', token):
                    continue

            # 토큰 누적
            token_buffer += token
            full_response += token

            # 1.5초마다 한 번씩 업데이트 (버퍼링)
            current_time = asyncio.get_event_loop().time()
            if current_time - last_update_time >= BUFFER_INTERVAL:
                logger.info(f"📤 Response 업데이트: {len(full_response)} 글자")

                await teams_service.stream_message_response(
                    conversation_id=conversation_id,
                    service_url=service_url,
                    stream_id=stream_id,
                    message=full_response,  # 누적된 전체 응답
                    sequence=sequence
                )
                sequence += 1
                token_buffer = ""
                last_update_time = current_time
                await asyncio.sleep(0.1)  # 과부하 방지

        # 버퍼에 남은 토큰이 있으면 마지막 업데이트
        if token_buffer:
            logger.info(f"📤 최종 Response 업데이트: {len(full_response)} 글자")

            await teams_service.stream_message_response(
                conversation_id=conversation_id,
                service_url=service_url,
                stream_id=stream_id,
                message=full_response,
                sequence=sequence
            )
            sequence += 1

        # 【4️⃣】최종 응답 (스트리밍 종료)
        logger.info("✅ 최종 응답 전송")

        await teams_service.stream_message_final(
            conversation_id=conversation_id,
            service_url=service_url,
            stream_id=stream_id,
            message=full_response
        )

        logger.info("✨ 스트리밍 완료", extra={
            "total_length": len(full_response),
            "sequence_count": sequence
        })

        # 💾 메시지 저장 (비동기 백그라운드)
        try:
            await supabase_service.client.table("messages").insert({
                "user_id": user_id,
                "user_query": user_message,
                "ai_response": full_response,
                "created_at": activity.timestamp.isoformat() if activity.timestamp else None
            }).execute()
            logger.info("💾 메시지 저장 완료")
        except Exception as save_error:
            logger.warning(f"⚠️ 메시지 저장 실패 (비치명적): {save_error}")

        return {"status": "success", "stream_id": stream_id}

    except Exception as e:
        logger.error(f"❌ Teams 처리 오류: {e}", exc_info=True)

        # 사용자에게 오류 메시지 전송
        try:
            error_msg = "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
            if activity:
                await teams_service.send_reply(activity, f"❌ {error_msg}")
        except:
            pass

        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health():
    """헬스 체크"""
    logger = get_logger(__name__)
    logger.info("👁️ Teams health check")
    return {
        "status": "healthy",
        "service": "Teams Bot",
        "timestamp": asyncio.get_event_loop().time()
    }

# ✅ 중요: 파일 끝에 이것은 필수!
# (router 객체가 제대로 export 되도록)
