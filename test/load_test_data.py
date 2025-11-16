import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.embedding_service import embedding_service
from services.supabase_service import supabase_service
import uuid


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """
    텍스트를 청크로 분할

    Args:
        text: 분할할 텍스트
        chunk_size: 한 청크의 최대 문자 수
        overlap: 청크 간 겹치는 문자 수

    Returns:
        청크 리스트
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks


def load_test_documents():
    """
    테스트 문서들을 Supabase에 로드
    """

    # 테스트 문서 1: 배포 가이드
    doc1_content = """
    ## 배포 프로세스 완벽 가이드
    
    ### 1. 사전 준비 단계
    배포 전에 다음 사항을 확인하세요:
    - 모든 테스트 케이스 통과 (100% 커버리지)
    - 코드 리뷰 완료 및 승인
    - 데이터베이스 마이그레이션 검토
    - 배포 환경 준비 (서버, DB, 네트워크)
    
    ### 2. 배포 단계
    배포는 다음 순서대로 진행됩니다:
    1. 스테이징 환경에 배포
    2. 스테이징에서 1시간 모니터링
    3. 프로덕션 환경에 배포
    4. 카나리 배포 (10% 트래픽)
    5. 트래픽 100% 전환
    6. 모니터링 (24시간)
    
    ### 3. 트러블슈팅
    배포 중 문제가 발생한 경우:
    - 즉시 로그 확인
    - 데이터베이스 상태 점검
    - 캐시 초기화
    - API 연결 상태 확인
    
    ### 4. 롤백 절차
    긴급 상황에서는 다음과 같이 롤백합니다:
    - 이전 버전의 도커 이미지 사용
    - 데이터베이스 복구 (백업에서)
    - 캐시 무효화
    - 모니터링 재개
    """

    # 테스트 문서 2: API 설명서
    doc2_content = """
    ## 베디 API 문서
    
    ### 인증
    모든 API 요청에는 다음 헤더가 필요합니다:
    - Authorization: Bearer {token}
    - Content-Type: application/json
    
    ### 주요 엔드포인트
    
    #### POST /api/chat/query
    사용자 질문을 처리하고 답변을 반환합니다.
    
    요청:
    {
        "user_id": "user@example.com",
        "query": "배포는 어떻게 하나요?"
    }
    
    응답:
    {
        "user_query": "배포는 어떻게 하나요?",
        "ai_response": "배포는 다음과 같이...",
        "source_chunks": [...],
        "usage": {"input_tokens": 100, "output_tokens": 200}
    }
    
    #### GET /api/health
    서버 상태를 확인합니다.
    
    응답:
    {
        "status": "healthy",
        "message": "베디가 준비되었습니다!"
    }
    """

    # 테스트 문서 3: 사내 규정
    doc3_content = """
    ## 베슬링크 사내 규정
    
    ### 근무 시간
    - 근무 시간: 09:00 ~ 18:00 (점심시간 12:00 ~ 13:00)
    - 유연 근무: 인정
    - 재택 근무: 팀장 승인 시 가능
    
    ### 휴가 정책
    - 연차: 연 15일
    - 월차: 월 1일
    - 병가: 의료 증빙 필요
    - 특별휴가: 경조사, 제사 등
    
    ### 보안 정책
    - 비밀번호: 3개월마다 변경
    - VPN: 사무실 외 접근 시 필수
    - 민감 정보: 암호화 저장
    - 로그아웃: 자리 비울 때 필수
    
    ### 비용 정책
    - 출장 경비: 경영진 사전 승인
    - 교육비: 연 200만원 한도
    - 용품 구매: 팀장 결재
    """

    documents = [
        {
            "source": "manual",
            "source_id": "doc-001",
            "title": "배포 프로세스 완벽 가이드",
            "content": doc1_content,
            "metadata": {
                "author": "DevOps Team",
                "category": "배포",
                "updated": "2025-11-16"
            }
        },
        {
            "source": "manual",
            "source_id": "doc-002",
            "title": "베디 API 문서",
            "content": doc2_content,
            "metadata": {
                "author": "AI Team",
                "category": "API",
                "updated": "2025-11-16"
            }
        },
        {
            "source": "manual",
            "source_id": "doc-003",
            "title": "베슬링크 사내 규정",
            "content": doc3_content,
            "metadata": {
                "author": "HR Team",
                "category": "규정",
                "updated": "2025-11-16"
            }
        }
    ]

    print("\n" + "="*60)
    print("📚 테스트 데이터 로드 시작")
    print("="*60)

    for idx, doc in enumerate(documents, 1):
        print(f"\n[{idx}/3] 문서 처리: {doc['title']}")

        # 1. 문서 저장
        print(f"  ├─ 문서 저장 중...")
        saved_doc = supabase_service.add_document(
            source=doc["source"],
            source_id=doc["source_id"],
            title=doc["title"],
            content=doc["content"],
            metadata=doc["metadata"]
        )
        document_id = saved_doc.get("id")
        print(f"  ├─ ✅ 문서 저장 완료 (ID: {document_id})")

        # 2. 청크 분할
        print(f"  ├─ 청크 분할 중...")
        chunks = chunk_text(doc["content"], chunk_size=400, overlap=50)
        print(f"  ├─ ✅ {len(chunks)}개 청크로 분할 완료")

        # 3. 청크 임베딩 & 저장
        print(f"  ├─ 벡터 임베딩 중...")

        # 배치로 임베딩 처리 (효율적)
        embeddings = embedding_service.embed_batch(chunks)

        for chunk_num, (chunk_content, embedding) in enumerate(zip(chunks, embeddings), 1):
            supabase_service.add_chunk(
                document_id=document_id,
                chunk_number=chunk_num,
                content=chunk_content,
                embedding=embedding
            )

        print(f"  └─ ✅ {len(chunks)}개 청크 저장 완료 (임베딩 포함)")

    print("\n" + "="*60)
    print("✅ 모든 테스트 데이터 로드 완료!")
    print("="*60 + "\n")

    # 저장된 문서 확인
    all_docs = supabase_service.list_documents(limit=100)
    print(f"📊 Supabase에 저장된 문서: {len(all_docs)}개")

    for doc in all_docs:
        print(f"  - {doc.get('title')} (ID: {doc.get('source_id')})")


if __name__ == "__main__":
    load_test_documents()
