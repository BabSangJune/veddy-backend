# backend/services/microsoft_graph_service.py (수정)

import logging
import aiohttp
import os
import time
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class MicrosoftGraphService:
    """Teams 봇용 Microsoft Graph API 클라이언트"""

    def __init__(self):
        self.graph_url = "https://graph.microsoft.com/v1.0"
        self.client_id = os.getenv("MICROSOFT_APP_ID")           # ✅ 변경
        self.client_secret = os.getenv("MICROSOFT_APP_PASSWORD") # ✅ 변경
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID")
        self.access_token = None
        self.token_expires_at = 0

        logger.info(f"🔍 Graph Service 초기화: client_id={self.client_id[:8]}...")

    async def get_access_token(self) -> str:
        """Application 권한으로 Access Token 발급"""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    result = await response.json()

                    if "access_token" in result:
                        self.access_token = result["access_token"]
                        expires_in = result.get("expires_in", 3600)
                        self.token_expires_at = time.time() + expires_in - 300

                        logger.info("✅ Graph API 토큰 발급 완료")
                        return self.access_token
                    else:
                        logger.error(f"❌ 토큰 발급 실패: {result}")
                        raise Exception(f"Token 발급 실패: {result}")
        except Exception as e:
            logger.error(f"❌ Graph 토큰 발급 오류: {str(e)}")
            raise

    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Teams 사용자 ID로 프로필 조회"""
        try:
            token = await self.get_access_token()

            url = f"{self.graph_url}/users/{user_id}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        logger.info(f"✅ 사용자 조회 성공: {user_data.get('displayName')}")

                        return {
                            "email": user_data.get("mail") or user_data.get("userPrincipalName"),
                            "displayName": user_data.get("displayName"),
                            "department": user_data.get("department"),
                            "jobTitle": user_data.get("jobTitle"),
                            "id": user_data.get("id")
                        }
                    else:
                        logger.warning(f"⚠️ 사용자 조회 실패 ({response.status}): {user_id}")
                        return None

        except Exception as e:
            logger.error(f"❌ 사용자 조회 오류: {str(e)}")
            return None

# 싱글톤 인스턴스
microsoft_graph_service = MicrosoftGraphService()
