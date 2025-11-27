from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from services.supabase_service import supabase_service
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()

# backend/auth/auth_service.py 수정

async def verify_supabase_token(credentials = Depends(security)) -> dict:
    """
    Supabase JWT 토큰 검증 (메타데이터 추출 강화)
    """
    token = credentials.credentials

    try:
        user = supabase_service.client.auth.get_user(token)

        if not user or not user.user:
            logger.error("Invalid token: user not found")
            raise HTTPException(status_code=401, detail="Invalid token")

        logger.info(f"User authenticated: {user.user.id}")

        # ✅ 메타데이터 추출 강화
        user_metadata = user.user.user_metadata or {}
        name = user_metadata.get("full_name") or user_metadata.get("name") or user_metadata.get("preferred_username")
        email = user.user.email

        return {
            "user_id": user.user.id,
            "email": email,
            "name": name,  # ✅ 이름 추가
            "access_token": token
        }

    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Token validation failed")
