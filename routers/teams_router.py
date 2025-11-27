from fastapi import APIRouter, Request, HTTPException, Depends
from botbuilder.schema import Activity, ActivityTypes
import logging
from services.langchain_rag_service import langchain_rag_service
from services.teams_service import teams_service
from auth.auth_service import verify_supabase_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])

@router.post("/messages")
async def handle_teams_message(
        request: Request,
        user: dict = Depends(verify_supabase_token)
):
    """Teams 봇 메시지 핸들러 (🔐 인증 필수)"""
    user_id = user["user_id"]
    activity = None

    try:
        activity_data = await request.json()
        activity = Activity.deserialize(activity_data)

        logger.info(f"Received {activity.type}")

        # TITLE Activity 타입 확인
        if activity.type != ActivityTypes.message:
            return {"status": "ok"}

        user_message = activity.text
        if not user_message or not user_message.strip():
            return {"status": "ok"}

        logger.info(f"Message: {user_message}")

        # TITLE 테이블 모드 감지
        table_keywords = ["테이블", "표", "데이터", "통계"]
        table_mode = any(keyword in user_message for keyword in table_keywords)

        if table_mode:
            logger.info(f"TITLE Step 1.5: 테이블 모드 활성화")

        # TITLE Step 1: Teams 사용자 ID 추출
        teams_user_id = activity.from_property.id if activity.from_property else "teams-user"
        logger.info(f"RAG processing for user_id: {user_id}, teams_user_id: {teams_user_id}")

        # TITLE Step 2: 타이핑 표시
        await teams_service.send_typing_indicator(activity)

        # TITLE Step 3: RAG 처리
        rag_result = langchain_rag_service.process_query(
            user_id=user_id,  # ✅ JWT에서 추출한 user_id 사용
            query=user_message,
            table_mode=table_mode
        )

        answer = rag_result.get("aiResponse", "")
        logger.info(f"RAG complete: {len(answer)} chars")

        # TITLE Step 4: Teams에 응답 전송
        if answer:
            success = await teams_service.send_reply_activity(activity, answer)
            return {
                "status": "success",
                "query": user_message,
                "response_length": len(answer),
                "table_mode": table_mode
            }

        return {"status": "no_response"}

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

        # TITLE Step 5: 에러 메시지 전송 (activity가 있는 경우만)
        if activity:
            try:
                error_msg = f"죄송합니다. 처리 중 오류가 발생했습니다.\n오류: {str(e)}"
                await teams_service.send_reply_activity(activity, error_msg)
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
