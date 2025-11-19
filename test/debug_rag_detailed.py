import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.rag_custom_service import rag_service
from services.embedding_service import embedding_service
import numpy as np

print("\n" + "="*70)
print("🔍 RAG 검색 심층 디버깅")
print("="*70)

# 테스트 쿼리
test_query = "EU ETS"

# 1. 쿼리 임베딩
print(f"\n1️⃣ 쿼리 임베딩 생성:")
print(f"   질문: {test_query}")
query_embedding = embedding_service.embed_text(test_query)
print(f"   ✅ 차원: {len(query_embedding)}")
print(f"   샘플: {query_embedding[:3]}")

# 2. 저장된 청크 조회
print(f"\n2️⃣ 저장된 모든 청크 조회:")
response = rag_service.supabase_service.client.table("document_chunks").select("*").execute()
all_chunks = response.data
print(f"   ✅ 총 청크 수: {len(all_chunks)}")

# 3. 각 청크별 유사도 계산
print(f"\n3️⃣ 청크별 유사도 계산:")
similarities = []

for i, chunk in enumerate(all_chunks):
    content = chunk.get('content', '')[:50]
    chunk_embedding = chunk.get('embedding', [])

    # 유사도 계산
    similarity = rag_service._cosine_similarity(query_embedding, chunk_embedding)
    similarities.append({
        'chunk_id': chunk.get('id'),
        'content': content,
        'similarity': similarity,
        'embedding_type': type(chunk_embedding).__name__,
        'embedding_sample': str(chunk_embedding)[:50] if isinstance(chunk_embedding, str) else 'array'
    })

    print(f"   {i+1}. 유사도: {similarity:.4f} | {content}...")

# 4. 상위 5개 청크 확인
print(f"\n4️⃣ 상위 5개 청크 (유사도 기준):")
top_5 = sorted(similarities, key=lambda x: x['similarity'], reverse=True)[:5]
for i, item in enumerate(top_5, 1):
    print(f"   {i}. 유사도: {item['similarity']:.4f} | {item['content']}...")
    print(f"      임베딩 타입: {item['embedding_type']}")

# 5. search_relevant_chunks 메서드 직접 호출
print(f"\n5️⃣ search_relevant_chunks 메서드 테스트:")
try:
    relevant_chunks = rag_service.search_relevant_chunks(test_query, top_k=5)
    print(f"   ✅ 검색된 청크 수: {len(relevant_chunks)}")
    for i, chunk in enumerate(relevant_chunks, 1):
        content = chunk.get('content', '')[:50]
        similarity = chunk.get('similarity', 0)
        print(f"   {i}. 유사도: {similarity:.4f} | {content}...")
except Exception as e:
    print(f"   ❌ 오류: {e}")
    import traceback
    traceback.print_exc()

# 6. 최고 유사도 분석
print(f"\n6️⃣ 유사도 통계:")
all_sims = [s['similarity'] for s in similarities]
if all_sims:
    print(f"   최고 유사도: {max(all_sims):.4f}")
    print(f"   최저 유사도: {min(all_sims):.4f}")
    print(f"   평균 유사도: {np.mean(all_sims):.4f}")
    print(f"   중앙값 유사도: {np.median(all_sims):.4f}")

print("\n" + "="*70)
