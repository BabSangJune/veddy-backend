"""
Teams Bot 서비스 (수정 버전)
"""

from botbuilder.schema import Activity, ActivityTypes
from botframework.connector import ConnectorClient
from botframework.connector.auth import MicrosoftAppCredentials
import os
import logging

logger = logging.getLogger(__name__)


class TeamsService:
    """Microsoft Teams 봇 서비스"""

    def __init__(self):
        self.app_id = os.getenv("MICROSOFT_APP_ID")
        self.app_password = os.getenv("MICROSOFT_APP_PASSWORD")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID")

        if not self.app_id or not self.app_password:
            raise ValueError(
                "MICROSOFT_APP_ID and MICROSOFT_APP_PASSWORD must be set"
            )

        logger.info(f"✅ TeamsService initialized with App ID: {self.app_id[:8]}...")

    async def send_reply(self, activity: Activity, message: str) -> bool:
        """
        Teams로 응답 메시지 전송
        """
        try:
            # 디버깅 로그
            logger.info(f"🔍 Service URL: {activity.service_url}")
            logger.info(f"🔍 Conversation ID: {activity.conversation.id}")

            # ✅ 수정: tenant_id 파라미터 제거
            credentials = MicrosoftAppCredentials(
                self.app_id,
                self.app_password,
                self.tenant_id
            )

            connector = ConnectorClient(
                credentials,
                base_url=activity.service_url
            )

            reply = Activity(
                type=ActivityTypes.message,
                text=message,
                conversation=activity.conversation,
                recipient=activity.from_property,
                from_property=activity.recipient
            )

            connector.conversations.send_to_conversation(
                activity.conversation.id,
                reply
            )

            logger.info("✅ Reply sent successfully to Teams")
            return True

        except Exception as e:
            logger.error(f"❌ Teams 응답 전송 실패: {e}", exc_info=True)
            raise

    async def send_typing_indicator(self, activity: Activity) -> bool:
        """타이핑 인디케이터 전송"""
        try:
            credentials = MicrosoftAppCredentials(
                self.app_id,
                self.app_password
            )

            connector = ConnectorClient(
                credentials,
                base_url=activity.service_url
            )

            typing_activity = Activity(
                type=ActivityTypes.typing,
                conversation=activity.conversation,
                recipient=activity.from_property,
                from_property=activity.recipient
            )

            connector.conversations.send_to_conversation(
                activity.conversation.id,
                typing_activity
            )

            logger.debug("✅ Typing indicator sent")
            return True

        except Exception as e:
            logger.warning(f"⚠️ Typing indicator failed (무시): {e}")
            return False


# 싱글톤
teams_service = TeamsService()
