# backend/routers/teams_router.py
# ✅ 대화 컨텍스트 통합 완료

from fastapi import APIRouter, Request, HTTPException
from botbuilder.schema import Activity, ActivityTypes
from services.langchain_rag_service import langchain_rag_service
from services.supabase_service import supabase_service
from services.teams_service import teams_service
from services.microsoft_graph_service import microsoft_graph_service
from services.conversation_service import ConversationService  # 🆕 추가
from auth.user_service import user_service
from datetime import datetime
import asyncio

from logging_config import get_logger, generate_request_id
import logging

base_logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/teams", tags=["teams"])

@router.post("/messages")
async def handle_teams_message(request: Request):
    """Teams 봇 메시지 핸들러"""
    activity = None

    request_id = generate_request_id()
    logger = get_logger(__name__, request_id=request_id)

    try:
        activity_data = await request.json()
        activity = Activity.deserialize(activity_data)

        logger.info("Teams 메시지 수신", extra={
            "activity_type": activity.type
        })

        if activity.type != ActivityTypes.message:
            return {"status": "ok"}

        user_message = activity.text
        if not user_message or not user_message.strip():
            return {"status": "ok"}

        # 테이블 모드 감지
        table_keywords = ["테이블", "표", "데이터", "통계"]
        table_mode = any(keyword in user_message for keyword in table_keywords)

        # Teams 사용자 정보 추출
        teams_user_id = activity.from_property.id if activity.from_property else "teams-user"
        user_id = f"teams_{teams_user_id}"
        user_name = activity.from_property.name if activity.from_property else "Unknown"

        logger = get_logger(__name__,
                            request_id=request_id,
                            user_id=user_id,
                            teams_user_name=user_name)

        logger.info("Teams 사용자 확인", extra={
            "teams_user_id": teams_user_id,
            "user_name": user_name
        })

        # aad_object_id 추출
        azure_ad_object_id = None
        if activity.from_property and hasattr(activity.from_property, 'aad_object_id'):
            azure_ad_object_id = activity.from_property.aad_object_id
            logger.info("AAD Object ID 추출", extra={
                "azure_ad_object_id": azure_ad_object_id
            })

        graph_user_id = azure_ad_object_id or teams_user_id

        # Microsoft Graph API로 이메일, 부서 등 조회
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

                logger.info("Graph API 조회 성공", extra={
                    "email": user_email,
                    "department": department
                })
        except Exception as graph_error:
            logger.warning("Graph API 조회 실패", extra={
                "error": str(graph_error)
            })

        teams_tenant_id = activity.channel_data.get("tenant", {}).get("id") if activity.channel_data else None

        # 사용자 정보 저장
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

        logger.info("사용자 정보 저장 완료", extra={"user_fk": user_fk})

        admin_supabase = supabase_service

        await teams_service.send_typing_indicator(activity)

        logger.info("RAG 처리 시작", extra={
            "query_length": len(user_message),
            "table_mode": table_mode
        })

        # RAG 처리
        rag_result = None
        answer = ""
        source_chunk_ids = []
        usage = {}
        conversation_id = None  # 🆕

        try:
            # 🆕 Step 1: 대화 컨텍스트 로드
            conversation_service = ConversationService(admin_supabase)

            # 대화 ID 조회/생성
            conversation_id = conversation_service.get_or_create_conversation(
                user_id=user_id,
                user_fk=user_fk,
                conversation_id=None  # Teams는 항상 활성 대화 사용
            )

            # 대화 히스토리 로드
            history = conversation_service.get_conversation_history(
                conversation_id=conversation_id,
                limit=10  # 최근 5턴
            )

            # 프롬프트 형식으로 변환
            history_text = conversation_service.format_history_for_prompt(
                history=history,
                max_turns=5
            )

            logger.info("대화 컨텍스트 로드", extra={
                "conversation_id": conversation_id,
                "history_turns": len(history) // 2 if history else 0
            })

            # 🆕 Step 2: 컨텍스트 포함 쿼리 생성
            if history_text:
                contextual_query = f'''이전 대화:
{history_text}

현재 질문: {user_message}

위 대화 맥락을 고려하여 현재 질문에 답변해주세요.'''
            else:
                contextual_query = user_message

            # Step 3: RAG 처리 (컨텍스트 포함 쿼리)
            rag_result = await asyncio.wait_for(
                asyncio.to_thread(
                    langchain_rag_service.process_query,
                    user_id=user_id,
                    query=contextual_query,
                    table_mode=table_mode,
                    supabase_client=admin_supabase
                ),
                timeout=120.0
            )

            # 정상 처리
            answer = rag_result.get("ai_response", "")
            source_chunk_ids = rag_result.get("source_chunk_ids", [])
            usage = rag_result.get("usage", {})

            logger.info("RAG 처리 완료", extra={
                "response_length": len(answer),
                "chunks_count": len(source_chunk_ids)
            })

        except asyncio.TimeoutError:
            logger.error("RAG 처리 타임아웃", extra={"timeout_seconds": 120})
            error_msg = "죄송합니다. 요청 처리 시간이 초과되었습니다.\n잠시 후 다시 시도해 주세요."
            await teams_service.send_reply(activity, error_msg)
            return {"status": "timeout"}

        # 메시지 저장 + 대화 제목 업데이트
        if answer:
            for attempt in range(2):
                try:
                    admin_supabase.client.table("messages").insert({
                        "user_id": user_id,
                        "user_fk": user_fk,
                        "user_query": user_message,
                        "ai_response": answer,
                        "conversation_id": conversation_id,  # 🆕 추가
                        "source_chunk_ids": source_chunk_ids if source_chunk_ids else None,
                        "usage": usage if usage else {},
                        "created_at": datetime.utcnow().isoformat()
                    }).execute()

                    # 🆕 첫 메시지면 대화 제목 업데이트
                    if conversation_id and len(history) == 0:
                        title = user_message[:50] + "..." if len(user_message) > 50 else user_message
                        conversation_service.update_conversation_title(
                            conversation_id=conversation_id,
                            title=title
                        )

                    logger.info("메시지 저장 완료", extra={
                        "attempt": attempt + 1,
                        "conversation_id": conversation_id
                    })
                    break

                except Exception as save_error:
                    if attempt == 0:
                        logger.warning("메시지 저장 실패 (재시도)", extra={
                            "error": str(save_error)
                        })
                        await asyncio.sleep(0.5)
                    else:
                        logger.error("메시지 저장 최종 실패", extra={
                            "error": str(save_error)
                        })

        # Teams에 응답 전송
        if answer:
            success = await teams_service.send_reply(activity, answer)
            logger.info("Teams 응답 전송 완료", extra={
                "success": success
            })

            return {
                "status": "success",
                "query": user_message,
                "response_length": len(answer),
                "table_mode": table_mode,
                "conversation_id": conversation_id  # 🆕 추가
            }

        return {"status": "no_response"}

    except Exception as e:
        logger.error("Teams 메시지 처리 오류", extra={
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)

        if activity:
            try:
                error_msg = "죄송합니다. 일시적인 오류가 발생했습니다."

                if "timeout" in str(e).lower():
                    error_msg = "요청 처리 시간이 초과되었습니다."
                elif "graph" in str(e).lower():
                    error_msg = "사용자 정보 조회 중 오류가 발생했습니다."
                elif "supabase" in str(e).lower() or "database" in str(e).lower():
                    error_msg = "데이터베이스 연결에 문제가 발생했습니다."

                error_msg += "\n잠시 후 다시 시도해 주세요."

                await teams_service.send_reply(activity, error_msg)
            except Exception as send_error:
                logger.error("에러 메시지 전송 실패", extra={
                    "error": str(send_error)
                })

        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health")
async def health():
    logger = get_logger(__name__)
    logger.info("Teams health check")
    return {
        "status": "healthy",
        "service": "Teams Bot",
        "app_id": teams_service.app_id[:8] + "..."
    }
