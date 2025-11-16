import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.supabase_service import supabase_service
from services.embedding_service import embedding_service
import json

print("="*60)
print("🔍 벡터 데이터 디버그")
print("="*60)

# 1. 저장된 청크 확인
print("\n1️⃣ Supabase의 청크 데이터 확인:")
response = supabase_service.client.table("document_chunks").select("*").limit(1).execute()

if response.data:
    chunk = response.data[0]
    print(f"  ✅ 청크 찾음")
    print(f"    - ID: {chunk.get('id')}")
    print(f"    - Content: {chunk.get('content')[:50]}...")

    embedding = chunk.get("embedding")
    print(f"\n    - Embedding 타입: {type(embedding)}")

    if embedding is None:
        print(f"    ❌ Embedding이 NULL입니다!")
    elif isinstance(embedding, str):
        print(f"    ⚠️ 문자열로 저장됨 (길이: {len(embedding)})")
        try:
            embedding_list = json.loads(embedding)
            print(f"    ✅ JSON 파싱 성공: {len(embedding_list)} 차원")
        except:
            print(f"    ❌ JSON 파싱 실패")
    elif isinstance(embedding, list):
        print(f"    ✅ 리스트 형태: {len(embedding)} 차원")
    else:
        print(f"    ❓ 알 수 없는 타입: {type(embedding)}")
else:
    print(f"  ❌ 청크 없음")

# 2. 새로운 임베딩 생성 테스트
print(f"\n2️⃣ 임베딩 모델 테스트:")
test_text = "배포는 어떻게 하나요?"
new_embedding = embedding_service.embed_text(test_text)
print(f"  ✅ 임베딩 생성 성공")
print(f"    - 텍스트: {test_text}")
print(f"    - 차원: {len(new_embedding)}")
print(f"    - 샘플 값: {new_embedding[:3]}")

("\n" + "="*60)
