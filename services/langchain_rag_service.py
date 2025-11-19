# services/langchain_rag_service.py (LangChain 1.0 + 베디 프롬프트)

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
    """Supabase 검색 래퍼"""

    def __init__(self, embeddings: Embeddings, k: int = 5, threshold: float = 0.3):
        self.embeddings = embeddings
        self.k = k
        self.threshold = threshold

    def search(self, query: str) -> str:
        """문서 검색 실행"""
        try:
            query_embedding = self.embeddings.embed_query(query)
            chunks = supabase_service.search_chunks(
                embedding=query_embedding,
                limit=self.k,
                threshold=self.threshold
            )

            if not chunks:
                return "관련 문서를 찾을 수 없습니다."

            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                title = chunk.get('title', '제목 없음')
                content = chunk.get('content', '')
                source = chunk.get('source', '출처 미상')

                context_parts.append(
                    f"📄 [문서 {i}] {title}\n{content}\n📍 출처: {source}"
                )

            return "\n\n".join(context_parts)

        except Exception as e:
            return f"검색 중 오류: {str(e)}"


# ===== 베디 프롬프트 템플릿 =====
VEDDY_SYSTEM_PROMPT = """너는 베슬링크의 내부 AI 어시스턴트 '베디(VEDDY)'야.

## 너의 역할과 정체성
- 이름: 베디 (Vessellink's Buddy)
- 성격: 친절하고 신뢰할 수 있으며, 온순하고 성실함
- 목표: 베슬링크 직원들의 업무 효율화와 정보 접근성 개선
- 전문성: 사내 문서(Confluence 위키, 규정, 매뉴얼)에 기반한 정확한 답변

## 답변의 원칙 (절대 준수)
1. **문서 기반 답변만 제공**
   - 반드시 제공된 문서 컨텍스트에서만 답변
   - 문서에 없는 추측이나 일반 지식은 제공하지 말 것

2. **구조화된 답변 포맷**
   - [답변 본문] → 직접적이고 명확한 답변
   - [참고 문서] → "X 문서, Y 항목" 형식으로 출처 명시
   - [추가 정보] (필요시) → 연관 규정이나 담당자 정보

3. **할루시네이션 방지**
   - 불확실한 경우: "정확한 정보를 찾을 수 없습니다"
   - 부분 일치: "다음 정보를 찾았습니다. 정확한 내용은 [문서명]을 참고하세요"
   - 복수 답변: "다음 여러 경우가 있습니다: 1) ... 2) ... 자세한 내용은 문서 참고"

4. **톤 & 매너**
   - 높임말 사용 (존댓글)
   - 따뜻하고 친근한 표현 ("도움이 되길 바랍니다", "혹시 더 궁금한 점이 있으신가요?")
   - 과도한 이모지나 반말 금지
   - 업무적이면서도 따뜻한 톤 유지

## 처리해야 할 상황별 응답

### 상황1: 문서에서 완벽하게 찾은 경우
[명확한 답변 내용]
참고 문서: [구체적 문서명] > [섹션]

### 상황2: 문서에 없는 경우
죄송하지만, 현재 문서에서 해당 정보를 찾을 수 없습니다.
더 자세한 내용은 [담당 부서] 또는 [담당자명]에게 문의해주세요.

### 상황3: 여러 문서에서 관련 정보가 있는 경우
다음과 같은 관련 정보들을 찾았습니다:
1. [문서1]에서: ...
2. [문서2]에서: ...
어느 정보가 더 필요하신지 알려주세요.

### 상황4: 질문이 모호한 경우
질문을 더 구체적으로 설명해주실 수 있을까요?
예를 들어, [추측되는 세부 사항]에 대해 묻는 건가요?

## 절대 금지 사항
❌ 문서에 없는 내용을 추측하거나 일반 지식으로 보충
❌ 확실하지 않은 출처 명시
❌ 과도하게 길거나 요약되지 않은 답변
❌ 마크다운 오버포맷팅 (필요한 만큼만)
❌ 개인 의견이나 추천 (문서 기반만)"""


# ===== LangChain 1.0 RAG 서비스 =====
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

        # 3. LLM (항상 초기화)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=OPENAI_API_KEY,
            streaming=True
        )

        # 4. Tool 정의
        @tool
        def search_knowledge_base(query: str) -> str:
            """베슬링크 사내 문서(Confluence 위키, 규정, 매뉴얼)를 검색합니다."""
            return self.retriever.search(query)

        self.tools = [search_knowledge_base]

        # 5. Agent 생성 시도 (선택사항)
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
            context_text = self.retriever.search(query)

            # 2. 사용자 메시지 구성 (기존 프롬프트 형식 유지)
            user_message = f"""다음 문서를 기반으로 질문에 답변해주세요.

문서:
{context_text}

질문: {query}

(출처는 항상 명시해주세요)"""

            # 3. 프롬프트 생성
            prompt = ChatPromptTemplate.from_messages([
                ("system", VEDDY_SYSTEM_PROMPT),
                ("user", user_message)
            ])
            messages = prompt.format_messages()

            # 4. LLM 호출
            response = self.llm.invoke(messages)
            ai_response = response.content

            # 5. 메시지 저장
            supabase_service.save_message(
                user_id=user_id,
                user_query=query,
                ai_response=ai_response,
                source_chunk_ids=[],
                usage={}
            )

            return {
                "user_query": query,
                "ai_response": ai_response,
                "source_chunks": [],
                "usage": {}
            }

        except Exception as e:
            print(f"❌ RAG 처리 중 오류: {e}")
            raise

    def process_query_streaming(self, user_id: str, query: str) -> Generator[str, None, None]:
        """RAG 스트리밍 응답 (베디 프롬프트 적용)"""
        try:
            # 1. 문서 검색
            context_text = self.retriever.search(query)

            # 2. 사용자 메시지 구성
            user_message = f"""다음 문서를 기반으로 질문에 답변해주세요.

문서:
{context_text}

질문: {query}

(출처는 항상 명시해주세요)"""

            # 3. 프롬프트 생성
            prompt = ChatPromptTemplate.from_messages([
                ("system", VEDDY_SYSTEM_PROMPT),
                ("user", user_message)
            ])
            messages = prompt.format_messages()

            # 4. 스트리밍 LLM 호출
            full_response = ""
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    token = chunk.content
                    full_response += token
                    yield token

            # 5. 메시지 저장
            supabase_service.save_message(
                user_id=user_id,
                user_query=query,
                ai_response=full_response,
                source_chunk_ids=[],
                usage={}
            )

        except Exception as e:
            print(f"❌ 스트리밍 중 오류: {e}")
            yield f"[오류] {str(e)}"


# 글로벌 인스턴스
langchain_rag_service = LangChainRAGService()
