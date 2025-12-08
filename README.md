# VEDDY Backend

**VEDDY (Vessellink AI Buddy)** - Confluence RAG 기반 AI 채팅 백엔드 & Microsoft Teams 봇

FastAPI 기반의 RAG(Retrieval-Augmented Generation) 시스템으로, Supabase 벡터 검색과 OpenAI GPT 모델을 활용하여 Confluence 문서에 대한 지능형 질의응답을 제공합니다.

---

## 📋 목차

- [주요 기능](#-주요-기능)
- [기술 스택](#-기술-스택)
- [시스템 요구사항](#-시스템-요구사항)
- [설치 및 실행](#-설치-및-실행)
- [환경 변수](#-환경-변수)
- [API 엔드포인트](#-api-엔드포인트)
- [프로젝트 구조](#-프로젝트-구조)
- [테스트](#-테스트)
- [배포](#-배포)
- [문제 해결](#-문제-해결)
- [라이선스](#-라이선스)

---

## ✨ 주요 기능

- **🤖 RAG 기반 AI 채팅**: Confluence 문서 검색 + OpenAI GPT를 활용한 정확한 답변 생성
- **🔍 벡터 검색**: Supabase pgvector 기반 의미론적(Semantic) 문서 검색
- **📊 리랭킹**: BGE Reranker를 활용한 검색 결과 재정렬로 정확도 향상
- **💬 스트리밍 응답**: Server-Sent Events(SSE)를 통한 실시간 토큰 스트리밍
- **🌐 Microsoft Teams 통합**: Teams 봇을 통한 기업 메신저 내 AI 어시스턴트
- **🔐 인증**: Supabase JWT 기반 사용자 인증
- **📈 헬스체크**: 상세한 시스템 상태 모니터링 (DB, 모델, 리소스)

---

## 🛠 기술 스택

### 언어 및 프레임워크
- **Python**: 3.13 (권장)
- **FastAPI**: 0.122.0 - 고성능 비동기 웹 프레임워크
- **Uvicorn**: ASGI 서버 (uvloop 자동 감지로 성능 최적화)
- **Gunicorn**: 프로덕션 멀티워커 서버

### AI/ML 스택
- **OpenAI**: GPT 모델을 활용한 답변 생성
- **LangChain**: 1.0.8 - RAG 파이프라인 구축
- **Sentence-Transformers**: 5.1.2 - 임베딩 모델
  - 기본 모델: `dragonkue/BGE-m3-ko` (한국어 최적화)
  - 차원: 1024
- **FlagEmbedding**: 1.3.5 - 리랭커
  - 모델: `dragonkue/bge-reranker-v2-m3-ko`
- **PyTorch**: 2.9.1 (CUDA 12.8 지원)
- **Transformers**: 4.57.1

### 데이터베이스 및 벡터 검색
- **Supabase**: PostgreSQL + pgvector
  - 벡터 유사도 검색 (HNSW 인덱스)
  - 사용자 인증 및 세션 관리
  - 대화 히스토리 저장

### 통합
- **Microsoft Bot Framework**: Teams 봇 통합
- **Confluence API**: 문서 동기화 및 관리

### 패키지 관리
- **pip**: Python 패키지 관리자
- **requirements.txt**: 의존성 정의

---

## 💻 시스템 요구사항

### 최소 요구사항
- **OS**: Windows / Linux / macOS
- **Python**: 3.13
- **RAM**: 8GB 이상 (권장: 16GB+)
- **Disk**: 10GB 이상 (모델 캐시 포함)
- **네트워크**: HuggingFace Hub 접근 (모델 다운로드)

### 프로덕션 권장사항
- **RAM**: Worker당 3GB (4 workers = 14GB 이상)
- **CPU**: 4 코어 이상
- **GPU**: CUDA 지원 GPU (선택사항, 추론 속도 향상)

### 필수 외부 서비스
- **Supabase** 프로젝트 (PostgreSQL + pgvector)
- **OpenAI** API 키
- **Microsoft Teams** (봇 사용 시)

---

## 🚀 설치 및 실행

### 1. 저장소 클론

```bash
git clone <repository-url>
cd veddy-backend
```

### 2. 가상환경 생성 및 활성화

#### Windows
```bash
python -m venv venv
venv\Scripts\activate
```

#### Linux/macOS
```bash
python -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

**⚠️ 첫 설치 시 유의사항:**
- 전체 설치 크기: ~5GB (PyTorch, CUDA 라이브러리 포함)
- 설치 시간: 네트워크 속도에 따라 5-15분 소요
- 첫 실행 시 임베딩 모델 자동 다운로드 (~1GB+)

### 4. 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```bash
cp .env.example .env  # .env.example이 있는 경우
```

또는 직접 생성 (필수 변수만):

```env
# 필수
OPENAI_API_KEY=sk-your-openai-api-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key

# 기본값 사용 가능 (선택)
ENV=development
LOG_LEVEL=INFO
SERVER_HOST=127.0.0.1
SERVER_PORT=8000
TOKENIZERS_PARALLELISM=false
```

자세한 환경 변수는 [환경 변수](#-환경-변수) 섹션 참조.

### 5. 서버 실행

#### 개발 모드 (자동 리로드)
```bash
python main.py
```

서버 시작 후 접근 가능:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs (개발 모드만)
- **헬스체크**: http://localhost:8000/api/health

#### 프로덕션 모드
```bash
ENV=production gunicorn main:app --config gunicorn.conf.py
```

또는

```bash
ENV=production gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 🔧 환경 변수

### 필수 환경 변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API 키 | `sk-...` |
| `SUPABASE_URL` | Supabase 프로젝트 URL | `https://xxx.supabase.co` |
| `SUPABASE_KEY` | Supabase anon/service key | `eyJ...` |

### 서버 설정

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `ENV` | `development` | 실행 환경 (`development` / `production`) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 (`DEBUG` / `INFO` / `WARNING` / `ERROR`) |
| `SERVER_HOST` | `0.0.0.0` | 서버 바인딩 호스트 |
| `SERVER_PORT` | `8000` | 서버 포트 |
| `GUNICORN_WORKERS` | `4` | Gunicorn 워커 수 |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` | CORS 허용 오리진 (콤마 구분) |

### 임베딩 모델 설정

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `EMBEDDING_MODEL_NAME` | `dragonkue/BGE-m3-ko` | HuggingFace 모델 이름 |
| `EMBEDDING_MODEL_DIMENSION` | `1024` | 임베딩 벡터 차원 |
| `TOKENIZERS_PARALLELISM` | `false` | 토크나이저 병렬 처리 (경고 방지) |

### 벡터 검색 튜닝

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `VECTOR_EF_SEARCH` | `50` | HNSW ef_search 파라미터 (↑ 정확도, ↓ 속도) |
| `VECTOR_CHUNK_TOKENS` | `400` | 문서 청크 크기 (토큰) |
| `VECTOR_OVERLAP_TOKENS` | `50` | 청크 오버랩 크기 (토큰) |
| `VECTOR_MIN_CHUNK_TOKENS` | `30` | 최소 청크 크기 (토큰) |
| `VECTOR_SIMILARITY_THRESHOLD` | `0.3` | 유사도 임계값 (낮은 값 필터링) |

### Microsoft Teams 설정 (선택)

| 변수명 | 설명 |
|--------|------|
| `MICROSOFT_APP_ID` | Teams 봇 앱 ID |
| `MICROSOFT_APP_PASSWORD` | Teams 봇 앱 비밀번호 |
| `MICROSOFT_TENANT_ID` | Microsoft 테넌트 ID |

### Confluence 설정 (선택)

| 변수명 | 설명 |
|--------|------|
| `CONFLUENCE_URL` | Confluence 인스턴스 URL |
| `CONFLUENCE_API_TOKEN` | Confluence API 토큰 |
| `CONFLUENCE_SPACE_KEY` | Confluence 스페이스 키 |

---

## 📡 API 엔드포인트

### 헬스체크

#### `GET /api/health`
시스템 상태 확인 (DB, 모델, 리소스)

**응답 예시:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-08T00:00:00",
  "environment": "development",
  "checks": {
    "database": {"status": "up", "type": "supabase"},
    "embedding_model": {"status": "up", "model": "BGE-m3-ko", "dimension": 1024},
    "teams_bot": {"status": "configured"},
    "system": {
      "memory": {"total_gb": 16, "used_gb": 8, "available_gb": 8, "percent": 50},
      "cpu_percent": 15.2
    }
  }
}
```

### 채팅 API

#### `POST /api/chat/stream`
웹 채팅 스트리밍 엔드포인트

**인증:** Bearer Token (Supabase JWT)

**요청:**
```json
{
  "query": "질문 내용",
  "table_mode": false
}
```

**응답:** Server-Sent Events (SSE)
```
data: {"type": "token", "token": "안"}

data: {"type": "token", "token": "녕"}

data: {"type": "token", "token": "하"}

data: {"type": "done"}
```

### Teams 봇

#### `POST /api/teams/messages`
Microsoft Teams 메시지 웹훅

#### `GET /api/teams/health`
Teams 봇 상태 확인

### 테스트 엔드포인트 (개발 모드)

- `GET /api/test-embedding?text=테스트` - 임베딩 테스트
- `GET /api/test-supabase` - Supabase 연결 테스트
- `GET /api/test-teams` - Teams 봇 테스트

---

## 📁 프로젝트 구조

```
veddy-backend/
├── main.py                     # FastAPI 앱 엔트리 포인트
├── config.py                   # 환경 설정 및 변수
├── logging_config.py           # 구조화된 로깅 설정
├── gunicorn.conf.py           # Gunicorn 서버 설정
├── requirements.txt           # Python 의존성
├── Dockerfile                 # Docker 이미지 빌드
├── docker-compose.yml         # Docker Compose 설정
├── .env                       # 환경 변수 (gitignore)
│
├── auth/                      # 인증 모듈
│   ├── auth_service.py       # Supabase JWT 인증
│   └── user_service.py       # 사용자 서비스
│
├── model/                     # 데이터 모델
│   └── schemas.py            # Pydantic 스키마
│
├── routers/                   # API 라우터
│   ├── chat_router.py        # 웹 채팅 엔드포인트
│   └── teams_router.py       # Teams 봇 엔드포인트
│
├── services/                  # 비즈니스 로직
│   ├── embedding_service.py   # 임베딩 모델 서비스
│   ├── reranker_service.py    # 리랭커 서비스
│   ├── supabase_service.py    # Supabase 클라이언트
│   ├── langchain_rag_service.py # RAG 파이프라인
│   ├── unified_chat_service.py  # 통합 채팅 로직
│   ├── teams_service.py       # Teams 봇 서비스
│   ├── confluence_service.py  # Confluence API
│   ├── history_service.py     # 대화 히스토리
│   └── token_chunk_service.py # 토큰 기반 청킹
│
├── test/                      # 테스트
│   ├── test_search.py        # 검색 테스트
│   ├── test_streaming.py     # 스트리밍 테스트
│   └── benchmark_*.py        # 벤치마크
│
└── backup/                    # 백업 코드
```

---

## 🧪 테스트

### 단위 테스트 실행

```bash
# 전체 테스트 실행
python -m unittest discover -s test -p "test_*.py"

# 특정 테스트 실행
python -m unittest test.test_search -v
```

### 수동 테스트

#### 임베딩 테스트
```bash
curl "http://localhost:8000/api/test-embedding?text=테스트"
```

#### Supabase 연결 테스트
```bash
curl http://localhost:8000/api/test-supabase
```

#### 헬스체크
```bash
curl http://localhost:8000/api/health
```

### 통합 테스트

통합 테스트는 외부 서비스(Supabase, OpenAI)가 필요하며, `.env` 파일에 유효한 자격증명이 설정되어 있어야 합니다.

```bash
# 검색 기능 테스트
python test/test_search.py

# 스트리밍 테스트
python test/test_streaming.py
```

---

## 🐳 배포

### Docker로 빌드 및 실행

#### 1. 이미지 빌드
```bash
docker build -t veddy-backend:latest .
```

#### 2. 컨테이너 실행
```bash
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name veddy-backend \
  veddy-backend:latest
```

#### 3. 로그 확인
```bash
docker logs -f veddy-backend
```

### Docker Compose

```bash
# 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 중지
docker-compose down
```

### Azure Container Apps (예시)

기존 README에서 발견된 Azure 배포 명령어:

```bash
# 1. ACR 로그인
az acr login --name acrveddyprod

# 2. 이미지 태그
docker tag veddy-backend:latest acrveddyprod.azurecr.io/veddy-backend:v20251208-0001

# 3. 이미지 푸시
docker push acrveddyprod.azurecr.io/veddy-backend:latest

# 4. Container App 업데이트
az containerapp update \
  --name ca-veddy-backend \
  --resource-group VESSELLINK_BOT_RESOURCE \
  --image acrveddyprod.azurecr.io/veddy-backend:latest

# 5. 로그 확인
az containerapp logs show \
  --name ca-veddy-backend \
  --resource-group VESSELLINK_BOT_RESOURCE \
  --follow
```

---

## 🔍 문제 해결

### 모델 로딩 실패

**증상:**
```
Error: No module named 'sentence_transformers'
```

**해결:**
```bash
pip install -r requirements.txt
```

### Supabase 연결 실패

**증상:**
```
⚠️  Supabase 연결 실패
```

**해결:**
1. `.env` 파일의 `SUPABASE_URL`과 `SUPABASE_KEY` 확인
2. Supabase 프로젝트 상태 확인
3. 네트워크 연결 확인
4. API 키 권한 확인 (anon key 또는 service_role key)

### TOKENIZERS_PARALLELISM 경고

**증상:**
```
huggingface/tokenizers: The current process just got forked...
```

**해결:**
`.env` 파일에 추가:
```env
TOKENIZERS_PARALLELISM=false
```

### 첫 실행 시 느린 시작

**증상:** 첫 실행 시 30-60초 대기

**원인:** 임베딩 모델 다운로드 (정상 동작)

**해결:**
- 이후 실행은 캐시된 모델 사용으로 빠름
- 프로덕션 환경: `ENV=production` 설정 시 앱 시작 시 자동 워밍업
- 캐시 위치: `~/.cache/huggingface`, `~/.cache/torch`

### 메모리 부족

**증상:** Worker가 종료되거나 OOM 오류

**해결:**
1. Worker 수 줄이기: `GUNICORN_WORKERS=2`
2. 권장 RAM: Worker당 3GB (4 workers = 14GB+)
3. 시스템 메모리 확인: `/api/health` 엔드포인트

### 테스트 실패

**증상:** 테스트 실행 시 ImportError 또는 타임아웃

**해결:**
1. 외부 서비스 필요한 테스트는 `.env` 설정 확인
2. 모킹 사용: `unittest.mock`으로 외부 의존성 제거
3. 통합 테스트는 수동 실행 권장

---

## 📄 라이선스

TODO: 라이선스 정보 추가 필요

---

## 📚 추가 문서

자세한 개발 가이드는 `.junie/guidelines.md` 참조:
- 코드 스타일 및 규칙
- 서비스 아키텍처
- 성능 최적화 팁
- CI/CD 고려사항

---

## 🤝 기여

TODO: 기여 가이드라인 추가 필요

---

## 📞 지원

TODO: 연락처 또는 이슈 트래커 정보 추가 필요

---

**버전:** 0.2.0  
**최종 업데이트:** 2025-12-08
