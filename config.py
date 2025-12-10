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
# CORS
# ==========================================
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

# ==========================================
# Gunicorn
# ==========================================
GUNICORN_WORKERS = int(os.getenv("GUNICORN_WORKERS", 4))

# ==========================================
# Microsoft Teams
# ==========================================
MICROSOFT_APP_ID = os.getenv("MICROSOFT_APP_ID")
MICROSOFT_APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID")

# ==========================================
# Azure Container Instances
# ==========================================
AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
AZURE_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")
AZURE_CONTAINER_APP_NAME = os.getenv("AZURE_CONTAINER_APP_NAME", "ca-veddy-backend")

# ==========================================
# 로깅 설정
# ==========================================
import logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if IS_PRODUCTION:
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
else:
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("hpack").setLevel(logging.INFO)

# ==========================================
# 동적 VECTOR_SEARCH_CONFIG
# ==========================================
def get_vector_search_config():
    """환경별 최적 config 반환"""
    base_config = {
        'ef_search': int(os.getenv("VECTOR_EF_SEARCH", "50")),
        'chunk_tokens': int(os.getenv("VECTOR_CHUNK_TOKENS", "400")),
        'overlap_tokens': int(os.getenv("VECTOR_OVERLAP_TOKENS", "50")),
        'min_chunk_tokens': int(os.getenv("VECTOR_MIN_CHUNK_TOKENS", "30")),
        'similarity_threshold': float(os.getenv("VECTOR_SIMILARITY_THRESHOLD", "0.3"))
    }

    print(f"📊 VECTOR_SEARCH_CONFIG 로드 | ENV={ENV} | ef_search={base_config['ef_search']}")
    return base_config

VECTOR_SEARCH_CONFIG = get_vector_search_config()

# ==========================================
# 리랭커 설정
# ==========================================
RERANKER_CONFIG = {
    'model_name': 'dragonkue/bge-reranker-v2-m3-ko',
    'max_length': 512,
    'enabled': True,  # 리랭킹 활성화 여부
    'top_k': 5  # 최종 반환 개수
}
