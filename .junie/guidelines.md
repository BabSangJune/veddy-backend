# Project Guidelines for Advanced Contributors

## Scope
This document captures project-specific knowledge to speed up development, testing, and debugging for this FastAPI-based RAG backend with Microsoft Teams integration.

**Audience:** Advanced developers. Assumes familiarity with Python packaging, FastAPI, and vector/RAG systems.

---

## Environment and Runtime

### Python Version
- **Required:** Python 3.13 (specified in `pyvenv.cfg`)
- Use CPython 3.13 to avoid dependency resolution issues
- Earlier versions (3.11+) may work but are not validated

### Entry Point
- `main.py` defines the FastAPI app with `/api/chat` and `/api/teams` routers
- Uses `uvloop` for improved async performance (falls back to standard asyncio if unavailable)
- Local run command: `python main.py` (uses `uvicorn.run` in `__main__`)

### Service Boundaries
1. **Supabase:** `services/supabase_service.py`
   - Encapsulates DB/vector search and message persistence
   - Requires `SUPABASE_URL` and `SUPABASE_KEY` or `SUPABASE_SERVICE_ROLE_KEY`
   - Uses `pgvector` extension for similarity search

2. **Embedding Model:** `services/embedding_service.py`
   - Loads `SentenceTransformer` at import time using `EMBEDDING_MODEL_NAME` (default: `dragonkue/BGE-m3-ko`)
   - **Heavy operation:** Triggers model download on first import (~1GB+)
   - Cache location: `~/.cache/huggingface` and `~/.cache/torch`

3. **Reranker:** `services/reranker_service.py`
   - Uses `dragonkue/bge-reranker-v2-m3-ko` model
   - Warmed up in production mode during app startup
   - Configurable via `RERANKER_CONFIG` in `config.py`

4. **OpenAI:** `services/langchain_rag_service.py` and `services/unified_chat_service.py`
   - Invoke OpenAI models configured via `OPENAI_API_KEY`
   - LangChain integration for RAG pipeline

5. **Microsoft Teams:** `services/teams_service.py` and `routers/teams_router.py`
   - Bot Framework integration
   - Requires `MICROSOFT_APP_ID`, `MICROSOFT_APP_PASSWORD`, `MICROSOFT_TENANT_ID`

6. **Streaming:** `routers/chat_router.py`
   - SSE (Server-Sent Events) streaming endpoint
   - Returns JSON-wrapped tokens: `{"type": "token", "token": "..."}`
   - Special messages: `{"type": "done"}` and `{"type": "error", "error": "..."}`

---

## Configuration

### Configuration Source
`config.py` reads from environment using `python-dotenv`. Key variables:

**Required for operation:**
- `SUPABASE_URL`
- `SUPABASE_KEY` or `SUPABASE_SERVICE_ROLE_KEY`
- `OPENAI_API_KEY`

**Optional with defaults:**
- `EMBEDDING_MODEL_NAME` (default: `dragonkue/BGE-m3-ko`)
- `EMBEDDING_MODEL_DIMENSION` (default: `1024`)
- `SERVER_HOST` (default: `0.0.0.0`)
- `SERVER_PORT` (default: `8000`)
- `TOKENIZERS_PARALLELISM` (default: `"false"`)
- `ENV` (default: `"development"`)
- `LOG_LEVEL` (default: `"INFO"`)
- `ALLOWED_ORIGINS` (default: `"http://localhost:3000,http://localhost:5173"`)
- `GUNICORN_WORKERS` (default: `4`)

**Vector search tuning:**
- `VECTOR_EF_SEARCH` (default: `50`)
- `VECTOR_CHUNK_TOKENS` (default: `400`)
- `VECTOR_OVERLAP_TOKENS` (default: `50`)
- `VECTOR_MIN_CHUNK_TOKENS` (default: `30`)
- `VECTOR_SIMILARITY_THRESHOLD` (default: `0.3`)

**Microsoft Teams (optional):**
- `CONFLUENCE_URL`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_SPACE_KEY`
- `MICROSOFT_APP_ID`, `MICROSOFT_APP_PASSWORD`, `MICROSOFT_TENANT_ID`

### .env Loading
- `load_dotenv()` is called at config.py import time
- Place `.env` file in repository root for local development
- **Never commit credentials** — use secret managers in CI/production

### Minimal Development .env
```env
OPENAI_API_KEY=sk-...your-key...
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_KEY=ey...anon-or-service-role...
TOKENIZERS_PARALLELISM=false
SERVER_HOST=127.0.0.1
SERVER_PORT=8000
ENV=development
LOG_LEVEL=INFO
```

---

## Build and Setup

### Create Virtual Environment
```bash
# Create venv with Python 3.13
python3.13 -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

**Important notes:**
- First install is heavy (~5GB) due to PyTorch, transformers, CUDA libraries
- First import of `embedding_service` will download the embedding model (~1GB+)
- Ensure network access for HuggingFace Hub downloads
- Consider caching `~/.cache/huggingface` and `~/.cache/torch` in CI to reduce build time

### Performance Recommendations
- Set `TOKENIZERS_PARALLELISM=false` to reduce warnings and contention
- In production, model warmup happens automatically during app startup
- uvloop is automatically used if installed (provides ~20-40% async performance boost)

---

## Running the Server

### Development Run
```bash
python main.py
```
- Reload is enabled in development mode (`ENV=development`)
- Logs startup messages with emoji markers (🚀, ✅, ⚠️, ❌)
- Swagger UI available at `http://localhost:8000/docs` (disabled in production)

### Production Run
```bash
# Using Gunicorn (recommended)
gunicorn main:app --config gunicorn.conf.py

# Or with environment variables
ENV=production gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Health Check
```bash
GET http://localhost:8000/api/health
```
Response:
```json
{
  "status": "healthy",
  "message": "API is running"
}
```

### Streaming Chat Endpoint
```bash
POST http://localhost:8000/api/chat/stream
Content-Type: application/json
Authorization: Bearer <supabase-jwt-token>

{
  "query": "Your question here",
  "table_mode": false
}
```

Response format (text/event-stream):
```
 {"type": "token", "token": "안"}

 {"type": "token", "token": "녕"}

 {"type": "token", "token": "하"}

 {"type": "done"}

```

---

## Testing

### Framework
- **Primary:** Python's built-in `unittest` module
- **Not included:** pytest (not in requirements.txt; install separately if needed)

### Test Structure
- Test directory: `test/`
- Existing tests are mostly integration scripts that hit external services
- No comprehensive unit test suite exists yet

### Test Categories

#### 1. Lightweight Unit Tests (Recommended)
Tests that avoid importing heavy services:

**Example:** `test/test_config_defaults.py`
```python
"""
Simple test to verify config.py defaults without importing heavy services.
"""
import unittest

class TestConfigDefaults(unittest.TestCase):
    def test_embedding_defaults(self):
        import config
        self.assertEqual(config.EMBEDDING_MODEL_NAME, "dragonkue/BGE-m3-ko")
        self.assertEqual(config.EMBEDDING_MODEL_DIMENSION, 1024)

if __name__ == "__main__":
    unittest.main()
```

**Run command:**
```bash
python -m unittest test.test_config_defaults -q
```

**Expected output:**
```
..
----------------------------------------------------------------------
Ran 2 tests in 0.012s

OK
```

#### 2. Integration Tests (Slow)
Tests that require external services or load heavy models:

**Examples:**
- `test/test_streaming.py` - Hits live server endpoint with requests
- `test/test_search.py` - Requires Supabase connection
- `test_import.py` - Checks Unicode normalization in Supabase data

**Important:** These tests:
- Require valid credentials in `.env`
- Load embedding models (slow first run)
- Should not run in CI without proper mocking
- Useful for local validation and debugging

### Adding New Tests

#### For Unit Tests (Fast)
1. Place test file in `test/` directory
2. Import only what's needed; avoid `services/embedding_service.py` and `main.py` if possible
3. Mock external dependencies:
   ```python
   from unittest.mock import patch, MagicMock
   
   @patch('services.supabase_service.supabase_service.client')
   def test_something(self, mock_client):
       mock_client.table.return_value.select.return_value.execute.return_value = ...
   ```

#### For Integration Tests (Slow)
1. Mark clearly in docstring that test requires external services
2. Consider environment flag to skip by default:
   ```python
   import os
   from unittest import skipUnless
   
   ENABLE_SLOW = os.getenv("ENABLE_SLOW_TESTS") == "1"
   
   @skipUnless(ENABLE_SLOW, "slow test disabled")
   def test_embedding_smoke(self):
       from services.embedding_service import embedding_service
       vec = embedding_service.embed_text("hello")
       self.assertGreater(len(vec), 0)
   ```

3. Run with flag:
   ```bash
   ENABLE_SLOW_TESTS=1 python -m unittest test.test_my_integration
   ```

### Running All Tests
```bash
# Run all tests in test directory
python -m unittest discover -s test -p "test_*.py" -q

# Run specific test file
python -m unittest test.test_config_defaults -v

# Run with pytest (if installed)
pip install pytest
pytest test/ -v
```

---

## Code Style and Conventions

### Language and Comments
- **Primary language:** Korean (한국어)
- Comments, docstrings, and log messages predominantly in Korean
- Use emoji markers for visual clarity: 🚀, ✅, ⚠️, ❌, 📊, 🔥, 📨, 🌐, ✨

### Python Style
- **Type hints:** Used throughout codebase (`typing.Optional`, `List`, `Dict`, `AsyncGenerator`)
- **Imports:** Grouped logically (stdlib, third-party, local)
- **Indentation:** 4 spaces (standard Python)
- **Line length:** Generally follows PEP 8 (~79-100 characters)

### Naming Conventions
- **Variables/functions:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE` (in `config.py`)
- **Private methods:** Prefix with single underscore `_method_name`

### Service Pattern
Services are implemented as classes with dependency injection:

```python
class MyService:
    def __init__(self, dependency: Optional[SomeDep] = None):
        self.dep = dependency or default_instance
    
    def do_something(self, param: str) -> Dict:
        """Korean docstring explaining the method"""
        # Implementation
        pass

# Singleton instance
my_service = MyService()
```

### Router Pattern
FastAPI routers use dependency injection for auth and services:

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/resource", tags=["resource"])

@router.post("/endpoint")
async def endpoint(
    request_body: Schema,
    user: dict = Depends(verify_supabase_token)
):
    """
    ✨ Korean docstring with emoji
    
    역할:
    - Point 1
    - Point 2
    """
    logger = get_logger(__name__, request_id=generate_request_id())
    logger.info("📨 요청 수신", extra={"param": value})
    # Implementation
```

### Logging Pattern
Structured logging with contextual information:

```python
from logging_config import get_logger, generate_request_id

request_id = generate_request_id()
logger = get_logger(__name__, request_id=request_id, user_id=user_id)

logger.info("📊 메시지", extra={
    "key": "value",
    "count": 123
})

logger.error(f"❌ 오류: {error}", exc_info=True)
```

### Error Handling
- Global exception handler in `main.py` catches all unhandled exceptions
- Returns JSON with status 500: `{"detail": "Internal server error"}`
- Original stack traces are logged but not returned to clients
- Use structured logging for debugging

### Async Patterns
- Async generators for streaming: `async def generate() -> AsyncGenerator[str, None]:`
- Async context managers: `async with session:`
- Prefer `async for` over manual iteration

---

## Architecture Notes

### Import Side Effects
- **⚠️ Warning:** `services/embedding_service.py` loads model at import time
- Importing `main.py` or `services.langchain_rag_service` will trigger model loading
- For lightweight tools/CLIs, avoid these imports or lazy-load the model

### Streaming Output Contract
`routers/chat_router.py` streaming behavior:
- Collects tokens from unified chat service
- Wraps each token in JSON format: `{"type": "token", "token": "..."}`
- Final markers: `{"type": "done"}` or `{"type": "error", "error": "..."}`
- Media type: `text/event-stream`
- Character encoding: UTF-8 (supports Korean)

### CORS Configuration
- Development: `allow_origins=["*"]` (permissive for local dev)
- Production: Restrict via `ALLOWED_ORIGINS` environment variable
- Default allowed: `http://localhost:3000,http://localhost:5173`

### Supabase Integration
- `services/supabase_service.py` is the single integration point
- Vector search uses HNSW index with configurable `ef_search` parameter
- Message history and document chunks stored in PostgreSQL tables
- For debugging search results, add instrumentation to `search_chunks()` method

### Model Downloads
- First run downloads models from HuggingFace Hub
- Cache directories:
  - `~/.cache/huggingface/hub/` - Model weights
  - `~/.cache/torch/` - PyTorch artifacts
- Cache between CI runs to reduce build time
- Download size: ~1-2GB for embedding + reranker models

---

## Development Workflow

### Local Development Setup
1. Clone repository
2. Create virtual environment with Python 3.13
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in credentials
5. Run server: `python main.py`
6. Access Swagger UI: `http://localhost:8000/docs`

### Debugging Tips
1. **Embedding issues:** Check `services/embedding_service.py` and model cache
2. **Search issues:** Add logging to `services/supabase_service.py::search_chunks()`
3. **Streaming issues:** Monitor `routers/chat_router.py` and check JSON formatting
4. **Teams bot issues:** Review `services/teams_service.py` and Microsoft credentials
5. **Unicode/Korean text:** Use `test_import.py` pattern to check NFC normalization

### Git Workflow
- Current changes tracked in `.git/`
- Check modified files: `git status`
- View changes: `git diff`
- **Never commit:** `.env`, `__pycache__/`, `venv/`, model cache

### Docker Deployment
- `Dockerfile` and `docker-compose.yml` available
- Uses Gunicorn with Uvicorn workers
- Configure via environment variables in docker-compose

---

## Troubleshooting

### Model Loading Failures
```
Error: No module named 'sentence_transformers'
```
**Solution:** Ensure all dependencies installed: `pip install -r requirements.txt`

### Supabase Connection Issues
```
⚠️  Supabase 연결 실패
```
**Solution:** 
- Check `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
- Verify network connectivity to Supabase endpoint
- Check Supabase project status and API key permissions

### TOKENIZERS_PARALLELISM Warnings
```
huggingface/tokenizers: The current process just got forked...
```
**Solution:** Set `TOKENIZERS_PARALLELISM=false` in `.env`

### Import Hangs on Model Loading
**Issue:** First import of embedding service takes 30-60 seconds
**Solution:** 
- Normal behavior on first run (downloading model)
- Subsequent runs use cached model
- Consider warmup during app startup in production

### Test Failures
**Issue:** Tests import heavy services and fail
**Solution:** 
- Mock external dependencies with `unittest.mock`
- Avoid importing `services/embedding_service.py` in unit tests
- Use integration test pattern with `ENABLE_SLOW_TESTS` flag

---

## Performance Optimization

### Production Checklist
- ✅ Set `ENV=production`
- ✅ Use Gunicorn with multiple workers (`GUNICORN_WORKERS=4`)
- ✅ Enable uvloop (automatically detected)
- ✅ Cache model weights (`~/.cache/huggingface`)
- ✅ Tune `VECTOR_EF_SEARCH` for accuracy/speed tradeoff
- ✅ Restrict CORS origins via `ALLOWED_ORIGINS`
- ✅ Disable Swagger UI (automatic in production mode)
- ✅ Configure proper logging level (`LOG_LEVEL=WARNING`)

### Vector Search Tuning
- Higher `ef_search` = better accuracy, slower search (default: 50)
- Adjust `similarity_threshold` to filter low-quality matches (default: 0.3)
- Tune `chunk_tokens` for optimal context size (default: 400)

### Memory Management
- Each worker loads its own copy of embedding model (~2GB RAM)
- Limit workers based on available RAM: `workers = (RAM_GB - 2) / 3`
- Monitor with: `psutil` or system tools

---

## Housekeeping

### Before Committing
- Run lightweight tests: `python -m unittest discover -s test -p "test_*.py" -q`
- Check no credentials in code: `git diff | grep -i "api_key\|password\|secret"`
- Ensure `.env` not staged: `git status`
- Format code if using formatter (optional)

### CI/CD Considerations
- Skip integration tests by default
- Cache HuggingFace and PyTorch directories
- Use secret managers for environment variables
- Run with minimal dependencies for pipeline testing
- Consider separate integration test stage with credentials

### Documentation Updates
- Update this file when adding new services or major changes
- Document new environment variables in Configuration section
- Add test examples for new features
- Keep troubleshooting section updated with common issues

---

## Quick Reference

### Common Commands
```bash
# Run server
python main.py

# Run lightweight tests
python -m unittest test.test_config_defaults -q

# Run all tests
python -m unittest discover -s test -p "test_*.py"

# Check config
python -c "import config; print(config.EMBEDDING_MODEL_NAME)"

# Test Supabase connection
python test_import.py

# Production run
ENV=production gunicorn main:app --config gunicorn.conf.py
```

### Key Files
- `main.py` - FastAPI app and startup logic
- `config.py` - Environment configuration
- `requirements.txt` - Python dependencies
- `logging_config.py` - Structured logging setup
- `gunicorn.conf.py` - Production server config
- `.env` - Local environment variables (not committed)

### Important Endpoints
- `GET /api/health` - Health check
- `POST /api/chat/stream` - Web streaming chat (requires auth)
- `POST /api/teams/messages` - Teams bot webhook
- `GET /docs` - Swagger UI (dev only)

---

**Document Version:** 1.0  
**Last Updated:** 2025-12-08  
**Maintainer:** Development Team
