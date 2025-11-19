# test_supabase.py
from services.supabase_service import supabase_service
from unicodedata import normalize as unicode_normalize

# 저장된 데이터 확인
chunks = supabase_service.client.table('document_chunks').select('content').limit(1).execute()

if chunks:
    original = chunks.data[0]['content']
    normalized = unicode_normalize('NFC', original)

    print(f"원본: {repr(original[:100])}")
    print(f"정규화: {repr(normalized[:100])}")

    if original == normalized:
        print("✅ 데이터 정상")
    else:
        print("❌ 데이터 손상 - 재로드 필요")
