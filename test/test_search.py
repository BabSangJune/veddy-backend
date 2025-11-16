import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.embedding_service import embedding_service
from services.rag_service import rag_service


def test_search():
    """벡터 검색 테스트"""

    test_queries = [
        "배포는 어떻게 하나요?",
        "API 문서를 찾아줘",
        "근무 시간은?",
        "롤백 절차는?"
    ]

    print("\n" + "="*60)
    print("🔍 벡터 검색 테스트")
    print("="*60)

    for query in test_queries:
        print(f"\n❓ 질문: {query}")

        # RAG 검색
        relevant_chunks = rag_service.search_relevant_chunks(query, top_k=3)

        print(f"📌 관련 청크 {len(relevant_chunks)}개 찾음:")

        for i, chunk in enumerate(relevant_chunks, 1):
            similarity = chunk.get("similarity", 0)
            content_preview = chunk.get("content", "")[:100] + "..."
            print(f"  {i}. [신뢰도: {similarity:.1%}]")
            print(f"     {content_preview}")

    print("\n" + "="*60)
    print("✅ 벡터 검색 테스트 완료!")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_search()
