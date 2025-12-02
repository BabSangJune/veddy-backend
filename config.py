import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 환경 설정
# ==========================================
ENV = os.getenv("ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
IS_PRODUCTION = ENV == "production"

# ==========================================
# Supabase
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ==========================================
# OpenAI
# ==========================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ==========================================
# Embedding
# ==========================================
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "dragonkue/BGE-m3-ko")
EMBEDDING_MODEL_DIMENSION = int(os.getenv("EMBEDDING_MODEL_DIMENSION", 1024))
TOKENIZERS_PARALLELISM = os.getenv("TOKENIZERS_PARALLELISM", "false")

# ==========================================
# Server
# ==========================================
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

# ==========================================
# Confluence
# ==========================================
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
CONFLUENCE_SPACE_KEY = os.getenv("CONFLUENCE_SPACE_KEY")

# ==========================================
# CORS - 프론트엔드 도메인
# ==========================================
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

# ==========================================
# Gunicorn (프로덕션 전용)
# ==========================================
GUNICORN_WORKERS = int(os.getenv("GUNICORN_WORKERS", 4))

# ==========================================
# Microsoft Teams
# ==========================================
MICROSOFT_APP_ID = os.getenv("MICROSOFT_APP_ID")
MICROSOFT_APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID")


import logging

# ==========================================
# 로깅 설정
# ==========================================

# 기본 로깅 레벨
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ✅ httpcore, hpack DEBUG 로그 끄기 (프로덕션)
if IS_PRODUCTION:
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
else:
    # 개발 모드에서는 DEBUG 유지 (필요 시)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("hpack").setLevel(logging.INFO)
