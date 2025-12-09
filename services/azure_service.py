"""
☁️ Azure Container Instances Service
- 컨테이너 상태 조회
- 컨테이너 시작/중지
"""

import logging
from typing import Dict, Any, Optional
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from config import (
    AZURE_SUBSCRIPTION_ID,
    AZURE_RESOURCE_GROUP,
    AZURE_CONTAINER_GROUP_NAME,
    IS_PRODUCTION,
)

logger = logging.getLogger(__name__)


class AzureService:
    """Azure Container Instances 관리"""

    def __init__(self):
        self.enabled = IS_PRODUCTION and all([
            AZURE_SUBSCRIPTION_ID,
            AZURE_RESOURCE_GROUP,
            AZURE_CONTAINER_GROUP_NAME,
        ])

        if self.enabled:
            try:
                self.credential = DefaultAzureCredential()
                self.client = ContainerInstanceManagementClient(
                    credential=self.credential,
                    subscription_id=AZURE_SUBSCRIPTION_ID,
                )
                logger.info("✅ Azure Container Instance Client 초기화 성공")
            except Exception as e:
                logger.error(f"❌ Azure 초기화 실패: {e}")
                self.enabled = False
        else:
            logger.warning("⚠️  Azure 설정이 없음 - 로컬 모드로 동작합니다")

    def get_container_status(self) -> Dict[str, Any]:
        """
        📊 Azure 컨테이너 상태 조회

        반환값:
        - "succeeded": 정상 작동
        - "terminated": 종료됨
        - "creating": 생성 중
        - "error": 에러
        """
        if not self.enabled:
            logger.info("⚠️  Azure 비활성화 - 로컬 상태 반환")
            return {
                "status": "running",
                "state": "Local Development",
                "provider": "local",
            }

        try:
            container_group = self.client.container_groups.get(
                resource_group_name=AZURE_RESOURCE_GROUP,
                container_group_name=AZURE_CONTAINER_GROUP_NAME,
            )

            # 상태 매핑
            provisioning_state = container_group.provisioning_state or "Unknown"
            instance_view = container_group.instance_view

            state = "Unknown"
            if instance_view and instance_view.state:
                state = instance_view.state

            logger.info(f"📊 Azure 상태: {provisioning_state} ({state})")

            return {
                "status": provisioning_state.lower(),
                "state": state,
                "restart_count": instance_view.restart_count if instance_view else 0,
                "events": [
                    {
                        "message": event.message,
                        "timestamp": event.first_timestamp.isoformat() if event.first_timestamp else None,
                    }
                    for event in (instance_view.events if instance_view else [])
                ][:5],
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
        🚀 Azure 컨테이너 시작
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
                logger.info("💚 컨테이너 이미 실행 중")
                return {
                    "message": "컨테이너가 이미 실행 중입니다.",
                    "status": "running",
                }

            logger.warning("🔄 Azure 컨테이너 재시작 시작...")

            container_group = self.client.container_groups.get(
                resource_group_name=AZURE_RESOURCE_GROUP,
                container_group_name=AZURE_CONTAINER_GROUP_NAME,
            )

            self.client.containers.restart(
                resource_group_name=AZURE_RESOURCE_GROUP,
                container_group_name=AZURE_CONTAINER_GROUP_NAME,
                container_name=container_group.containers[0].name,
            )

            logger.info("✅ Azure 컨테이너 재시작 요청 완료")

            return {
                "message": "컨테이너 재시작을 요청했습니다.",
                "status": "restarting",
                "estimated_time": "30-40초",
            }

        except Exception as e:
            logger.error(f"❌ Azure 컨테이너 시작 실패: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "error",
            }

    def is_healthy(self) -> bool:
        """
        💚 컨테이너가 정상 상태인지 확인
        """
        status = self.get_container_status()
        return status["status"] in ["succeeded", "running"]

    def get_logs(self, lines: int = 50) -> Optional[str]:
        """
        📋 컨테이너 로그 조회
        """
        if not self.enabled:
            return "Local development - no logs available"

        try:
            container_group = self.client.container_groups.get(
                resource_group_name=AZURE_RESOURCE_GROUP,
                container_group_name=AZURE_CONTAINER_GROUP_NAME,
            )

            logs = self.client.containers.list_logs(
                resource_group_name=AZURE_RESOURCE_GROUP,
                container_group_name=AZURE_CONTAINER_GROUP_NAME,
                container_name=container_group.containers[0].name,
                tail=lines,
            )

            return logs.content

        except Exception as e:
            logger.error(f"❌ 로그 조회 실패: {e}")
            return None


# 싱글톤 인스턴스
azure_service = AzureService()
