"""
🔄 Container Wake-up Router
- Cold start 처리
- Azure Container Instances 연동
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging
from typing import Dict, Any
from services.azure_service import azure_service
from config import IS_PRODUCTION

router = APIRouter(prefix="/api/container", tags=["container"])
logger = logging.getLogger(__name__)


@router.post("/wake-up")
async def wake_up_container() -> Dict[str, Any]:
    """
    🔌 컨테이너 깨우기 (Cold Start 유발)

    프로덕션: Azure API 호출
    개발환경: 로컬 상태 변경
    """
    try:
        # Azure 상태 조회
        status = azure_service.get_container_status()

        if status["status"] in ["succeeded", "running"]:
            logger.info("💚 컨테이너 이미 HEALTHY 상태")
            return {
                "status": "healthy",
                "message": "컨테이너가 이미 준비되어 있습니다.",
                "azure_status": status,
            }

        # Azure 컨테이너 시작
        logger.info("🌅 Azure 컨테이너 시작 요청 중...")
        result = azure_service.start_container()

        return {
            "status": "warming-up",
            "message": "컨테이너를 시작하는 중입니다. 약 30-40초 소요됩니다.",
            "estimated_time_seconds": 40,
            "azure_response": result,
        }

    except Exception as e:
        logger.error(f"❌ 컨테이너 WAKE-UP 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="컨테이너 시작에 실패했습니다.",
        )


@router.get("/status")
async def get_container_status() -> Dict[str, Any]:
    """
    📊 컨테이너 상태 조회 (Azure 실제 상태)
    """
    try:
        azure_status = azure_service.get_container_status()

        # Azure 상태 → 프론트엔드 상태로 변환
        status_mapping = {
            "succeeded": "healthy",
            "running": "healthy",
            "creating": "warming-up",
            "terminated": "idle",
            "error": "error",
        }

        frontend_status = status_mapping.get(
            azure_status.get("status", "error"),
            "error"
        )

        return {
            "status": frontend_status,
            "azure_status": azure_status,
            "timestamp": datetime.utcnow().isoformat(),
            "provider": "azure" if IS_PRODUCTION else "local",
        }

    except Exception as e:
        logger.error(f"❌ 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_container_logs(lines: int = 50) -> Dict[str, Any]:
    """
    📋 컨테이너 로그 조회
    """
    try:
        logs = azure_service.get_logs(lines=lines)

        return {
            "logs": logs,
            "lines": lines,
        }
    except Exception as e:
        logger.error(f"❌ 로그 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
