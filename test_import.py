# test_import.py

from services.supabase_service import supabase_service

# add_chunk 메서드 확인
print("✅ supabase_service 인스턴스:", supabase_service)
print("✅ add_chunk 메서드 존재 여부:", hasattr(supabase_service, 'add_chunk'))

if hasattr(supabase_service, 'add_chunk'):
    print("✅ add_chunk 메서드 발견!")
else:
    print("❌ add_chunk 메서드 없음!")
    print("\n사용 가능한 메서드:")
    for attr in dir(supabase_service):
        if not attr.startswith('_'):
            print(f"  - {attr}")
