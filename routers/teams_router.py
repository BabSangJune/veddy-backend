from fastapi import APIRouter, Request, HTTPException
from botbuilder.schema import Activity, ActivityTypes
import logging
from services.langchain_rag_service import langchain_rag_service
from services.supabase_service import SupabaseService, supabase_service
from services.teams_service import teams_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])

@router.post("/messages")
async def handle_teams_message(request: Request):
    """Teams 봇 메시지 핸들러 (Teams 자체 인증 사용)"""
    activity = None

    try:
        activity_data = await request.json()
        activity = Activity.deserialize(activity_data)

        logger.info(f"Received {activity.type}")

        # Activity 타입 확인
        if activity.type != ActivityTypes.message:
            return {"status": "ok"}

        user_message = activity.text
        if not user_message or not user_message.strip():
            return {"status": "ok"}

        logger.info(f"Message: {user_message}")

        # 테이블 모드 감지
        table_keywords = ["테이블", "표", "데이터", "통계"]
        table_mode = any(keyword in user_message for keyword in table_keywords)

        if table_mode:
            logger.info(f"Step 1.5: 테이블 모드 활성화")

        # Step 1: Teams 사용자 ID 추출
        teams_user_id = activity.from_property.id if activity.from_property else "teams-user"
        user_id = f"teams_{teams_user_id}"

        logger.info(f"RAG processing for teams_user_id: {teams_user_id}")

        # Step 2: Service Role 클라이언트 사용
        admin_supabase = supabase_service

        # Step 3: 타이핑 표시
        await teams_service.send_typing_indicator(activity)

        # Step 4: RAG 처리
        rag_result = langchain_rag_service.process_query(
            user_id=user_id,
            query=user_message,
            table_mode=table_mode,
            supabase_client=admin_supabase
        )

        answer = rag_result.get("ai_response", "")
        logger.info(f"RAG complete: {len(answer)} chars")

        # Step 5: Teams에 응답 전송
        if answer:
            success = await teams_service.send_reply(activity, answer)  # ✅ send_reply_activity → send_reply
            return {
                "status": "success",
                "query": user_message,
                "response_length": len(answer),
                "table_mode": table_mode
            }

        return {"status": "no_response"}

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

        # Step 6: 에러 메시지 전송
        if activity:
            try:
                error_msg = f"죄송합니다. 처리 중 오류가 발생했습니다.\n오류: {str(e)}"
                await teams_service.send_reply(activity, error_msg)  # ✅ send_reply_activity → send_reply
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
