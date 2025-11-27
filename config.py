import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Embedding
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "dragon-kue/BGE-m3-ko")
EMBEDDING_MODEL_DIMENSION = int(os.getenv("EMBEDDING_MODEL_DIMENSION", 1024))

# Server
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

# Confluence
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
CONFLUENCE_SPACE_KEY = os.getenv("CONFLUENCE_SPACE_KEY")

TOKENIZERS_PARALLELISM = os.getenv("TOKENIZERS_PARALLELISM", "false")

# CORS - 프론트엔드 도메인
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")
