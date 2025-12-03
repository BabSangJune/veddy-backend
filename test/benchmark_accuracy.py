# benchmark_accuracy.py
from typing import List, Tuple
from services.embedding_service import embedding_service
from services.supabase_service import supabase_service

# 테스트 케이스: (질문, 정답 문서 ID)
TEST_CASES = [
    ("휴가 신청 절차", "doc-uuid-1"),
    ("출장비 정산", "doc-uuid-2"),
    # ... 실제 문서 ID로 교체
]

def measure_accuracy(ef_search: int, test_cases: List[Tuple[str, str]]) -> float:
    """정확도 측정 (정답 문서가 Top-5에 있는지)"""
    correct = 0

    for query, expected_doc_id in test_cases:
        embedding = embedding_service.embed_text(query)
        results = supabase_service.search_chunks(
            embedding=embedding,
            limit=5,
            ef_search=ef_search
        )

        # Top-5 결과에 정답 문서가 있는지 확인
        found_doc_ids = [r.get('document_id') for r in results]
        if expected_doc_id in found_doc_ids:
            correct += 1

    accuracy = correct / len(test_cases)
    return accuracy

# 실행
for ef in [20, 50, 100]:
    acc = measure_accuracy(ef, TEST_CASES)
    print(f"ef_search={ef}: 정확도 {acc*100:.1f}%")
