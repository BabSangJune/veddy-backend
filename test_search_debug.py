# test_search_debug.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.embedding_service import embedding_service
from services.supabase_service import supabase_service

# 테스트 쿼리
query = "EU MRV 항차"
print(f"🔍 검색 쿼리: {query}\n")

# 임베딩 생성
query_embedding = embedding_service.embed_text(query)
print(f"✅ 임베딩 생성 완료\n")

# 검색 실행 (threshold 낮춤)
results = supabase_service.search_chunks(
    embedding=query_embedding,
    limit=5,
    threshold=0.2
)

print(f"\n📊 최종 결과: {len(results)}개\n")

if results:
    for i, result in enumerate(results, 1):
        print(f"[{i}] 제목: {result.get('title')}")
        print(f"    유사도: {result.get('similarity'):.3f}")
        print(f"    내용: {result.get('content')[:100]}...")
        print()
else:
    print("❌ 검색 결과 없음!")
