"""Teams Bot API 라우터 (완전 버전 + 🆕 표 모드 지원)"""

from fastapi import APIRouter, Request, HTTPException
from botbuilder.schema import Activity, ActivityTypes
import logging

from services.langchain_rag_service import langchain_rag_service
from services.teams_service import teams_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])

@router.post("/messages")
async def handle_teams_message(request: Request):
    """Teams Bot Service 엔드포인트 (완전 버전 + 🆕 표 모드 지원)"""
    activity = None
    try:
        # Activity 파싱
        activity_data = await request.json()
        activity = Activity().deserialize(activity_data)
        logger.info(f"📩 Received: {activity.type}")

        # 메시지만 처리
        if activity.type != ActivityTypes.message:
            return {"status": "ok"}

        user_message = activity.text
        if not user_message or user_message.strip() == "":
            return {"status": "ok"}

        logger.info(f"💬 Message: {user_message}")

        # 🔧 Step 1: 타이핑 인디케이터 (선택, 실패 허용)
        await teams_service.send_typing_indicator(activity)

        # 🆕 Step 1.5: 표 모드 키워드 감지
        table_keywords = ["표로", "비교", "차이점", "정리해줘", "비교해줘"]
        table_mode = any(keyword in user_message for keyword in table_keywords)

        if table_mode:
            logger.info(f"📊 표 모드 자동 활성화 (키워드 감지)")

        # 🔧 Step 2: RAG 처리
        user_id = activity.from_property.id if activity.from_property else "teams_user"
        logger.info(f"🔍 RAG processing for {user_id}")

        # 🆕 table_mode 전달
        rag_result = langchain_rag_service.process_query(
            user_id=user_id,
            query=user_message,
            table_mode=table_mode  # 🆕 표 모드 전달
        )

        answer = rag_result.get("ai_response", "답변 생성 실패")
        logger.info(f"✅ RAG complete: {len(answer)} chars")

        # 🔧 Step 3: Teams로 응답 (필수)
        success = await teams_service.send_reply(activity, answer)

        return {
            "status": "success",
            "query": user_message,
            "response_length": len(answer),
            "table_mode": table_mode  # 🆕 응답에 표 모드 상태 포함
        }

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        # 에러 메시지 전송 시도
        if activity:
            try:
                error_msg = "❌ 오류 발생. IT 부서에 문의하세요."
                await teams_service.send_reply(activity, error_msg)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Teams Bot",
        "app_id": teams_service.app_id[:8] + "..."
    }
