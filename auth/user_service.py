# backend/auth/user_service.py
import logging
from datetime import datetime
from services.supabase_service import supabase_service
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class UserService:
    """사용자 정보 관리 (users 테이블 자동 생성/업데이트)"""

    @staticmethod
    async def get_or_create_user(
            user_id: str,
            email: Optional[str] = None,
            name: Optional[str] = None,
            department: Optional[str] = None,
            auth_type: str = "general",
            teams_tenant_id: Optional[str] = None,
            metadata: Optional[Dict] = None
    ) -> str:
        """
        사용자 정보를 users 테이블에서 찾거나 생성합니다.

        Args:
            user_id: Teams OID 또는 일반 인증 UUID (고유값)
            email: 이메일
            name: 실명
            department: 부서
            auth_type: 인증 방식 ('teams' 또는 'general')
            teams_tenant_id: Teams tenant ID (Teams인 경우만)
            metadata: 추가 정보

        Returns:
            users 테이블의 id (UUID) - 이걸 user_fk로 사용
        """
        try:
            # 1️⃣ 기존 사용자 조회
            response = supabase_service.client.table("users").select("id").eq(
                "user_id", user_id
            ).execute()

            if response.data:
                # 기존 사용자: last_login_at 업데이트
                user_fk = response.data[0]["id"]
                logger.info(f"✅ 기존 사용자 찾음: {user_id} → {user_fk}")

                supabase_service.client.table("users").update({
                    "last_login_at": datetime.utcnow().isoformat()
                }).eq("user_id", user_id).execute()

                return user_fk

            # 2️⃣ 신규 사용자: 저장
            logger.info(f"🆕 신규 사용자 생성: {user_id}")

            insert_data = {
                "user_id": user_id,
                "email": email,
                "name": name,
                "department": department,
                "auth_type": auth_type,
                "teams_tenant_id": teams_tenant_id,
                "metadata": metadata or {},
                "first_login_at": datetime.utcnow().isoformat(),
                "last_login_at": datetime.utcnow().isoformat()
            }

            insert_response = supabase_service.client.table("users").insert(
                insert_data
            ).execute()

            user_fk = insert_response.data[0]["id"]
            logger.info(f"✅ 신규 사용자 저장 완료: {user_id} → {user_fk}")

            return user_fk

        except Exception as e:
            logger.error(f"❌ 사용자 저장 실패: {str(e)}")
            raise

# 싱글톤 인스턴스
user_service = UserService()
