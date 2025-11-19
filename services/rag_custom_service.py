# services/rag_custom_service.py
from typing import List, Dict, Any, Generator
from openai import OpenAI
from services.embedding_service import embedding_service
from services.supabase_service import supabase_service
from config import OPENAI_API_KEY

class RAGService:
    def __init__(self):
        """RAG 서비스 초기화"""
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

        # 개선된 베디 시스템 프롬프트 (이전과 동일)
        self.system_prompt = """너는 베슬링크의 내부 AI 어시스턴트 '베디(VEDDY)'야.

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

4. **톤 & 매너**
   - 높임말 사용, 따뜻하고 친근한 표현
   - 업무적이면서도 따뜻한 톤 유지

## 절대 금지 사항
❌ 문서에 없는 내용을 추측하거나 일반 지식으로 보충
❌ 확실하지 않은 출처 명시
❌ 개인 의견이나 추천 (문서 기반만)
"""

        print("✅ RAG 서비스 초기화 완료")

    def _format_context(self, chunks: List[Dict[str, Any]]) -> str:
        """검색된 청크를 컨텍스트로 포맷팅 (UUID 기반)"""
        if not chunks:
            return "관련 문서를 찾을 수 없습니다."

        formatted = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get('content', '')
            similarity = chunk.get('similarity', 0)
            title = chunk.get('title', '제목 없음')
            source = chunk.get('source', '출처 미상')
            chunk_number = chunk.get('chunk_number', 0)

            formatted.append(f"""
[문서 {i}] (유사도: {similarity:.2f})
출처: {source} > {title} (섹션 {chunk_number})
내용: {content}
---""")

        return "\n".join(formatted)

    def process_query(self, user_id: str, query: str) -> Dict[str, Any]:
        """RAG 파이프라인 실행 (일반 응답)"""
        try:
            # 1. 쿼리 임베딩
            query_embedding = embedding_service.embed_text(query)

            # 2. 벡터 유사도 검색
            retrieved_chunks = supabase_service.search_chunks(
                embedding=query_embedding,
                limit=5,
                threshold=0.3  # 낮춰서 더 많은 결과 허용
            )

            # 3. 컨텍스트 생성
            context_text = self._format_context(retrieved_chunks)

            # 4. LLM 호출
            user_message = f"""다음 문서를 기반으로 질문에 답변해주세요.

문서:
{context_text}

질문: {query}

(출처는 항상 명시해주세요)"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            ai_response = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

            # 5. 메시지 저장 (UUID 리스트로 변환)
            chunk_ids = [str(chunk.get('id')) for chunk in retrieved_chunks]
            supabase_service.save_message(
                user_id=user_id,
                user_query=query,
                ai_response=ai_response,
                source_chunk_ids=chunk_ids,
                usage=usage
            )

            return {
                "user_query": query,
                "ai_response": ai_response,
                "source_chunks": retrieved_chunks,
                "usage": usage
            }

        except Exception as e:
            print(f"❌ RAG 처리 중 오류: {e}")
            raise

    def process_query_streaming(self, user_id: str, query: str) -> Generator[str, None, None]:
        """RAG 파이프라인 실행 (스트리밍 응답)"""
        try:
            # 1. 쿼리 임베딩
            query_embedding = embedding_service.embed_text(query)

            # 2. 벡터 유사도 검색
            retrieved_chunks = supabase_service.search_chunks(
                embedding=query_embedding,
                limit=5,
                threshold=0.3
            )

            # 3. 컨텍스트 생성
            context_text = self._format_context(retrieved_chunks)

            # 4. LLM 스트리밍 호출
            user_message = f"""다음 문서를 기반으로 질문에 답변해주세요.

문서:
{context_text}

질문: {query}

(출처는 항상 명시해주세요)"""

            stream = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=1000,
                stream=True
            )

            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    yield token

            # 5. 스트리밍 종료 후 메시지 저장
            chunk_ids = [str(chunk.get('id')) for chunk in retrieved_chunks]
            supabase_service.save_message(
                user_id=user_id,
                user_query=query,
                ai_response=full_response,
                source_chunk_ids=chunk_ids,
                usage={}
            )

        except Exception as e:
            print(f"❌ 스트리밍 RAG 처리 중 오류: {e}")
            yield f"[오류] {str(e)}"


# 글로벌 인스턴스
rag_service = RAGService()
