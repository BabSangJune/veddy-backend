# routers/teams_router.py
"""
👥 Teams 봇 라우터 (간소화)
- Azure Bot Framework 호환
- unified_chat_service 호출
"""

from fastapi import APIRouter, Request, HTTPException
from botbuilder.schema import Activity, ActivityTypes
from services.unified_chat_service import unified_chat_service
from services.supabase_service import supabase_service
from services.teams_service import teams_service
from services.microsoft_graph_service import microsoft_graph_service
from auth.user_service import user_service
from logging_config import get_logger, generate_request_id

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.post("/messages")
async def handle_teams_message(request: Request):
    """
    👥 Teams Bot Framework 메시지 핸들러

    역할:
    - Azure Bot Framework 호환
    - 사용자 정보 추출
    - 통합 서비스 호출
    """

    request_id = generate_request_id()
    logger = get_logger(__name__, request_id=request_id)

    try:
        # 요청 파싱
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

        logger.info("👥 Teams 메시지 수신", extra={
            "user_id": user_id,
            "user_name": user_name,
            "message": user_message[:50]
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

        # Typing indicator 표시
        await teams_service.send_typing_indicator(activity)

        # 📝 테이블 모드 감지
        table_keywords = ["테이블", "표", "데이터", "통계"]
        table_mode = any(kw in user_message for kw in table_keywords)

        # ✨ 통합 서비스 호출 (비스트리밍)
        result = await unified_chat_service.process_chat_non_streaming(
            user_id=user_id,
            query=user_message,
            table_mode=table_mode,
            client_type="teams",
            supabase_client=supabase_service,
            email=user_email,
            name=user_name
        )

        # Teams에 응답 전송
        if result["response"]:
            await teams_service.send_reply(activity, result["response"])
            logger.info("✅ Teams 응답 전송 완료")
            return {"status": "success"}

        return {"status": "no_response"}

    except Exception as e:
        logger.error(f"❌ Teams 처리 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health():
    """헬스 체크"""
    return {"status": "healthy", "service": "Teams Bot"}
