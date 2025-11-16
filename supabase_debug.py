import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.supabase_service import supabase_service
from services.embedding_service import embedding_service

print("\n" + "="*60)
print("🔍 Supabase 데이터 디버깅")
print("="*60)

# 1. 저장된 문서 확인
print("\n1️⃣ 저장된 문서 개수:")
try:
    response = supabase_service.client.table("documents").select("*").execute()
    documents = response.data
    print(f"✅ 총 {len(documents)}개 문서")

    for i, doc in enumerate(documents[:3], 1):
        print(f"  {i}. {doc.get('title')} (ID: {doc.get('id')})")
except Exception as e:
    print(f"❌ 오류: {e}")

# 2. 저장된 청크 확인
print("\n2️⃣ 저장된 청크 개수:")
try:
    response = supabase_service.client.table("document_chunks").select("*").execute()
    chunks = response.data
    print(f"✅ 총 {len(chunks)}개 청크")

    for i, chunk in enumerate(chunks[:3], 1):
        content = chunk.get('content', '')[:50]
        has_embedding = 'embedding' in chunk and chunk['embedding'] is not None
        print(f"  {i}. {content}... (임베딩: {'✅' if has_embedding else '❌'})")
except Exception as e:
    print(f"❌ 오류: {e}")

# 3. 임베딩 모델 테스트
print("\n3️⃣ 임베딩 모델 테스트:")
try:
    test_text = "프론트엔드 코딩 테스트"
    embedding = embedding_service.embed_text(test_text)
    print(f"✅ 임베딩 생성 성공")
    print(f"  - 차원: {len(embedding)}")
    print(f"  - 샘플: {embedding[:5]}")
except Exception as e:
    print(f"❌ 오류: {e}")

# 4. 유사도 검색 테스트
print("\n4️⃣ 유사도 검색 테스트:")
try:
    query = "프론트엔드 코딩 테스트"
    query_embedding = embedding_service.embed_text(query)

    # 직접 쿼리
    response = supabase_service.client.table("document_chunks").select("*").limit(5).execute()
    chunks = response.data

    print(f"✅ 검색된 청크: {len(chunks)}개")

    # 유사도 계산
    import numpy as np
    for i, chunk in enumerate(chunks[:3], 1):
        chunk_content = chunk.get('content', '')[:50]
        chunk_embedding = chunk.get('embedding', [])

        if chunk_embedding:
            v1 = np.array(query_embedding, dtype=np.float32)
            v2 = np.array(chunk_embedding, dtype=np.float32)

            similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            print(f"  {i}. 유사도: {similarity:.2%} - {chunk_content}...")
        else:
            print(f"  {i}. ❌ 임베딩 없음 - {chunk_content}...")

except Exception as e:
    print(f"❌ 오류: {e}")

print("\n" + "="*60)
