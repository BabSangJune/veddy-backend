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

            # 상태 확인 (직접 속성 접근)
            provisioning_state = getattr(container_app, 'provisioning_state', 'Unknown')

            # configuration 확인
            configuration = getattr(container_app, 'configuration', None)
            min_replicas = 0
            max_replicas = 0

            if configuration:
                scale = getattr(configuration, 'scale', None)
                if scale:
                    min_replicas = getattr(scale, 'min_replicas', 0)
                    max_replicas = getattr(scale, 'max_replicas', 1)

            logger.info(f"📊 Azure 상태: {provisioning_state} (Min: {min_replicas}, Max: {max_replicas})")

            # 상태 매핑
            status_mapping = {
                "Succeeded": "healthy",
                "Running": "healthy",
                "Creating": "warming-up",
                "Updating": "warming-up",
                "Deleting": "error",
                "Failed": "error",
            }

            frontend_status = status_mapping.get(provisioning_state, "idle")

            return {
                "status": frontend_status,
                "state": provisioning_state,
                "provider": "azure",
                "min_replicas": min_replicas,
                "max_replicas": max_replicas,
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
        🚀 Azure Container App 시작 (Min Replicas 조정)
        """
        if not self.enabled:
            logger.info("⚠️  Azure 비활성화 - 로컬 모드")
            return {
                "message": "Local development mode",
                "status": "running",
            }

        try:
            # 현재 상태 확인
            current_status = self.get_container_status()

            if current_status["status"] == "healthy":
                logger.info("💚 Container App 이미 실행 중")
                return {
                    "message": "Container App이 이미 실행 중입니다.",
                    "status": "healthy",
                }

            # Container App 가져오기
            logger.warning("🔄 Container App 시작 중...")

            container_app = self.client.container_apps.get(
                resource_group_name=AZURE_RESOURCE_GROUP,
                container_app_name=AZURE_CONTAINER_APP_NAME,
            )

            # Min Replicas를 1로 설정
            if hasattr(container_app, 'configuration'):
                if hasattr(container_app.configuration, 'scale'):
                    container_app.configuration.scale.min_replicas = 1

                    # 업데이트 요청
                    self.client.container_apps.begin_update(
                        resource_group_name=AZURE_RESOURCE_GROUP,
                        container_app_name=AZURE_CONTAINER_APP_NAME,
                        container_app_envelope=container_app,
                    )

                    logger.info("✅ Container App 시작 요청 완료")

                    return {
                        "message": "Container App 시작을 요청했습니다.",
                        "status": "warming-up",
                        "estimated_time": "30-40초",
                    }

            # 구조를 찾을 수 없으면 에러
            raise ValueError("Container App 설정을 찾을 수 없습니다")

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
        return status["status"] == "healthy"


# 싱글톤 인스턴스
azure_service = AzureService()
