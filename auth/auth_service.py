from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from services.supabase_service import supabase_service
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()

async def verify_supabase_token(credentials = Depends(security)) -> dict:
    """
    Supabase JWT 토큰 검증
    Authorization: Bearer <TOKEN>
    """
    token = credentials.credentials

    try:
        # Supabase 클라이언트로 토큰 검증
        user = supabase_service.client.auth.get_user(token)

        if not user or not user.user:
            logger.error("Invalid token: user not found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        logger.info(f"User authenticated: {user.user.id}")

        return {
            "user_id": user.user.id,
            "email": user.user.email,
            "access_token": token  # ✅ 토큰 추가 (옵션 2에 필요)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}"
        )
