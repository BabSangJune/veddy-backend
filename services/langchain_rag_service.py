# backend/services/langchain_rag_service.py (✅ 최종 수정 - 저장 제거, 반환만)

import re
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
from config import OPENAI_API_KEY

# ===== 커스텀 임베딩 래퍼 =====

class CustomEmbeddings(Embeddings):
    """BGE-m3-ko를 LangChain Embeddings로 래핑"""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return embedding_service.embed_batch(texts)

    def embed_query(self, text: str) -> List[float]:
        return embedding_service.embed_text(text)

# ===== Supabase Retriever =====

class SupabaseRetriever:
    """Supabase 검색 래퍼 (URL 포함)"""

    def __init__(self, embeddings: Embeddings, supabase_client: SupabaseService, k: int = 5, threshold: float = 0.3):
        self.embeddings = embeddings
        self.supabase_client = supabase_client
        self.k = k
        self.threshold = threshold

    def search(self, query: str) -> tuple[str, List[Dict]]:
        """문서 검색 실행 (URL 완벽 보존)"""
        try:
            query_embedding = self.embeddings.embed_query(query)
            chunks = self.supabase_client.search_chunks(
                embedding=query_embedding,
                limit=self.k,
                threshold=self.threshold
            )

            if not chunks:
                return "관련 문서를 찾을 수 없습니다.", []

            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                title = chunk.get('title', '제목 없음')
                content = chunk.get('content', '')
                source = chunk.get('source', '출처 미상')
                url = chunk.get('url', '')
                similarity = chunk.get('similarity', 0.0)

                # ✅ URL 보존 (절대 삭제 금지)
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
            return f"검색 중 오류: {str(e)}", []

# ===== 베디 프롬프트 템플릿 (동일) =====

VEDDY_SYSTEM_PROMPT = """너는 베슬링크의 내부 AI 어시스턴트 '베디(VEDDY)'야.

## 너의 역할과 정체성

이름: 베디 (Vessellink's Buddy)

성격: 친절하고 신뢰할 수 있으며, 온순하고 성실함

목표: 베슬링크 직원들의 업무 효율화와 정보 접근성 개선

전문성: 사내 문서(Confluence 위키, 규정, 매뉴얼)에 기반한 정확한 답변

## 답변 포맷 규칙 (반드시 준수)

✅ 필수 포맷:

1. **제목 (1줄)**
2. **빈 줄**
3. **본문 (번호 리스트)**
각 번호는 반드시 새로운 줄에서 시작하세요.
각 번호 사이에는 빈 줄 1줄을 반드시 추가하세요.
4. **참고 문서 섹션**

📚 참고 문서:

- 문서명 > (섹션명)
URL: https://...

혹시 더 궁금한 점이 있으신가요?
"""

TABLE_MODE_PROMPT = """
🚨 표 형식 답변 모드 활성화 - 절대 준수 🚨

**사용자가 표 모드를 활성화했습니다. 다음 규칙을 반드시 따르세요:**

1. 답변의 첫 줄은 제목만 작성
2. 제목 다음 줄부터 즉시 마크다운 표 시작
3. 번호 리스트(1., 2., 3.)는 절대 사용 금지

| 항목 | 설명 |
|------|------|
| 값1 | 내용1 |
"""

USER_MESSAGE_TEMPLATE = """아래 검색된 문서를 기반으로 질문에 정확하게 답변해 주세요.

【검색된 문서】

{context}

【사용자 질문】

{query}

【답변 작성 지침 - 매우 중요!】

1. 반드시 위의 "답변 포맷 규칙"을 따라 작성하세요
2. 제목은 한 줄로만 작성하세요
3. 제목 다음에는 반드시 빈 줄(개행)을 추가하세요
4. 본문은 번호 리스트(1., 2., 3., ...)로 구성하세요
5. 각 번호는 반드시 새로운 줄에서 시작하세요"""

TABLE_USER_MESSAGE_TEMPLATE = """아래 검색된 문서를 기반으로 질문에 답변하세요.

【검색된 문서】

{context}

【사용자 질문】

{query}

【‼️ 표 형식 답변 필수】

반드시 마크다운 표 형식으로 답변하세요."""

# ===== LangChain 1.0 RAG 서비스 (✅ 메시지 저장 제거 - 반환만) =====

class LangChainRAGService:
    """LangChain 1.0 기반 RAG 서비스 (베디 프롬프트 적용)"""

    def __init__(self):
        """Agent 초기화"""
        print("🔧 LangChain 1.0 RAG Service 초기화 중...")

        # 1. 임베딩
        self.embeddings = CustomEmbeddings()

        # 2. LLM (개선된 설정)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=OPENAI_API_KEY,
            streaming=True
        )

        # 3. 프롬프트 템플릿
        self.base_prompt_template = ChatPromptTemplate.from_messages([
            ("system", VEDDY_SYSTEM_PROMPT),
            ("user", USER_MESSAGE_TEMPLATE)
        ])

        self.table_prompt_template = ChatPromptTemplate.from_messages([
            ("system", VEDDY_SYSTEM_PROMPT + TABLE_MODE_PROMPT),
            ("user", TABLE_USER_MESSAGE_TEMPLATE)
        ])

        print("✅ LangChain 1.0 RAG Service 초기화 완료")

    def _normalize_response(self, response: str) -> str:
        """✅ 응답 텍스트 정규화 (자모 분리 복구)"""
        import re
        from unicodedata import normalize as unicode_normalize

        # 1. ✅ 유니코드 정규화 (가장 중요!)
        text = unicode_normalize('NFC', response)

        # 2. 줄바꿈 통일
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')

        # 3. 3개 이상 줄바꿈 → 2개
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 4. 각 줄 공백 정리
        lines = []
        for line in text.split('\n'):
            stripped = line.rstrip()
            stripped = re.sub(r' +', ' ', stripped)
            lines.append(stripped)
        text = '\n'.join(lines)

        # 5. 최종 정리
        return text.strip()

    def process_query(
            self,
            user_id: str,
            query: str,
            table_mode: bool = False,
            supabase_client: Optional[SupabaseService] = None
    ) -> Dict[str, Any]:
        """RAG 쿼리 처리 (일반 응답) - ✅ 저장 제거, 반환만"""
        try:
            # ✅ 클라이언트 선택: 전달된 것이 있으면 사용, 없으면 글로벌 사용
            client = supabase_client if supabase_client else supabase_service

            # 1. Retriever 생성 (사용자 클라이언트 사용)
            retriever = SupabaseRetriever(
                embeddings=self.embeddings,
                supabase_client=client,
                k=5,
                threshold=0.3
            )

            # 2. 문서 검색
            context_text, raw_chunks = retriever.search(query)

            # 3. 프롬프트 선택
            prompt_template = self.table_prompt_template if table_mode else self.base_prompt_template

            # 4. 메시지 생성
            messages = prompt_template.format_messages(
                context=context_text,
                query=query
            )

            # 5. LLM 호출
            response = self.llm.invoke(messages)
            ai_response = response.content

            # ✅ 6. 응답 정규화
            ai_response = self._normalize_response(ai_response)

            # 7. 소스 ID 추출
            source_chunk_ids = [
                chunk.get('id') for chunk in raw_chunks
                if chunk.get('id')
            ]

            # ❌ 메시지 저장 제거! (라우터에서 저장)

            return {
                "user_query": query,
                "ai_response": ai_response,
                "source_chunks": raw_chunks,
                "source_chunk_ids": source_chunk_ids,
                "usage": {}
            }

        except Exception as e:
            print(f"❌ RAG 처리 중 오류: {e}")
            raise

    def process_query_streaming(
            self,
            user_id: str,
            query: str,
            table_mode: bool = False,
            supabase_client: Optional[SupabaseService] = None
    ) -> Generator[str, None, None]:
        """RAG 스트리밍 응답 - ✅ 저장 제거, 반환만"""
        try:
            # ✅ 클라이언트 선택
            client = supabase_client if supabase_client else supabase_service

            # 1. Retriever 생성
            retriever = SupabaseRetriever(
                embeddings=self.embeddings,
                supabase_client=client,
                k=5,
                threshold=0.3
            )

            # 2. 문서 검색
            context_text, raw_chunks = retriever.search(query)

            # 3. 프롬프트 선택
            prompt_template = self.table_prompt_template if table_mode else self.base_prompt_template

            print(f"[RAG] table_mode: {table_mode}")
            if table_mode:
                print(f"[RAG] 표 모드 프롬프트 사용 중")

            # 4. 메시지 생성
            messages = prompt_template.format_messages(
                context=context_text,
                query=query
            )

            # 5. 스트리밍 LLM 호출
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    token = chunk.content
                    # ✅ 각 토큰 정규화
                    normalized_token = unicode_normalize('NFC', token)
                    yield normalized_token

            # ❌ 메시지 저장 제거! (라우터에서 저장)

        except Exception as e:
            print(f"❌ 스트리밍 중 오류: {e}")
            yield f"\n\n[오류 발생]\n{str(e)}"

# 글로벌 인스턴스
langchain_rag_service = LangChainRAGService()
