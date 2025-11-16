import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.confluence_service import confluence_service
from services.embedding_service import embedding_service
from services.supabase_service import supabase_service


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """텍스트를 청크로 분할"""
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks


def load_confluence_documents():
    """Confluence 문서를 Supabase에 로드"""

    print("\n" + "="*60)
    print("📚 Confluence 문서 로드 시작")
    print("="*60)

    # 1. Confluence에서 문서 조회
    print("\n1️⃣ Confluence에서 문서 조회 중...")
    pages = confluence_service.get_all_pages_with_content()

    if not pages:
        print("❌ Confluence에서 문서를 찾을 수 없습니다.")
        return

    print(f"\n✅ {len(pages)}개 페이지 조회 완료")

    # 2. 각 페이지별로 청크 분할 및 저장
    print("\n2️⃣ 문서 처리 중...")

    for idx, page in enumerate(pages, 1):
        print(f"\n  [{idx}/{len(pages)}] 페이지 처리: {page['title']}")

        # 내용이 너무 짧으면 스킵
        if len(page["content"]) < 100:
            print(f"    ⚠️ 내용이 너무 짧아서 스킵 (길이: {len(page['content'])})")
            continue

        # 1. 문서 저장
        print(f"    ├─ 문서 저장 중...")
        saved_doc = supabase_service.add_document(
            source="confluence",
            source_id=page["page_id"],
            title=page["title"],
            content=page["content"],
            metadata={
                "url": page["url"],
                "labels": page["labels"],
                "source": "confluence"
            }
        )

        document_id = saved_doc.get("id")
        if not document_id:
            print(f"    ❌ 문서 저장 실패")
            continue

        print(f"    ├─ ✅ 문서 저장 완료")

        # 2. 청크 분할
        print(f"    ├─ 청크 분할 중...")
        chunks = chunk_text(page["content"], chunk_size=400, overlap=50)
        print(f"    ├─ ✅ {len(chunks)}개 청크로 분할")

        # 3. 임베딩 & 저장
        print(f"    ├─ 벡터 임베딩 중...")
        embeddings = embedding_service.embed_batch(chunks)

        for chunk_num, (chunk_content, embedding) in enumerate(zip(chunks, embeddings), 1):
            supabase_service.add_chunk(
                document_id=document_id,
                chunk_number=chunk_num,
                content=chunk_content,
                embedding=embedding
            )

        print(f"    └─ ✅ {len(chunks)}개 청크 저장 완료")

    print("\n" + "="*60)
    print("✅ Confluence 문서 로드 완료!")
    print("="*60)

    # 저장된 문서 통계
    all_docs = supabase_service.list_documents(limit=100)
    confluence_docs = [d for d in all_docs if d.get("source") == "confluence"]

    print(f"\n📊 Supabase 통계:")
    print(f"  - 전체 문서: {len(all_docs)}개")
    print(f"  - Confluence 문서: {len(confluence_docs)}개")


if __name__ == "__main__":
    load_confluence_documents()
