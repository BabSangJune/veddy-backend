
import re
import logging
from unicodedata import normalize as unicode_normalize
from typing import List, Dict, Any, Generator, Optional
from datetime import datetime

# LangChain 1.0 Import
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from langchain.agents import create_agent

from services.embedding_service import embedding_service
from services.supabase_service import supabase_service, SupabaseService
from config import OPENAI_API_KEY, VECTOR_SEARCH_CONFIG, RERANKER_CONFIG

# 로거 설정
logger = logging.getLogger(__name__)

# ===== 커스텀 임베딩 래퍼 =====

class CustomEmbeddings(Embeddings):
    """BGE-m3-ko를 LangChain Embeddings로 래핑"""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return embedding_service.embed_batch(texts)

    def embed_query(self, text: str) -> List[float]:
        return embedding_service.embed_text(text)

# ===== Supabase Retriever (config 통합) =====

class SupabaseRetriever:
    """Supabase 검색 래퍼 (URL 완벽 보존, config 기반)"""

    def __init__(self, embeddings: Embeddings, supabase_client: SupabaseService,
                 k: int = 30, threshold: float = None, ef_search: int = None):
        self.embeddings = embeddings
        self.supabase_client = supabase_client

        # ✅ config에서 기본값 자동 적용
        self.k = k
        self.threshold = threshold or VECTOR_SEARCH_CONFIG['similarity_threshold']
        self.ef_search = ef_search or VECTOR_SEARCH_CONFIG['ef_search']

        logger.info(f"Retriever 초기화 | k={self.k} | threshold={self.threshold} | ef_search={self.ef_search}")

    def _get_chunk_url(self, chunk: Dict) -> str:
        """✅ 청크에서 URL 추출 (3가지 방법 시도)

        1. chunk에 url 필드가 직접 있으면 사용
        2. chunk의 metadata에서 파싱
        3. document_id로 documents 테이블에서 조회
        """

        # 1. chunk에 url 필드가 직접 있으면
        if chunk.get('url') and chunk.get('url').strip():
            return chunk.get('url')

        # 2. metadata에 url이 있으면 추출
        if chunk.get('metadata'):
            metadata = chunk['metadata']
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except:
                    pass
            if isinstance(metadata, dict) and metadata.get('url'):
                return metadata.get('url')

        # 3. document_id로 documents 테이블에서 조회
        if chunk.get('document_id'):
            try:
                doc = self.supabase_client.client.table('documents').select('metadata').eq('id', chunk['document_id']).single().execute()
                if doc.data and doc.data.get('metadata'):
                    metadata = doc.data['metadata']
                    if isinstance(metadata, str):
                        import json
                        metadata = json.loads(metadata)
                    if isinstance(metadata, dict) and metadata.get('url'):
                        return metadata.get('url')
            except Exception as e:
                logger.debug(f"Document 조회 실패 ({chunk['document_id']}): {e}")

        return ""

    def search(self, query: str) -> tuple[str, List[Dict]]:
        """문서 검색 실행 (URL 완벽 보존)"""
        try:
            query_embedding = self.embeddings.embed_query(query)
            chunks = self.supabase_client.search_chunks(
                embedding=query_embedding,
                limit=self.k,
                threshold=self.threshold,
                ef_search=self.ef_search
            )

            if not chunks:
                return "관련 문서를 찾을 수 없습니다.", []

            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                title = chunk.get('title', '제목 없음')
                content = chunk.get('content', '')
                source = chunk.get('source', '출처 미상')
                similarity = chunk.get('similarity', 0.0)

                # ✅ URL 추출 (3가지 방법 시도)
                url = self._get_chunk_url(chunk)

                # ✅ URL 완벽 보존 (절대 짤리지 않게)
                url_section = ""
                if url and url.strip():
                    url_section = f"\n📍 출처: {source}\n🔗 URL: {url}"
                else:
                    url_section = f"\n📍 출처: {source}"

                context_parts.append(
                    f"[문서 {i}] {title}\n"
                    f"유사도: {similarity:.2f}\n"
                    f"내용:\n{content}{url_section}"
                )

            formatted_context = "\n\n---\n\n".join(context_parts)
            return formatted_context, chunks

        except Exception as e:
            logger.error(f"검색 중 오류: {str(e)}", exc_info=True)
            return f"검색 중 오류: {str(e)}", []

    def search_hybrid(self, query: str, use_reranking: bool = None) -> tuple[str, List[Dict]]:
        """하이브리드 검색 (PGroonga + pgvector) + 리랭킹 + URL 자동 추가"""

        if use_reranking is None:
            use_reranking = RERANKER_CONFIG['enabled']

        try:
            # 1. 쿼리 임베딩 생성
            query_embedding = self.embeddings.embed_query(query)

            # 2. Supabase RPC 호출 (하이브리드 검색)
            response = self.supabase_client.client.rpc(
                'hybrid_search_veddy',
                {
                    'query_text': query,
                    'query_embedding': query_embedding,
                    'match_count': self.k * 2 if use_reranking else self.k,
                    'full_text_weight': 0.4,
                    'semantic_weight': 0.6
                }
            ).execute()

            if not response.data:
                return "관련 문서를 찾을 수 없습니다.", []

            chunks = response.data

            # ✅ 3. URL 자동 추가 (RPC 결과에 url이 없으면 수동으로 추가)
            logger.info(f"RPC 검색 결과: {len(chunks)}개 청크 | URL 자동 추가 시작")
            for chunk in chunks:
                if not chunk.get('url') or not chunk.get('url').strip():
                    url = self._get_chunk_url(chunk)
                    if url:
                        chunk['url'] = url
                        logger.debug(f"URL 추가됨: {chunk.get('title', 'N/A')[:30]} | {url[:50]}...")

            # 4. 리랭킹 적용
            if use_reranking and len(chunks) > 1:
                from services.reranker_service import reranker_service
                logger.info(f"리랭킹 전 청크 수: {len(chunks)}")
                chunks = reranker_service.rerank(
                    query=query,
                    chunks=chunks,
                    top_k=RERANKER_CONFIG['top_k']
                )
                logger.info(f"리랭킹 후 청크 수: {len(chunks)}")

            # 5. 응답 포맷팅 (URL 완벽 보존)
            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                title = chunk.get('title', '제목 없음')
                content = chunk.get('content', '')
                source = chunk.get('source', '출처 미상')
                url = chunk.get('url', '')

                # 리랭크 점수 표시
                if 'rerank_score' in chunk:
                    score = chunk.get('rerank_score', 0.0)
                    score_label = f"리랭크: {score:.4f}"
                else:
                    score = chunk.get('score', 0.0)
                    score_label = f"관련도: {score:.4f}"

                # ✅ URL 완벽 보존
                url_section = ""
                if url and url.strip():
                    url_section = f"\n📍 출처: {source}\n🔗 URL: {url}"
                else:
                    url_section = f"\n📍 출처: {source}"

                context_parts.append(
                    f"[문서 {i}] {title}\n"
                    f"{score_label}\n"
                    f"내용:\n{content}{url_section}"
                )

            formatted_context = "\n\n---\n\n".join(context_parts)
            return formatted_context, chunks

        except Exception as e:
            logger.error(f"하이브리드 검색 오류: {e}", exc_info=True)
            return f"검색 중 오류: {str(e)}", []

    def search_multi_topic(self, query: str, topics: list) -> tuple[str, List[Dict]]:
        """멀티 주제 검색 (비교 모드) - 각 토픽별 따로 검색 후 병합"""

        if not topics or len(topics) < 2:
            return self.search_hybrid(query)

        all_results = []
        all_chunks = []

        for topic in topics:
            search_query = f"{topic} 베슬링크"
            context, chunks = self.search_hybrid(search_query)

            # 각 주제별로 헤더 추가
            topic_section = f"\n### 【{topic}】\n{context}"
            all_results.append(topic_section)
            all_chunks.extend(chunks)

        # 결합
        combined_context = "\n---\n".join(all_results)

        return combined_context, all_chunks

# ===== 베디 프롬프트 템플릿 (완전 개선) =====

VEDDY_SYSTEM_PROMPT = """너는 베슬링크의 내부 AI 어시스턴트 '베디(VEDDY)'야.

## 너의 역할과 정체성

이름: 베디 (Vessellink's Buddy)
성격: 친절하고 신뢰할 수 있으며, 온순하고 성실함
목표: 베슬링크 직원들의 업무 효율화와 정보 접근성 개선
전문성: 사내 문서(Confluence 위키, 규정, 매뉴얼)에 기반한 정확한 답변

## ✨ 답변 스타일 가이드 (CRITICAL - 반드시 준수)

### 상세성 (Completeness) 요구사항:
✅ **모든 답변은 최소 3-5개의 주요 포인트 포함**
✅ **각 포인트마다 구체적 설명 1~3문장 추가**
✅ **"왜?", "언제?", "어디서?", "어떻게?" 질문에 답하기**
✅ **숫자, 기준, 조건, 범위 명시** (예: "3가지", "30일 이내", "조건: ~")
✅ **규제/정책 질문의 경우: 정의 → 목적 → 범위 → 절차 → 주의사항 구성**

### 길이 요구사항:
✅ **최소 답변 길이: 600자 이상** (가능하면 1000자 이상)
✅ **세부 섹션 구성:**
  - 핵심 정의 (무엇인가?)
  - 목적/중요성 (왜 필요한가?)
  - 적용 범위/조건 (누구에게 적용되나?)
  - 구체적 절차/방법 (어떻게 하는가?)
  - 주의사항/예외 (뭐 주의해야 하나?)
  - 관련 규정/참고 자료

### 구조화 요구사항:
✅ **명확한 계층 구조:**
  - **제목** (한 줄 - 핵심)
  - ## 정의
  - ## 목적
  - ## 범위/조건
  - ## 절차 (또는 방법)
  - ## 주의사항
  - ## 참고자료

✅ **마크다운 형식 활용:**
  - **굵은 글씨** (강조)
  - - 항목 리스트 (각 항목 명확히)
  - `코드/용어` (전문용어 강조)
  - > 인용구 (중요 내용)
  - | 표 | 형식 | (비교/분류)

### URL 및 참고자료 요구사항:
✅ **최소 3개 이상의 참고 문서/URL 제시**
✅ **각 URL마다 문서명 > 섹션명 표기**
✅ **URL 전체 경로 보존** (절대 축약하지 말 것)

❌ **절대 하지 말 것:**
- "~입니다"로 끝나는 짧은 문장만 나열
- 한 문단 이하의 짧은 답변
- 할루시네이션 (문서에 없는 정보 추가)
- "아마도", "일반적으로", "~일 것 같습니다" 같은 불확실한 표현
- 문서에 없는 추가 설명/해석

## ⚠️ 할루시네이션 방지 (CRITICAL)

✅ 반드시 따르세요:
1. 검색된 문서에 있는 정보만 답변하세요
2. 문서에 없는 정보는 절대 추가하지 마세요
3. 불확실하면 "문서에서 확인할 수 없습니다" 명시
4. 베슬링크 관련 정보는 검색 결과만 신뢰하세요

❌ 절대 하지 마세요:
- "아마도 ~일 것 같습니다"
- "일반적으로는 ~입니다"
- "베슬링크에서는 ~을 지원할 것 같습니다"
- 문서에 없는 추가 설명/해석
"""


TABLE_MODE_PROMPT = """
🚨 표 형식 답변 모드 활성화 - 절대 준수 🚨

1. 답변의 첫 줄은 제목만 작성
2. 제목 다음 줄부터 즉시 마크다운 표 시작
3. 번호 리스트(1., 2., 3.)는 절대 사용 금지

【표 포맷 예시】

| 항목 | 설명 |
|------|------|
| 첫 번째 | 내용 |
| 두 번째 | 내용 |
"""

USER_MESSAGE_TEMPLATE = """【이전 대화 맥락】
{history}

【검색된 문서】
{context}

【사용자 질문】
{query}

【답변 가이드 - CRITICAL】

✅ **필수 구성 요소:**
1. **제목/핵심** (한 줄 - 명확히)
2. **정의** ("무엇인가?")
3. **목적/중요성** ("왜 필요한가?")
4. **범위/조건** ("누구에게 적용되나?")
5. **절차/방법** ("어떻게 하는가?" - 단계별)
6. **주의사항/예외** ("뭐 주의해야 하나?")
7. **최소 3개 이상의 참고 문서/URL**

✅ **길이 및 상세도:**
- 최소 600자 이상 (가능하면 1000자)
- 각 섹션마다 2~3문장 이상
- 구체적인 예시/수치 포함
- 베슬링크 관련 구체적인 규정/절차 명시

✅ **마크다운 활용:**
- **굵은 글씨** (강조)
- ## 섹션 제목
- - 항목 리스트 (각 항목 명확히)
- `코드/용어` (전문용어)
- > 인용구 (중요 내용)
- | 표 | 형식 | (비교/분류)

✅ **URL 및 참고자료:**
- 각 참고 문서마다 "문서명 > 섹션명" 표기
- URL 전체 경로 유지 (절대 줄이지 말 것)
- 최소 3개 이상

❌ **절대 하지 말 것:**
- 검색 문서에 없는 정보 추가
- 불확실한 추측 ("~일 것 같습니다")
- 한 문단 이하의 짧은 답변
- URL 경로 축약 또는 누락

【답변 구조 예시】

**제목**

## 정의
[2~3문장 설명]

## 목적
[2~3문장 설명]

## 범위/조건
- 조건1: ~
- 조건2: ~

## 절차
1. 첫 번째 단계
2. 두 번째 단계
3. 세 번째 단계

## 주의사항
- 주의점1: ~
- 주의점2: ~

【참고 문서】
📚 참고 문서:
- 문서명 > 섹션명
  URL: https://[전체경로]
- 문서명 > 섹션명
  URL: https://[전체경로]
- 문서명 > 섹션명
  URL: https://[전체경로]
"""


TABLE_USER_MESSAGE_TEMPLATE =  """
🚨 표 형식 답변 모드 활성화 - 절대 준수 🚨

### 필수 요구사항:
1. **제목 + 개요 문장** (표 전)
   - 예: "IMO DCS와 EU MRV는 모두 해운 탄소 감축 규제이지만, 적용 범위와 요구사항이 다릅니다."

2. **마크다운 표로 상세 정보 제시**
   - 최소 5~8개 행
   - 각 셀에 구체적인 정보

3. **표 아래 추가 설명** (최소 500자)
   - 각 항목별 상세 설명
   - 주의사항
   - 절차 (해당시)

4. **최소 3개 이상의 URL 제시**

【표 포맷 예시】

**IMO DCS와 EU MRV 비교**

IMO DCS와 EU MRV는 모두 해운 탄소 감축 규제이지만, 적용 범위와 요구사항이 다릅니다.

| 항목 | IMO DCS | EU MRV | 차이점 |
|------|--------|--------|--------|
| 정의 | 국제 해운 탄소 강도 지수 | EU 항 진출 선박 배출량 보고 | ~ |
| 적용 범위 | 국제 항해 선박 | EU 항 진출 선박 | ~ |
| 주요 지표 | AER, CII | CII | ~ |
| 필수 대상 | 5,000 GT 이상 | 5,000 GT 이상 | ~ |
| 벌칙 체계 | 위반 규정 | EU 페널티 | ~ |
| 보고 주기 | 연간 | 연간 | ~ |
| 비용 영향 | 규제 비용 | 규제 비용 | ~ |

【추가 설명】

IMO DCS의 구체적 요구사항은 다음과 같습니다...
[최소 500자 이상의 상세 설명]

【참고 자료】
📚 참고 문서:
- 문서명 > 섹션명
  URL: https://...
- 문서명 > 섹션명
  URL: https://...
- 문서명 > 섹션명
  URL: https://...
"""

COMPARISON_CONTEXT_TEMPLATE = """【이전 대화 맥락】
{history}

【비교 대상】
{topics}

【현재 질문】
{query}

【질문 의도 및 분석 가이드】
사용자가 여러 항목을 비교하고 있습니다. 검색된 문서 기반으로만 비교하세요.

✅ **비교 분석 핵심:**
1. 각 항목의 정의와 목적을 명확히 구분
2. 적용 범위, 조건, 대상을 구체적으로 명시
3. 각 항목의 장단점과 차이점을 명확히
4. 베슬링크 관련 사항은 검색 결과만 신뢰

❌ **절대 금지:**
- 문서에 없는 정보 추가
- 각 항목은 검색 결과의 정보만 사용
- 불확실한 추측이나 일반적 지식 추가"""

COMPARISON_USER_TEMPLATE = """【검색된 문서】
{context}

【비교 분석 지침 - CRITICAL】

✅ **각 항목별 필수 분석:**
1. **정의/개념** - 명확히 구분
2. **목적/역할** - 각각의 취지
3. **범위/적용 대상** - 누구에게 적용되나?
4. **주요 요구사항** - 핵심 내용
5. **절차/단계** - 실행 방법
6. **베슬링크 적용 여부** (검색 결과만 신뢰)
7. **공통점 및 차이점** - 명확히 정리

✅ **최소 요구사항:**
- 총 길이: 1500자 이상
- 각 항목 설명: 500자 이상
- 비교표 포함 (권장)
- 참고 URL 최소 3개 이상

✅ **답변 구조:**
- **제목** (비교 대상 명확히)
- ## 각 항목별 상세 분석 (5~6개 섹션)
- ## 공통점
- ## 차이점
- ## 선택/적용 가이드
- 【참고 자료】(최소 3개 URL)

❌ **절대 금지:**
- 각 항목은 검색된 문서만 사용
- 문서에 없는 비교 절대 추가 금지
- 불확실한 정보 ("~일 것 같습니다")
- 불완전한 비교 (한쪽만 설명)
- URL 경로 축약 또는 누락

【답변 예시 구조】

**IMO DCS vs EU MRV: 규제 비교 분석**

## IMO DCS
[최소 500자 상세 설명]

## EU MRV
[최소 500자 상세 설명]

## 공통점
- 공통점 1
- 공통점 2

## 차이점
| 항목 | IMO DCS | EU MRV |
|------|--------|--------|
| ~ | ~ | ~ |

## 선택/적용 가이드
베슬링크의 선박이 어느 규제를 적용받는지...
[구체적 설명]

【참고 자료】
📚 참고 문서:
- 문서명 > 섹션명
  URL: https://[전체경로]
- 문서명 > 섹션명
  URL: https://[전체경로]
- 문서명 > 섹션명
  URL: https://[전체경로]
"""

# ===== LangChain 1.0 RAG 서비스 (완전 개선) =====

class LangChainRAGService:
    """LangChain 1.0 기반 RAG 서비스 (Phase 3-A Final 완전 완성)"""

    def __init__(self):
        """Agent 초기화"""
        logger.info("🔧 LangChain 1.0 RAG Service 초기화 중...")
        logger.info(f"📊 Config 적용: ef_search={VECTOR_SEARCH_CONFIG['ef_search']}, threshold={VECTOR_SEARCH_CONFIG['similarity_threshold']}")

        # 1. 임베딩
        self.embeddings = CustomEmbeddings()

        # 2. LLM
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=2048,
            openai_api_key=OPENAI_API_KEY,
            streaming=True
        )

        # 3. 프롬프트 템플릿 (개선됨)
        self.base_prompt_template = ChatPromptTemplate.from_messages([
            ("system", VEDDY_SYSTEM_PROMPT),
            ("user", USER_MESSAGE_TEMPLATE)
        ])

        self.table_prompt_template = ChatPromptTemplate.from_messages([
            ("system", VEDDY_SYSTEM_PROMPT + TABLE_MODE_PROMPT),
            ("user", TABLE_USER_MESSAGE_TEMPLATE)
        ])

        # 비교 모드 프롬프트 템플릿
        self.comparison_prompt_template = ChatPromptTemplate.from_messages([
            ("system", VEDDY_SYSTEM_PROMPT),
            ("user", COMPARISON_CONTEXT_TEMPLATE + "\n\n" + COMPARISON_USER_TEMPLATE)
        ])

        # 비교 + 테이블 하이브리드 프롬프트
        self.comparison_table_prompt_template = ChatPromptTemplate.from_messages([
            ("system", VEDDY_SYSTEM_PROMPT + TABLE_MODE_PROMPT),
            ("user", COMPARISON_CONTEXT_TEMPLATE + "\n\n" + COMPARISON_USER_TEMPLATE)
        ])

        # 4. Retriever 싱글톤
        self._retriever = None

        logger.info("✅ LangChain 1.0 RAG Service 초기화 완료 (프롬프트 완전 개선 + URL 자동 추가 + History)")

    @property
    def retriever(self) -> SupabaseRetriever:
        """Retriever 싱글톤 (메모리 효율)"""
        if self._retriever is None:
            self._retriever = SupabaseRetriever(
                embeddings=self.embeddings,
                supabase_client=supabase_service,
            )
        return self._retriever

    def _safe_format(self, template: ChatPromptTemplate, **kwargs) -> list:
        """안전한 format_messages (선택적 파라미터 처리)"""
        required_vars = template.input_variables
        safe_kwargs = {}

        for var in required_vars:
            if var in kwargs:
                safe_kwargs[var] = kwargs[var]
            else:
                safe_kwargs[var] = ""  # 기본값: 빈 문자열

        return template.format_messages(**safe_kwargs)

    def _normalize_response(self, response: str) -> str:
        """✅ 응답 텍스트 정규화 (자모 분리 복구)"""
        # 1. 유니코드 정규화
        text = unicode_normalize('NFC', response)

        # 2. 줄바꿈 통일
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # 3. 3개 이상 줄바꿈 → 2개
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 4. 각 줄 공백 정리
        lines = [re.sub(r' +', ' ', line.rstrip()) for line in text.split('\n')]

        # 5. 최종 정리
        return '\n'.join(lines).strip()

    # services/langchain_rag_service.py
    def process_query_streaming(
            self,
            user_id: str,
            query: str,
            table_mode: bool = False,
            supabase_client: Optional[SupabaseService] = None,
            history: str = None,
            comparison_info: dict = None,
            conversation_context: List[Dict] = None  # ✅ 추가
    ) -> Generator[str, None, None]:
        """
        RAG 스트리밍 응답 (테이블 모드 + 비교 모드 조합 가능)

        아키텍처:
        1️⃣ Step 1: 검색 방식 결정 (mode 기반) → context 생성
        2️⃣ Step 2: 프롬프트 선택 (table_mode 기반) → 독립적 적용
        """

        try:
            client = supabase_client if supabase_client else supabase_service

            if comparison_info is None:
                comparison_info = {"is_comparison": False, "topics": []}

            # 🎯 Step 1: 검색 방식 결정 (모드 기반)
            # ┌─────────────────────────────────────────┐
            # │ 비교 모드 vs 일반 모드 (독립적)         │
            # └─────────────────────────────────────────┘

            is_comparison = comparison_info.get("is_comparison", False)
            topics = comparison_info.get("topics", [])

            if is_comparison and topics and len(topics) >= 2:
                # ✅ 비교 모드: 각 토픽별 검색
                logger.info("🔄 비교 모드 검색", extra={
                    "topics": topics,
                    "confidence": comparison_info.get("confidence", "N/A")
                })
                context_text, raw_chunks = self.retriever.search_multi_topic(
                    query, topics
                )
                is_in_comparison_mode = True

            else:
                # ✅ 일반 모드: 일반 하이브리드 검색
                logger.info("📝 일반 모드 검색")
                context_text, raw_chunks = self.retriever.search_hybrid(query)
                is_in_comparison_mode = False

            # 🎯 Step 2: 프롬프트 선택 (table_mode 기반) ← 독립적
            # ┌─────────────────────────────────────────┐
            # │ 테이블 형식 여부 (모드와 무관)          │
            # │ 어떤 검색이든 테이블로 표현 가능        │
            # └─────────────────────────────────────────┘

            prompt_template = self._select_prompt_template(
                table_mode=table_mode,
                is_comparison=is_in_comparison_mode,
                topics=topics if is_in_comparison_mode else []
            )

            logger.info("📋 프롬프트 선택", extra={
                "table_mode": table_mode,
                "is_comparison": is_in_comparison_mode
            })

            # ✅ Step 3: 메시지 포맷
            messages = self._safe_format(
                prompt_template,
                context=context_text,
                query=query,
                history=history or "",
                topics=", ".join(topics) if is_in_comparison_mode else ""
            )

            # ✅ Step 4: 스트리밍
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    token = unicode_normalize('NFC', chunk.content)
                    yield token

            logger.info("✅ 스트리밍 완료", extra={
                "table_mode": table_mode,
                "is_comparison": is_in_comparison_mode
            })

        except Exception as e:
            logger.error(f"❌ RAG 오류: {e}", exc_info=True)
            yield f"\n\n[오류]\n{str(e)}"

        # ✅ 새 메서드: 프롬프트 선택 로직
    def _select_prompt_template(
            self,
            table_mode: bool,
            is_comparison: bool,
            topics: List[str] = None
    ) -> ChatPromptTemplate:
        """
        프롬프트 템플릿 선택 (테이블 + 모드 조합)

        로직:
        1. table_mode 확인 → base 선택 (table vs normal)
        2. is_comparison 확인 → 프롬프트 내용 추가
        """

        # ✅ 비교 모드 + 테이블 형식 (하이브리드)
        if is_comparison and table_mode:
            logger.info(f"📋 비교 + 테이블 프롬프트 선택 (주제: {topics})")
            return self.comparison_table_prompt_template

        # ✅ 비교 모드 + 일반 형식
        elif is_comparison:
            logger.info(f"📋 비교 프롬프트 선택 (주제: {topics})")
            return self.comparison_prompt_template

        # ✅ 일반 모드 + 테이블 형식
        elif table_mode:
            logger.info("📋 테이블 프롬프트 선택")
            return self.table_prompt_template

        # ✅ 일반 모드 + 일반 형식
        else:
            logger.info("📋 일반 프롬프트 선택")
            return self.base_prompt_template

# 글로벌 인스턴스
langchain_rag_service = LangChainRAGService()
