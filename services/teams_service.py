# services/teams_service.py - 【완전 수정 버전】

from botbuilder.schema import Activity, ActivityTypes
from botframework.connector import ConnectorClient
from botframework.connector.auth import MicrosoftAppCredentials
import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class TeamsService:
    """Microsoft Teams 봇 서비스 (스트리밍 지원)"""

    def __init__(self):
        self.app_id = os.getenv("MICROSOFT_APP_ID")
        self.app_password = os.getenv("MICROSOFT_APP_PASSWORD")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")

        if not self.app_id or not self.app_password:
            raise ValueError("MICROSOFT_APP_ID and MICROSOFT_APP_PASSWORD must be set")

        logger.info(f"✅ TeamsService initialized with App ID: {self.app_id[:8]}...")

    # ============ 【기존 메서드】 ============

    async def send_reply(self, activity: Activity, message: str) -> bool:
        """Teams로 응답 메시지 전송 (기존)"""
        try:
            logger.info(f"🔍 Service URL: {activity.service_url}")
            logger.info(f"🔍 Conversation ID: {activity.conversation.id}")

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
        """타이핑 인디케이터 전송 (기존)"""
        try:
            credentials = MicrosoftAppCredentials(
                self.app_id,
                self.app_password,
                self.tenant_id
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

    # ============ 【새로운 스트리밍 메서드】 ============

    async def stream_message_start(
            self,
            conversation_id: str,
            service_url: str,
            message: str = "🔍 검색 중..."
    ) -> Optional[str]:
        """
        【1단계】 스트리밍 시작 - streamId 생성 + 초기 informative 메시지

        Returns:
            streamId (이후 모든 요청에서 사용)
        """
        try:
            payload = {
                "type": "typing",
                "serviceUrl": service_url,
                "channelId": "msteams",
                "from": {
                    "id": self.app_id,
                    "name": "VEDDY Bot"
                },
                "conversation": {
                    "conversationType": "personal",
                    "id": conversation_id
                },
                "locale": "en-US",
                "text": message,
                "entities": [{
                    "type": "streaminfo",
                    "streamType": "informative",
                    "streamSequence": 1
                }]
            }

            # Bearer token 생성
            credentials = MicrosoftAppCredentials(
                self.app_id,
                self.app_password,
                self.tenant_id
            )

            token = credentials.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{service_url}/v3/conversations/{conversation_id}/activities",  # ✅ 슬래시 추가!
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )

            if response.status_code == 201:
                stream_id = response.json().get("id")
                logger.info(f"✅ 스트리밍 시작: streamId={stream_id}")
                return stream_id
            else:
                logger.error(f"❌ 스트리밍 시작 실패: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ stream_message_start 오류: {e}", exc_info=True)
            return None

    async def stream_message_informative(
            self,
            conversation_id: str,
            service_url: str,
            stream_id: str,
            message: str,
            sequence: int
    ) -> bool:
        """
        【2단계】 Informative 업데이트 - 진행 상황 표시
        """
        try:
            payload = {
                "type": "typing",
                "serviceUrl": service_url,
                "channelId": "msteams",
                "from": {
                    "id": self.app_id,
                    "name": "VEDDY Bot"
                },
                "conversation": {
                    "conversationType": "personal",
                    "id": conversation_id
                },
                "locale": "en-US",
                "text": message,
                "entities": [{
                    "type": "streaminfo",
                    "streamId": stream_id,
                    "streamType": "informative",
                    "streamSequence": sequence
                }]
            }

            credentials = MicrosoftAppCredentials(
                self.app_id,
                self.app_password,
                self.tenant_id
            )

            token = credentials.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{service_url}/v3/conversations/{conversation_id}/activities",  # ✅ 슬래시 추가!
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )

            if response.status_code == 202:
                logger.info(f"✅ Informative 업데이트: seq={sequence}")
                return True
            else:
                logger.error(f"❌ Informative 업데이트 실패: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ stream_message_informative 오류: {e}", exc_info=True)
            return False

    async def stream_message_response(
            self,
            conversation_id: str,
            service_url: str,
            stream_id: str,
            message: str,
            sequence: int
    ) -> bool:
        """
        【3단계】 Response Streaming - 실시간 토큰 스트리밍
        """
        try:
            payload = {
                "type": "typing",
                "serviceUrl": service_url,
                "channelId": "msteams",
                "from": {
                    "id": self.app_id,
                    "name": "VEDDY Bot"
                },
                "conversation": {
                    "conversationType": "personal",
                    "id": conversation_id
                },
                "locale": "en-US",
                "text": message,
                "entities": [{
                    "type": "streaminfo",
                    "streamId": stream_id,
                    "streamType": "streaming",
                    "streamSequence": sequence
                }]
            }

            credentials = MicrosoftAppCredentials(
                self.app_id,
                self.app_password,
                self.tenant_id
            )

            token = credentials.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{service_url}/v3/conversations/{conversation_id}/activities",  # ✅ 슬래시 추가!
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )

            if response.status_code == 202:
                logger.info(f"✅ Response Streaming: seq={sequence}, len={len(message)}")
                return True
            else:
                logger.error(f"❌ Response Streaming 실패: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ stream_message_response 오류: {e}", exc_info=True)
            return False

    async def stream_message_final(
            self,
            conversation_id: str,
            service_url: str,
            stream_id: str,
            message: str
    ) -> bool:
        """
        【4단계】 최종 응답 - 스트리밍 종료
        """
        try:
            payload = {
                "type": "message",
                "serviceUrl": service_url,
                "channelId": "msteams",
                "from": {
                    "id": self.app_id,
                    "name": "VEDDY Bot"
                },
                "conversation": {
                    "conversationType": "personal",
                    "id": conversation_id
                },
                "locale": "en-US",
                "text": message,
                "entities": [{
                    "type": "streaminfo",
                    "streamId": stream_id,
                    "streamType": "final"
                }]
            }

            credentials = MicrosoftAppCredentials(
                self.app_id,
                self.app_password,
                self.tenant_id
            )

            token = credentials.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{service_url}/v3/conversations/{conversation_id}/activities",  # ✅ 슬래시 추가!
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )

            if response.status_code == 202:
                logger.info(f"✅ 최종 응답 완료: len={len(message)}")
                return True
            else:
                logger.error(f"❌ 최종 응답 실패: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ stream_message_final 오류: {e}", exc_info=True)
            return False


# 싱글톤
teams_service = TeamsService()
