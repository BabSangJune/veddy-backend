"""
☁️ Azure Container Apps Service
- 컨테이너 상태 조회
- 컨테이너 재시작
"""

import logging
from typing import Dict, Any
from azure.identity import DefaultAzureCredential
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from config import (
    AZURE_SUBSCRIPTION_ID,
    AZURE_RESOURCE_GROUP,
    IS_PRODUCTION,
)
import os

logger = logging.getLogger(__name__)

# Container App 이름
AZURE_CONTAINER_APP_NAME = os.getenv("AZURE_CONTAINER_APP_NAME", "ca-veddy-backend")


class AzureService:
    """Azure Container Apps 관리"""

    def __init__(self):
        self.enabled = IS_PRODUCTION and all([
            AZURE_SUBSCRIPTION_ID,
            AZURE_RESOURCE_GROUP,
            AZURE_CONTAINER_APP_NAME,
        ])

        if self.enabled:
            try:
                self.credential = DefaultAzureCredential()
                self.client = ContainerAppsAPIClient(
                    credential=self.credential,
                    subscription_id=AZURE_SUBSCRIPTION_ID,
                )
                logger.info("✅ Azure Container Apps Client 초기화 성공")
            except Exception as e:
                logger.error(f"❌ Azure 초기화 실패: {e}")
                self.enabled = False
        else:
            logger.warning("⚠️  Azure 설정이 없음 - 로컬 모드로 동작합니다")

    def get_container_status(self) -> Dict[str, Any]:
        """
        📊 Azure Container App 상태 조회
        """
        if not self.enabled:
            logger.info("⚠️  Azure 비활성화 - 로컬 상태 반환")
            return {
                "status": "running",
                "state": "Local Development",
                "provider": "local",
            }

        try:
            # Container App 조회
            container_app = self.client.container_apps.get(
                resource_group_name=AZURE_RESOURCE_GROUP,
                container_app_name=AZURE_CONTAINER_APP_NAME,
            )

            # 상태 확인
            provisioning_state = container_app.properties.provisioning_state
            running_status = container_app.properties.running_status

            logger.info(f"📊 Azure 상태: {provisioning_state} / {running_status}")

            return {
                "status": provisioning_state.lower(),
                "state": running_status,
                "provider": "azure",
                "replicas": container_app.properties.configuration.active_revisions_mode,
            }

        except Exception as e:
            logger.error(f"❌ Azure 상태 조회 실패: {e}", exc_info=True)
            return {
                "status": "error",
                "state": str(e),
                "provider": "azure",
            }

    def start_container(self) -> Dict[str, Any]:
        """
        🚀 Azure Container App 시작
        """
        if not self.enabled:
            logger.info("⚠️  Azure 비활성화 - 로컬 모드")
            return {
                "message": "Local development mode",
                "status": "running",
            }

        try:
            status = self.get_container_status()

            if status["status"] == "succeeded":
                logger.info("💚 Container App 이미 실행 중")
                return {
                    "message": "Container App이 이미 실행 중입니다.",
                    "status": "running",
                }

            # Container App 시작 (Revision 활성화)
            logger.warning("🔄 Container App 시작 중...")

            container_app = self.client.container_apps.get(
                resource_group_name=AZURE_RESOURCE_GROUP,
                container_app_name=AZURE_CONTAINER_APP_NAME,
            )

            # Replica를 늘려서 시작
            container_app.properties.configuration.min_replicas = 1

            self.client.container_apps.begin_update(
                resource_group_name=AZURE_RESOURCE_GROUP,
                container_app_name=AZURE_CONTAINER_APP_NAME,
                container_app_envelope=container_app,
            )

            logger.info("✅ Container App 시작 요청 완료")

            return {
                "message": "Container App 시작을 요청했습니다.",
                "status": "starting",
                "estimated_time": "30-40초",
            }

        except Exception as e:
            logger.error(f"❌ Container App 시작 실패: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "error",
            }

    def is_healthy(self) -> bool:
        """
        💚 Container App이 정상 상태인지 확인
        """
        status = self.get_container_status()
        return status["status"] in ["succeeded", "running"]


# 싱글톤 인스턴스
azure_service = AzureService()
