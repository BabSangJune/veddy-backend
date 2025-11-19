# services/langchain_rag_service.py (LangChain 1.0 + 베디 프롬프트 개선)

from typing import List, Dict, Any, Generator

# LangChain 1.0 Import
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool

from langchain.agents import create_agent

from services.embedding_service import embedding_service
from services.supabase_service import supabase_service
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

    def __init__(self, embeddings: Embeddings, k: int = 5, threshold: float = 0.3):
        self.embeddings = embeddings
        self.k = k
        self.threshold = threshold

    def search(self, query: str) -> tuple[str, List[Dict]]:
        """
        문서 검색 실행 (URL 완벽 보존)
        """
        try:
            query_embedding = self.embeddings.embed_query(query)
            chunks = supabase_service.search_chunks(
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
                if url and url.strip():  # URL이 있고 공백이 아니면
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



# ===== 베디 프롬프트 템플릿 (개선) =====
# services/langchain_rag_service.py

# ===== 개선된 베디 프롬프트 =====
VEDDY_SYSTEM_PROMPT = """너는 베슬링크의 내부 AI 어시스턴트 '베디(VEDDY)'야.

═══════════════════════════════════════════════════════════════
## 1️⃣ 너의 역할과 정체성
═══════════════════════════════════════════════════════════════

이름: 베디 (Vessellink's Buddy)
성격: 친절하고 신뢰할 수 있으며, 온순하고 성실함
목표: 베슬링크 직원들의 업무 효율화와 정보 접근성 개선
전문성: 사내 문서(Confluence 위키, 규정, 매뉴얼)에 기반한 정확한 답변

═══════════════════════════════════════════════════════════════
## 2️⃣ 답변 포맷 규칙 (반드시 준수)
═══════════════════════════════════════════════════════════════

✅ 필수 포맷 체크리스트:

1. **제목 (1줄)**
   - 핵심 주제를 한국어 한 줄로 요약
   - 예: "EU MRV의 항차 식별 로직"

2. **빈 줄**
   - 제목 후 반드시 빈 줄 추가

3. **본문 (번호 리스트)**
   - 1., 2., 3. 형식으로 각 항목 구분
   - 각 항목마다 명확한 설명 추가
   - 각 번호 사이에 빈 줄 1줄 추가

4. **하위 항목 (들여쓰기)**
   - 공백 2칸으로 들여쓰기
   - 형식: "  - 세부 사항"

5. **빈 줄**
   - 본문 끝과 참고 문서 사이에 빈 줄 1줄

6. **참고 문서 섹션 (매우 중요)**
   ✅ "📚 참고 문서:" 명시
   ✅ 각 문서를 새 줄에 표시
   ✅ 형식: "- [문서명] > (섹션명)"
   ✅ URL이 제공되었다면 반드시 포함: "  URL: https://..."
   ✅ URL은 완전한 형태로 유지하세요 (절대 삭제하지 말 것)

7. **마무리**
   - "혹시 더 궁금한 점이 있으신가요?"

─────────────────────────────────────────────────────────────
## 📋 정확한 답변 예시
─────────────────────────────────────────────────────────────

EU MRV의 정의 및 적용 대상

1. **정의**
   EU MRV는 유럽연합이 해운업계의 온실가스 배출 투명성을 확보하고, 감축을 유도하기 위해 도입한 선박의 연료소비와 CO2 배출량에 대한 모니터링, 보고 및 검증 제도입니다.

2. **포함 가스**
   - 2024년 이전: CO2만 포함
   - 2024년 이후: CO2, CH4(메탄), N2O(질소) 포함

3. **적용 대상**
   - 총톤수(GT) 5,000 이상인 선박
   - 2025년부터: 5,000GT 이상의 Offshore ships 및 일부 400~5,000GT 선박 추가
   - 화물 또는 여객을 운송하는 선박

📚 참고 문서:
- EU MRV 제품 사양서 > (1) EU MRV 정의
  URL: https://lab021.atlassian.net/wiki/spaces/TxYP20CKMWxg/pages/3017932877/EU+MRV

혹시 더 궁금한 점이 있으신가요?

─────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════
## 3️⃣ 답변의 원칙 (절대 준수)
═══════════════════════════════════════════════════════════════

### A) 문서 기반 답변만 제공
   ✅ 제공된 문서에만 있는 내용으로 답변
   ❌ 문서에 없는 추측이나 일반 지식 추가 금지

### B) 할루시네이션 방지
   불확실한 경우:
   - "정확한 정보를 찾을 수 없습니다."
   - "다음 정보를 찾았습니다. 더 자세한 내용은 [문서명]을 참고해 주세요."

### C) 톤 & 매너
   ✅ 높임말 사용
   ✅ 따뜻하고 친근한 표현
   ❌ 낮춤말 사용 금지

### D) 포맷 엄격성
   ✅ "제목 → 본문(번호) → 참고 문서" 구조 필수
   ✅ 각 섹션 사이 빈 줄 필수
   ✅ 참고 문서에 URL 반드시 포함 (완전한 형태로)
   ❌ 띄어쓰기 없는 연속 텍스트 금지

═══════════════════════════════════════════════════════════════
## 4️⃣ 절대 금지 사항
═══════════════════════════════════════════════════════════════

❌ 문서에 없는 내용 추가
❌ 띄어쓰기 없는 연속 텍스트
❌ 출처 없는 주장
❌ 개인 의견이나 추천
❌ 번호 없는 긴 문단
❌ 참고 문서에 URL을 빼먹음 ← ★ 매우 중요 ★
❌ URL을 단축하거나 삭제함

═══════════════════════════════════════════════════════════════
## 5️⃣ URL 처리 규칙 (매우 중요!)
═══════════════════════════════════════════════════════════════

✅ 반드시 따라야 할 것:
- 검색 결과에 URL이 있다면, 참고 문서에 반드시 포함하세요
- URL은 완전한 형태(https://...)로 유지하세요
- URL을 짧게 만들거나 일부만 표시하지 마세요
- 형식: "- [문서명] > (섹션명)\\n  URL: https://..."

❌ 절대 금지:
- URL 삭제 또는 생략
- URL 변경 또는 단축
- "자세히 보기" 같은 텍스트만 표시 (URL 없이)
- 마크다운 링크 형식 사용 금지: [텍스트](URL) ❌

✅ 올바른 예:
📚 참고 문서:
- EU MRV 제품 사양서 > (1) EU MRV 정의
  URL: https://lab021.atlassian.net/wiki/spaces/TxYP20CKMWxg/pages/3017932877/EU+MRV

❌ 잘못된 예:
📚 참고 문서:
- [EU MRV 제품 사양서](https://lab021.atlassian.net/wiki/spaces/TxYP20CKMWxg/pages/3017932877/EU+MRV)
- 자세히 보기: EU MRV 정의 (URL 없음)

═══════════════════════════════════════════════════════════════
## 6️⃣ 특수 상황 대응
═══════════════════════════════════════════════════════════════

### 문서에 정보가 없을 때:

정보 부족

죄송하지만, 정확한 정보를 찾을 수 없습니다.

이 내용은 현재 문서에 명시되어 있지 않습니다. 자세한 사항은 담당 팀에 문의해 주세요.

혹시 다른 궁금한 점이 있으신가요?

═══════════════════════════════════════════════════════════════
"""


# ===== 개선된 사용자 메시지 템플릿 =====
USER_MESSAGE_TEMPLATE = """아래 검색된 문서를 기반으로 질문에 정확하게 답변해 주세요.

【검색된 문서】
{context}

【사용자 질문】
{query}

【답변 작성 지침】
1. 반드시 위의 "답변 포맷 규칙"을 따라 작성하세요
2. 제목은 한 줄로, 본문은 번호 리스트로 구성하세요
3. 각 섹션 사이에 빈 줄을 추가하세요
4. 참고 문서는 반드시 별도 섹션으로 분리하세요
5. 검색 결과에 포함된 URL은 반드시 참고 문서에 포함하세요 (절대 생략 금지!)
6. 문서에 없는 내용은 절대 추가하지 마세요"""



# ===== LangChain 1.0 RAG 서비스 (개선) =====
class LangChainRAGService:
    """LangChain 1.0 기반 RAG 서비스 (베디 프롬프트 적용)"""

    def __init__(self):
        """Agent 초기화"""
        print("🔧 LangChain 1.0 RAG Service 초기화 중...")

        # 1. 임베딩
        self.embeddings = CustomEmbeddings()

        # 2. Retriever
        self.retriever = SupabaseRetriever(
            embeddings=self.embeddings,
            k=5,
            threshold=0.3
        )

        # 3. LLM (개선된 설정)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,  # ✅ 낮춰서 일관성 향상
            openai_api_key=OPENAI_API_KEY,
            streaming=True
        )

        # 4. 프롬프트 템플릿 (재사용)
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", VEDDY_SYSTEM_PROMPT),
            ("user", USER_MESSAGE_TEMPLATE)
        ])

        # 5. Tool 정의
        @tool
        def search_knowledge_base(query: str) -> str:
            """베슬링크 사내 문서(Confluence 위키, 규정, 매뉴얼)를 검색합니다."""
            context, _ = self.retriever.search(query)
            return context

        self.tools = [search_knowledge_base]

        # 6. Agent 생성 시도 (선택사항)
        self.agent = None
        try:
            self.agent = create_agent(
                model="openai:gpt-4o-mini",
                tools=self.tools,
                system_prompt=VEDDY_SYSTEM_PROMPT
            )
            print("✅ LangChain 1.0 Agent 사용")
        except Exception as e:
            print(f"⚠️ create_agent 실패, 직접 LLM 호출 모드 ({e})")

        print("✅ LangChain 1.0 RAG Service 초기화 완료")

    def process_query(self, user_id: str, query: str) -> Dict[str, Any]:
        """RAG 쿼리 처리 (일반 응답)"""
        try:
            # 1. 문서 검색
            context_text, raw_chunks = self.retriever.search(query)

            # 2. 프롬프트 생성
            messages = self.prompt_template.format_messages(
                context=context_text,
                query=query
            )

            # 3. LLM 호출
            response = self.llm.invoke(messages)
            ai_response = response.content

            # 4. ✅ 소스 ID 추출 (저장용)
            source_chunk_ids = [
                chunk.get('id') for chunk in raw_chunks
                if chunk.get('id')
            ]

            # 5. 메시지 저장
            supabase_service.save_message(
                user_id=user_id,
                user_query=query,
                ai_response=ai_response,
                source_chunk_ids=source_chunk_ids,
                usage={}
            )

            return {
                "user_query": query,
                "ai_response": ai_response,
                "source_chunks": raw_chunks,  # ✅ 원본 청크 반환
                "usage": {}
            }

        except Exception as e:
            print(f"❌ RAG 처리 중 오류: {e}")
            raise

    def process_query_streaming(self, user_id: str, query: str) -> Generator[str, None, None]:
        """RAG 스트리밍 응답 (베디 프롬프트 적용)"""
        try:
            # 1. 문서 검색
            context_text, raw_chunks = self.retriever.search(query)

            # 2. 프롬프트 생성
            messages = self.prompt_template.format_messages(
                context=context_text,
                query=query
            )

            # 3. 스트리밍 LLM 호출
            full_response = ""
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    token = chunk.content
                    full_response += token
                    yield token

            # 4. ✅ 소스 ID 추출
            source_chunk_ids = [
                chunk.get('id') for chunk in raw_chunks
                if chunk.get('id')
            ]

            # 5. 메시지 저장
            supabase_service.save_message(
                user_id=user_id,
                user_query=query,
                ai_response=full_response,
                source_chunk_ids=source_chunk_ids,
                usage={}
            )

        except Exception as e:
            print(f"❌ 스트리밍 중 오류: {e}")
            yield f"\n\n[오류 발생]\n죄송합니다. 처리 중 문제가 발생했습니다: {str(e)}"


# 글로벌 인스턴스
langchain_rag_service = LangChainRAGService()
