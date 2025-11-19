Project guidelines for advanced contributors

Scope
- This document captures project-specific knowledge to speed up development, testing, and debugging for this FastAPI-based RAG backend.
- Audience: advanced developers. Assumes familiarity with Python packaging, FastAPI, and vector/RAG systems.

Environment and runtime
- Python: The repo includes pyvenv.cfg indicating Python 3.14. Use CPython 3.14 to avoid subtle dependency resolution issues. Earlier 3.11+ may work but is not validated here.
- Entry point: main.py defines a FastAPI app and includes the /api/chat router. Uvicorn command for local run: python main.py (uses uvicorn.run in __main__).
- Service boundaries:
  - Supabase: services/supabase_service.py encapsulates DB/vector search and message persistence. Requires SUPABASE_URL and a key.
  - Embedding model: services/embedding_service.py loads SentenceTransformer at import time using EMBEDDING_MODEL_NAME (default dragonkue/BGE-m3-ko). This is heavy and triggers a model download on first import.
  - OpenAI: services/rag_custom_service.py and services/langchain_rag_service.py invoke OpenAI models, configured via OPENAI_API_KEY.
  - Streaming: routers/chat.py implements a token stream endpoint with additional formatting and throttling.

Configuration
- Configuration source: config.py reads from environment using python-dotenv. The following keys are recognized:
  - SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY
  - OPENAI_API_KEY
  - EMBEDDING_MODEL_NAME (default: dragonkue/BGE-m3-ko)
  - EMBEDDING_MODEL_DIMENSION (default: 1024)
  - SERVER_HOST (default: 0.0.0.0), SERVER_PORT (default: 8000)
  - CONFLUENCE_URL, CONFLUENCE_API_TOKEN, CONFLUENCE_SPACE_KEY
  - TOKENIZERS_PARALLELISM (default: "false")
- .env loading: load_dotenv() is called at import. Place a .env file in the repository root for local development.
- Minimal dev .env example:
  OPENAI_API_KEY=sk-...your-key...
  SUPABASE_URL=https://<your-project>.supabase.co
  SUPABASE_KEY=ey...anon-or-service-role...
  TOKENIZERS_PARALLELISM=false
  SERVER_HOST=127.0.0.1
  SERVER_PORT=8000

Build and setup
- Create and activate a virtual environment with Python 3.14.
  python3.14 -m venv .venv
  source .venv/bin/activate
- Install dependencies. requirements.txt pins a large stack including torch/transformers; first install will be heavy.
  pip install -r requirements.txt
- Optional performance notes:
  - First load of SentenceTransformer will download the model named by EMBEDDING_MODEL_NAME; ensure network access.
  - TOKENIZERS_PARALLELISM=false is recommended to reduce tokenizer warnings and contention.

Running the server
- Development run (reload enabled inside main.py __main__):
  python main.py
- Health check:
  GET http://localhost:8000/api/health -> {"status": "healthy", "message": "..."}
- Streaming chat endpoint:
  POST http://localhost:8000/api/chat/stream with JSON body {"user_id": "<uuid>", "query": "..."}
  - Response is an SSE-like text/event-stream. routers/chat.py intentionally formats content by inserting newlines, headings spacing, and a trailing "📚 참고 문서:" section if absent.

Testing
- Frameworks available: There is an existing test/ directory with a mix of scripts and utilities. Some of these are not pure unit tests; several hit external services (Supabase/OpenAI) and load the full embedding model.
- Recommended approach for CI/unit testing:
  - Prefer lightweight tests that do not import services/embedding_service.py or anything that triggers the heavy model load unless explicitly needed. Importing main.py or rag services will load models and attempt network calls.
  - For FastAPI endpoints, use TestClient inside tests to import the app object without instantiating the embedding model. If you need to import main.app, ensure tests do not access services that force model import during import time. Alternatively, structure tests to import routers only.
- Running tests with unittest (verified):
  - A demonstration test was created and executed locally using the built-in unittest runner:
    python -m unittest test.test_config_defaults -q
    Output observed:
    Ran 2 tests in 0.012s
    OK
  - This test validates config.py defaults and avoids heavy imports.
- Running tests with pytest:
  - pytest is not currently listed in requirements.txt. If you prefer pytest, install it explicitly:
    pip install pytest
    pytest -q
  - Note: On the authoring machine, pytest was not present by default, so unittest was used to validate the example.
- Adding new tests:
  - Place tests under test/ with either unittest-style classes or pytest functions.
  - Keep unit tests fast by mocking:
    - Mock OpenAI calls in services/rag_custom_service.py.
    - Mock Supabase interactions in services/supabase_service.py.
    - Avoid importing services/embedding_service.py unless you explicitly mark the test as integration/slow.
  - For integration tests that need vector search, prepare a dedicated Supabase project or a mock layer. Do not run against production keys.

Example lightweight test template (unittest)
  # file: test/test_health_endpoint.py
  import unittest
  from fastapi.testclient import TestClient
  import importlib

  class TestHealth(unittest.TestCase):
      def test_health(self):
          app_mod = importlib.import_module("main")
          client = TestClient(app_mod.app)
          r = client.get("/api/health")
          self.assertEqual(r.status_code, 200)
          self.assertEqual(r.json().get("status"), "healthy")

  if __name__ == "__main__":
      unittest.main()

Run with:
  python -m unittest test.test_health_endpoint -q

Adding and running a slow test (optional)
- If you need to test embedding behavior, structure it to skip by default unless an env flag ENABLE_SLOW_TESTS=1 is set, e.g.:
  import os, unittest
  from unittest import skipUnless
  ENABLE_SLOW = os.getenv("ENABLE_SLOW_TESTS") == "1"

  @skipUnless(ENABLE_SLOW, "slow test disabled")
  def test_embedding_smoke(self):
      from services.embedding_service import embedding_service
      vec = embedding_service.embed_text("hello")
      self.assertIsInstance(vec, list)
      self.assertGreater(len(vec), 0)

Coding and development notes
- Import side effects: Avoid importing services.embedding_service in modules executed at import time for tools/CLI/scripts that should remain lightweight. Consider lazy-loading the model if you refactor.
- Streaming output contract: routers/chat.py collects the full LLM stream, applies regex-based formatting, and then yields character by character with slight delays. This design implies:
  - SSE consumers should treat each character as a separate event and buffer client-side.
  - Final markers: " [DONE]\n\n" and error format " [ERROR] ...\n\n" are emitted; clients should handle both.
  - The formatter adds list/heading newlines and a "📚 참고 문서:" section if missing; adjust client rendering accordingly.
- CORS: Wide-open for development (allow_origins=["*"]). Tighten in production.
- Error handling: main.py registers a global exception handler that wraps any error as status=500 JSON. Be mindful when debugging—original stack traces are not returned to clients.
- Logging: routers/chat.py uses logging.getLogger(__name__). Ensure logging is configured by the app/runner if you depend on log output. For local dev, running via python main.py is sufficient to see prints and logs.

Supabase/debugging tips
- The test_import.py script demonstrates a quick content normalization check against the document_chunks table. Use it as a reference for data integrity checks.
- services/supabase_service.py is the integration point for vector search and persistence; prefer adding instrumentation there when diagnosing search results.

Reproducibility notes
- To reproduce the verified test run from above (unittest-based):
  1) Create and activate venv; install requirements.
  2) Ensure no overriding environment variables for SERVER_HOST/PORT/TOKENIZERS_PARALLELISM are set.
  3) Run: python -m unittest test.test_config_defaults -q
  Expected: 2 tests pass quickly without downloading models.

Housekeeping
- Keep heavy, integration-style tests either skipped by default or placed under a separate marker/folder.
- Do not commit credentials. Use .env locally and secret managers in CI.
- Model downloads can be cached between CI runs to reduce build time (e.g., cache ~/.cache/huggingface and ~/.cache/torch).
