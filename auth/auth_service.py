from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from services.supabase_service import supabase_service
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()

# backend/auth/auth_service.py
# backend/auth/auth_service.py (최종 수정)

import jwt
import logging

async def verify_supabase_token(credentials = Depends(security)) -> dict:
    """
    Supabase JWT 토큰 검증 (Azure AD 연동)
    """
    token = credentials.credentials

    try:
        user = supabase_service.client.auth.get_user(token)

        if not user or not user.user:
            logger.error("Invalid token: user not found")
            raise HTTPException(status_code=401, detail="Invalid token")

        logger.info(f"User authenticated: {user.user.id}")

        # ✅ user_metadata에서 정보 추출
        user_metadata = user.user.user_metadata or {}
        email = user_metadata.get("email") or user.user.email
        name = user_metadata.get("full_name") or user_metadata.get("name")
        azure_oid = user_metadata.get("oid") or user_metadata.get("sub")

        # ✅ 이름이 없으면 provider_token에서 추출 시도 (NEW!)
        if not name:
            try:
                # Supabase는 provider_token을 세션에 저장함
                # 프론트엔드에서 받아올 수도 있지만, 여기서는 custom_claims 확인
                custom_claims = user_metadata.get("custom_claims", {})
                if custom_claims:
                    logger.info(f"custom_claims: {custom_claims}")

                # identities에서 이름 추출 시도
                identities = user.user.identities or []
                for identity in identities:
                    if identity.get("provider") == "azure":
                        identity_data = identity.get("identity_data", {})
                        name = identity_data.get("name") or identity_data.get("given_name")
                        if name:
                            logger.info(f"✅ 이름 발견 (identity): {name}")
                            break
            except Exception as e:
                logger.warning(f"⚠️ 이름 추출 실패: {str(e)}")

        logger.info(f"✅ User info: email={email}, name={name}, azure_oid={azure_oid}")

        return {
            "user_id": user.user.id,
            "email": email,
            "name": name,
            "azure_oid": azure_oid,
            "access_token": token
        }

    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Token validation failed")
