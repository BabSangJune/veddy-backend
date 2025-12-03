# load_confluence_data.py (config 통합 + 토큰 필터링 완성)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.confluence_service import confluence_service
from services.embedding_service import embedding_service
from services.supabase_service import supabase_service
from services.token_chunk_service import token_chunk_service
from config import CONFLUENCE_URL, VECTOR_SEARCH_CONFIG  # ✅ VECTOR_SEARCH_CONFIG 추가

def load_confluence_documents():
    """Confluence 문서를 Supabase에 로드 (완전 config 통합)"""

    print("\n" + "="*60)
    print("📚 Confluence 문서 로드 시작 (토큰 기반 + config 통합)")
    print(f"📊 Config: chunk={VECTOR_SEARCH_CONFIG['chunk_tokens']}tokens, overlap={VECTOR_SEARCH_CONFIG['overlap_tokens']}")
    print("="*60)

    # 1. Confluence에서 문서 조회
    print("\n1️⃣ Confluence에서 문서 조회 중...")
    try:
        pages = confluence_service.get_all_pages_with_content()
    except Exception as e:
        print(f"❌ Confluence 조회 실패: {e}")
        return

    if not pages:
        print("❌ Confluence에서 문서를 찾을 수 없습니다.")
        return

    print(f"\n✅ {len(pages)}개 페이지 조회 완료")

    # 2. 각 페이지별로 청크 분할 및 저장
    print("\n2️⃣ 문서 처리 중...")
    success_count = 0
    error_count = 0

    for idx, page in enumerate(pages, 1):
        try:
            page_title = page.get('title', '제목 없음')
            page_id = page.get('page_id', '')
            page_content = page.get('content', '')
            page_url = page.get('url', '')
            page_labels = page.get('labels', [])

            print(f"\n [{idx}/{len(pages)}] 페이지 처리: {page_title}")

            # ✅ 토큰 기반 필터링 (config 통합)
            text_stats = token_chunk_service.get_text_stats(page_content)
            print(f"   📊 원본: {text_stats['char_count']}자 / {text_stats['token_count']}토큰")

            if text_stats['token_count'] < VECTOR_SEARCH_CONFIG['min_chunk_tokens']:  # ✅ 토큰 기준 변경
                print(f"   ⚠️ 내용이 너무 짧아서 스킵 (토큰: {text_stats['token_count']})")
                continue

            # ===== URL 처리 =====
            full_url = page_url
            if page_url and not page_url.startswith('http'):
                full_url = f"{CONFLUENCE_URL}{page_url}"

            print(f"   🔗 URL: {full_url}")

            # 1. 문서 저장
            print(f"   ├─ 문서 저장 중...")
            saved_doc = supabase_service.add_document(
                source="confluence",
                source_id=page_id,
                title=page_title,
                content=page_content,
                metadata={
                    'url': full_url,
                    'page_url': full_url,
                    'labels': page_labels,
                    'source': 'confluence',
                    'confluence_id': page_id,
                    'token_count': text_stats['token_count']
                }
            )

            document_id = saved_doc.get("id")
            if not document_id:
                print(f"   ❌ 문서 저장 실패")
                error_count += 1
                continue

            print(f"   ├─ ✅ 문서 저장 완료 (ID: {document_id})")

            # 2. ✅ config 기반 토큰 청킹
            print(f"   ├─ 토큰 기반 청크 분할 중...")
            chunks = token_chunk_service.chunk_text(
                page_content,
                chunk_tokens=VECTOR_SEARCH_CONFIG['chunk_tokens'],      # ✅ config 사용
                overlap_tokens=VECTOR_SEARCH_CONFIG['overlap_tokens'],  # ✅ config 사용
                min_chunk_tokens=VECTOR_SEARCH_CONFIG['min_chunk_tokens']  # ✅ config 사용
            )
            print(f"   ├─ ✅ {len(chunks)}개 청크로 분할 (토큰 기반)")

            # 3. 임베딩 & 저장
            print(f"   ├─ 벡터 임베딩 중...")
            embeddings = embedding_service.embed_batch(chunks)

            for chunk_num, (chunk_content, embedding) in enumerate(zip(chunks, embeddings), 1):
                chunk_stats = token_chunk_service.get_text_stats(chunk_content)
                supabase_service.add_chunk(
                    document_id=document_id,
                    chunk_number=chunk_num,
                    content=chunk_content,
                    embedding=embedding
                )
                print(f"   │  └─ 청크 {chunk_num}: {chunk_stats['char_count']}자 / {chunk_stats['token_count']}토큰")

            print(f"   └─ ✅ {len(chunks)}개 청크 저장 완료")
            success_count += 1

        except Exception as e:
            print(f"   ❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            error_count += 1
            continue

    # 3. 최종 통계
    print("\n" + "="*60)
    print("✅ Confluence 문서 로드 완료!")
    print("="*60)

    print(f"\n📊 처리 결과:")
    print(f"   - 성공: {success_count}개")
    print(f"   - 실패: {error_count}개")
    print(f"   - 전체: {len(pages)}개")

    # Supabase 통계
    try:
        all_docs = supabase_service.list_documents(limit=100)
        confluence_docs = [d for d in all_docs if d.get("source") == "confluence"]
        print(f"\n📊 Supabase 통계:")
        print(f"   - 전체 문서: {len(all_docs)}개")
        print(f"   - Confluence 문서: {len(confluence_docs)}개")
    except Exception as e:
        print(f"\n⚠️ 통계 조회 실패: {e}")

if __name__ == "__main__":
    load_confluence_documents()
