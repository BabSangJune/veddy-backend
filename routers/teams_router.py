# backend/routers/teams_router.py

from fastapi import APIRouter, Request, HTTPException
from botbuilder.schema import Activity, ActivityTypes
import logging
from services.langchain_rag_service import langchain_rag_service
from services.supabase_service import supabase_service
from services.teams_service import teams_service
from services.microsoft_graph_service import microsoft_graph_service
from auth.user_service import user_service
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])

@router.post("/messages")
async def handle_teams_message(request: Request):
    """Teams 봇 메시지 핸들러 (Microsoft Graph로 사용자 정보 조회)"""
    activity = None

    try:
        activity_data = await request.json()
        activity = Activity.deserialize(activity_data)

        logger.info(f"Received {activity.type}")

        if activity.type != ActivityTypes.message:
            return {"status": "ok"}

        user_message = activity.text
        if not user_message or not user_message.strip():
            return {"status": "ok"}

        logger.info(f"Message: {user_message}")

        # 테이블 모드 감지
        table_keywords = ["테이블", "표", "데이터", "통계"]
        table_mode = any(keyword in user_message for keyword in table_keywords)

        # ✅ Teams 사용자 정보 추출
        teams_user_id = activity.from_property.id if activity.from_property else "teams-user"
        user_id = f"teams_{teams_user_id}"
        user_name = activity.from_property.name if activity.from_property else "Unknown"

        logger.info(f"Teams user: {user_name} ({teams_user_id})")

        # ✅ aad_object_id 추출 (from_property에서!)
        azure_ad_object_id = None
        if activity.from_property and hasattr(activity.from_property, 'aad_object_id'):
            azure_ad_object_id = activity.from_property.aad_object_id
            logger.info(f"✅ aad_object_id found: {azure_ad_object_id}")

        # Graph API 호출용 ID 결정
        graph_user_id = azure_ad_object_id or teams_user_id
        logger.info(f"Graph user_id to use: {graph_user_id}")

        # ✅ Microsoft Graph API로 이메일, 부서 등 조회
        user_email = None
        department = None
        job_title = None

        try:
            graph_user_info = await microsoft_graph_service.get_user_by_id(graph_user_id)
            if graph_user_info:
                user_email = graph_user_info.get("email")
                department = graph_user_info.get("department")
                job_title = graph_user_info.get("jobTitle")
                user_name = graph_user_info.get("displayName") or user_name
                logger.info(f"✅ Graph API 조회 성공: {user_email} / 부서: {department}")
        except Exception as e:
            logger.warning(f"⚠️ Graph API 조회 실패 (이메일 없이 진행): {str(e)}")

        # Tenant ID 추출
        teams_tenant_id = activity.channel_data.get("tenant", {}).get("id") if activity.channel_data else None

        # ✅ 사용자 정보 저장 (users 테이블)
        user_fk = await user_service.get_or_create_user(
            user_id=user_id,
            name=user_name,
            email=user_email,
            department=department,
            auth_type="teams",
            teams_tenant_id=teams_tenant_id,
            metadata={
                "teams_user_id": teams_user_id,
                "azure_ad_object_id": azure_ad_object_id,
                "job_title": job_title,
                "channel_id": activity.channel_id if activity else None
            }
        )
        logger.info(f"user_fk: {user_fk}")

        # RAG 처리
        admin_supabase = supabase_service

        await teams_service.send_typing_indicator(activity)

        rag_result = langchain_rag_service.process_query(
            user_id=user_id,
            query=user_message,
            table_mode=table_mode,
            supabase_client=admin_supabase
        )

        answer = rag_result.get("ai_response", "")
        logger.info(f"RAG complete: {len(answer)} chars")

        # ✅ 메시지 저장
        if answer:
            try:
                admin_supabase.client.table("messages").insert({
                    "user_id": user_id,
                    "user_fk": user_fk,
                    "user_query": user_message,
                    "ai_response": answer,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                logger.info(f"✅ Teams 메시지 저장 완료")
            except Exception as e:
                logger.error(f"⚠️ 메시지 저장 실패: {str(e)}")

        # Teams에 응답 전송
        if answer:
            success = await teams_service.send_reply(activity, answer)
            return {
                "status": "success",
                "query": user_message,
                "response_length": len(answer),
                "table_mode": table_mode
            }

        return {"status": "no_response"}

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

        if activity:
            try:
                error_msg = f"죄송합니다. 처리 중 오류가 발생했습니다.\n오류: {str(e)}"
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
