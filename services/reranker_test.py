# test_reranker.py (임시 테스트 파일)

from services.reranker_service import reranker_service

# 테스트 데이터
query = "베슬링크 날씨 시스템 개요"
chunks = [
    {"id": "1", "content": "베슬링크는 날씨 시스템을 운영합니다.", "score": 0.5},
    {"id": "2", "content": "NOAA 모델을 사용합니다.", "score": 0.4},
    {"id": "3", "content": "태풍 데이터는 AerisWeather에서 수집합니다.", "score": 0.3},
]

# 리랭킹 실행
reranked = reranker_service.rerank(query, chunks, top_k=3)

# 결과 출력
for i, chunk in enumerate(reranked, 1):
    print(f"{i}. {chunk['content']}")
    print(f"   원본 점수: {chunk['score']:.4f}")
    print(f"   리랭크 점수: {chunk['rerank_score']:.4f}\n")
