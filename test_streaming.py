import requests

# 스트리밍 엔드포인트
url = "http://localhost:8000/api/chat/stream"

request_data = {
    "user_id": "applause1319@naver.com",
    "query": "프론트엔드 코딩 테스트 기획 내용을 알려줘"
}

print("\n" + "="*60)
print("🎬 스트리밍 응답 테스트")
print("="*60 + "\n")

try:
    # 스트리밍 요청
    with requests.post(url, json=request_data, stream=True) as response:
        response.raise_for_status()

        print("📡 실시간 응답:\n")

        for line in response.iter_lines():
            if line:
                # " " 제거
                if line.startswith(b" "):
                    token = line[6:].decode('utf-8')

                    if token == "[DONE]":
                        print("\n\n✅ 스트리밍 완료!")
                        break
                    elif token.startswith("ERROR:"):
                        print(f"\n❌ {token}")
                        break
                    else:
                        # 토큰 출력 (한국어 지원)
                        print(token, end="", flush=True)

except requests.exceptions.ConnectionError:
    print("❌ 서버에 연결할 수 없습니다.")
except Exception as e:
    print(f"❌ 오류: {e}")

print("\n" + "="*60 + "\n")
