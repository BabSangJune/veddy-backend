import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import requests
import base64
from config import CONFLUENCE_URL, CONFLUENCE_API_TOKEN

print("="*60)
print("🔍 Confluence 인증 테스트")
print("="*60)

# 이메일 입력
email = input("\n📧 Confluence 계정 이메일 입력: ").strip()

if not email:
    print("❌ 이메일 필요")
    sys.exit(1)

if not CONFLUENCE_API_TOKEN:
    print("❌ CONFLUENCE_API_TOKEN이 설정되지 않았습니다")
    print("   .env 파일 확인: CONFLUENCE_API_TOKEN=...")
    sys.exit(1)

print(f"\n설정:")
print(f"  - URL: {CONFLUENCE_URL}")
print(f"  - 이메일: {email}")
print(f"  - API Token: {'***' if CONFLUENCE_API_TOKEN else '❌'}")

# 기본 인증 설정
auth_string = f"{email}:{CONFLUENCE_API_TOKEN}"
encoded_auth = base64.b64encode(auth_string.encode()).decode()

headers = {
    "Authorization": f"Basic {encoded_auth}",
    "Accept": "application/json"
}

# 1. 메자 엔드포인트 테스트 (가장 간단)
print(f"\n1️⃣ 메타 정보 조회 (가장 간단한 테스트):")
url = f"{CONFLUENCE_URL}/rest/api/version"

try:
    response = requests.get(url, headers=headers)
    print(f"  상태: {response.status_code}")

    if response.status_code == 200:
        print(f"  ✅ 인증 성공!")
        print(f"  응답: {response.json()}")
    else:
        print(f"  ❌ 인증 실패")
        print(f"  응답: {response.text[:300]}")

except Exception as e:
    print(f"  ❌ 오류: {e}")

# 2. 모든 공간 조회
print(f"\n2️⃣ 모든 공간 조회:")
url = f"{CONFLUENCE_URL}/rest/api/space"

try:
    response = requests.get(url, headers=headers)
    print(f"  상태: {response.status_code}")

    if response.status_code == 200:
        spaces = response.json().get("results", [])
        print(f"  ✅ {len(spaces)}개 공간:")

        for space in spaces:
            print(f"    - {space.get('name')} (KEY: {space.get('key')})")
    else:
        print(f"  ❌ 오류: {response.status_code}")
        print(f"  {response.text[:300]}")

except Exception as e:
    print(f"  ❌ 오류: {e}")

print("\n" + "="*60)
