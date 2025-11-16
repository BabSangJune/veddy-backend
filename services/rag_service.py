from services.embedding_service import embedding_service
from services.supabase_service import supabase_service
from typing import List, Dict, Any, Tuple
from openai import OpenAI
from config import OPENAI_API_KEY


class RAGService:
    def __init__(self):
        """RAG 서비스 초기화"""
        self.embedding_service = embedding_service
        self.supabase_service = supabase_service
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ RAG 서비스 초기화 완료")

    def search_relevant_chunks(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        사용자 질문에서 관련 청크 검색

        1. 질문을 벡터로 변환
        2. Supabase에서 유사한 청크 검색
        3. 메타데이터와 함께 반환
        """
        # 1. 질문 벡터화
        query_embedding = self.embedding_service.embed_text(query)

        # 2. 벡터 유사도 검색 (Supabase RPC 사용)
        # Note: RPC 함수는 별도로 Supabase에서 설정 필요
        # 여기서는 기본 select로 대체
        response = self.supabase_service.client.table("document_chunks") \
            .select("*") \
            .limit(top_k * 2) \
            .execute()

        # 3. 벡터 유사도 계산 (간단한 코사인 유사도)
        chunks_with_similarity = []
        for chunk in response.data:
            similarity = self._cosine_similarity(query_embedding, chunk.get("embedding", []))
            chunks_with_similarity.append({
                **chunk,
                "similarity": similarity
            })

        # 상위 top_k개 반환
        return sorted(chunks_with_similarity, key=lambda x: x["similarity"], reverse=True)[:top_k]

    def _cosine_similarity(self, vec1, vec2) -> float:
        """코사인 유사도 계산"""
        import numpy as np
        import json

        # None 체크
        if vec1 is None or vec2 is None:
            return 0.0

        try:
            # 문자열이면 JSON 파싱
            if isinstance(vec1, str):
                vec1 = json.loads(vec1)
            if isinstance(vec2, str):
                vec2 = json.loads(vec2)

            # numpy array로 변환
            v1 = np.array(vec1, dtype=np.float32)
            v2 = np.array(vec2, dtype=np.float32)

            # 크기 확인
            if v1.size == 0 or v2.size == 0:
                return 0.0

            if v1.shape[0] != v2.shape[0]:
                print(f"⚠️ 벡터 차원 불일치: {v1.shape[0]} vs {v2.shape[0]}")
                return 0.0

            # 코사인 유사도 계산
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = float(dot_product / (norm1 * norm2))
            return similarity

        except Exception as e:
            print(f"❌ 유사도 계산 오류: {e}")
            return 0.0

    def generate_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> Tuple[str, Dict[str, int]]:
        """
        LLM을 사용해 답변 생성

        Args:
            query: 사용자 질문
            context_chunks: 검색된 관련 청크들

        Returns:
            (답변, 토큰 사용량)
        """
        # 컨텍스트 조합
        context_text = "\n---\n".join([
            f"출처: {chunk.get('content', '')} (신뢰도: {chunk.get('similarity', 0):.2%})"
            for chunk in context_chunks
        ])

        # 프롬프트 구성
        system_prompt = """너는 베슬링크의 내부 AI 어시스턴트 '베디(VEDDY)'야.
너는 사내 문서 기반으로 정확한 답변을 제공하는 온순하고 성실한 챗봇이야.

다음 규칙을 지켜:
1. 제공된 문서 기반으로만 답변해
2. 문서에 없는 내용은 "문서에서 해당 정보를 찾을 수 없습니다"라고 말해
3. 한국어로 친절하고 명확하게 답변해
4. 출처를 명시해
"""

        user_message = f"""다음 문서를 기반으로 질문에 답변해주세요.

문서:
{context_text}

질문: {query}
"""

        # GPT 호출
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=1000
        )

        answer = response.choices[0].message.content
        usage = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }

        return answer, usage

    def process_query(self, user_id: str, query: str) -> Dict[str, Any]:
        """
        전체 RAG 파이프라인 실행

        1. 질문 입력받기
        2. 관련 청크 검색
        3. LLM으로 답변 생성
        4. 메시지 저장
        """
        # 1. 관련 청크 검색
        relevant_chunks = self.search_relevant_chunks(query, top_k=5)

        # 2. 답변 생성
        answer, usage = self.generate_answer(query, relevant_chunks)

        # 3. 메시지 저장
        source_chunk_ids = [chunk.get("id") for chunk in relevant_chunks]
        self.supabase_service.save_message(
            user_id=user_id,
            user_query=query,
            ai_response=answer,
            source_chunk_ids=source_chunk_ids,
            usage=usage
        )

        return {
            "user_query": query,
            "ai_response": answer,
            "source_chunks": relevant_chunks,
            "usage": usage
        }


# 글로벌 인스턴스
rag_service = RAGService()
