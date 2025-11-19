# services/langchain_rag_service.py (LangChain 1.0)

from typing import List, Dict, Any, Generator

# ===== LangChain 1.0 Import =====
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool

# ⚠️ LangChain 1.0의 새로운 Agent API
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


# ===== Tool 정의 (LangChain 1.0 @tool 데코레이터) =====
class SupabaseRetriever:
    """Supabase 검색 래퍼"""

    def __init__(self, embeddings: Embeddings, k: int = 5, threshold: float = 0.3):
        self.embeddings = embeddings
        self.k = k
        self.threshold = threshold

    def search(self, query: str) -> str:
        """문서 검색 실행"""
        try:
            # 쿼리 임베딩
            query_embedding = self.embeddings.embed_query(query)

            # Supabase 검색
            chunks = supabase_service.search_chunks(
                embedding=query_embedding,
                limit=self.k,
                threshold=self.threshold
            )

            if not chunks:
                return "⚠️ 관련 문서를 찾을 수 없습니다."

            # 컨텍스트 생성
            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                title = chunk.get('title', '제목 없음')
                content = chunk.get('content', '')
                source = chunk.get('source', '출처 미상')
                similarity = chunk.get('similarity', 0.0)

                context_parts.append(
                    f"📄 [문서 {i}] {title}\n"
                    f"유사도: {similarity:.2f}\n"
                    f"{content}\n"
                    f"📍 출처: {source}"
                )

            return "\n\n".join(context_parts)

        except Exception as e:
            return f"❌ 검색 중 오류: {str(e)}"
class LangChainRAGService:
    """LangChain 1.0 기반 RAG 서비스 (create_agent 사용)"""

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

        # ===== 🔥 핵심: LLM을 항상 먼저 초기화 =====
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=OPENAI_API_KEY,
            streaming=True
        )

        # 3. Tool 정의
        @tool
        def search_knowledge_base(query: str) -> str:
            """베슬링크 사내 문서(Confluence)를 검색합니다."""
            return self.retriever.search(query)

        self.tools = [search_knowledge_base]

        # 4. Agent 생성 시도 (선택사항)
        try:
            self.agent = create_agent(
                model="openai:gpt-4o-mini",
                tools=self.tools,
                system_prompt="""너는 베슬링크의 내부 AI 어시스턴트 '베디(VEDDY)'야.

## 핵심 원칙
1. **반드시 search_knowledge_base 도구를 먼저 사용**해 사내 문서를 검색
2. 검색된 문서 내용만을 기반으로 답변 (할루시네이션 금지)
3. 답변 시 출처를 명확히 표기 (예: [문서 1] 참고)
4. 문서를 찾지 못하면 "관련 문서가 없습니다"라고 정직하게 답변
5. 친절하고 명확한 한국어 사용

## 답변 형식
- 핵심 답변을 먼저 제시
- 근거가 되는 문서 출처 명시
- 추가 정보나 관련 절차가 있으면 안내"""
            )
            print("✅ create_agent 사용")
        except Exception as e:
            print(f"⚠️ create_agent 실패, LLM 직접 사용 모드: {e}")
            self.agent = None

        print("✅ LangChain 1.0 RAG Service 초기화 완료")

    def process_query(self, user_id: str, query: str) -> Dict[str, Any]:
        """RAG 쿼리 처리 (일반 응답)"""
        try:
            if self.agent:
                # Agent 사용
                result = self.agent.invoke({
                    "messages": [{"role": "user", "content": query}]
                })
                ai_response = result["messages"][-1]["content"]
            else:
                # Fallback: 직접 검색 + LLM 호출
                context = self.retriever.search(query)
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "너는 베디(VEDDY)야. 주어진 컨텍스트를 기반으로 답변해."),
                    ("user", f"컨텍스트:\n{context}\n\n질문: {query}")
                ])
                messages = prompt.format_messages()
                response = self.llm.invoke(messages)
                ai_response = response.content

            # 메시지 저장
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
        """RAG 스트리밍 응답"""
        try:
            # 1. 문서 검색
            context = self.retriever.search(query)

            # 2. 프롬프트 생성
            prompt = ChatPromptTemplate.from_messages([
                ("system", "너는 베디(VEDDY)야. 주어진 컨텍스트를 기반으로 답변해."),
                ("user", f"컨텍스트:\n{context}\n\n질문: {query}")
            ])
            messages = prompt.format_messages()

            # 3. 스트리밍 LLM 호출
            full_response = ""
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    token = chunk.content
                    full_response += token
                    yield token

            # 4. 메시지 저장
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
