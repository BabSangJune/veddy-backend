# routers/admin_router.py (✨ 변경 감지 로직 추가)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.confluence_service import ConfluenceService
from services.supabase_service import supabase_service
from services.embedding_service import embedding_service
from services.token_chunk_service import token_chunk_service
from auth.auth_service import verify_supabase_token
from logging_config import get_logger
import json

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ===== 📋 요청 스키마 =====

class LoadConfluenceDataRequest(BaseModel):
    """Confluence 데이터 로드 요청"""
    space_key: str
    atlassian_id: str
    api_token: str


# ===== 🔌 API 엔드포인트 =====

@router.post("/confluence/load")
async def load_confluence_data(
        request: LoadConfluenceDataRequest,
        user: dict = Depends(verify_supabase_token)
):
    """
    ✨ 관리자: Confluence 데이터 로드 (✅ 변경 감지 + 스마트 업데이트)
    """

    logger = get_logger(__name__, user_id=user["user_id"])

    logger.info(
        "📚 Confluence 데이터 로드 요청",
        extra={
            "space_key": request.space_key,
            "atlassian_id": request.atlassian_id[:20] + "***"
        }
    )

    try:
        print("\n" + "="*60)
        print("📚 Confluence 데이터 로드 시작")
        print("="*60)

        confluence_service = ConfluenceService.initialize(
            space_key=request.space_key,
            atlassian_id=request.atlassian_id,
            api_token=request.api_token
        )

        print("\n1️⃣ Confluence에서 문서 조회 중...")
        pages = confluence_service.get_all_pages_with_content()

        if not pages:
            logger.warning(f"⚠️ {request.space_key}에서 페이지를 찾을 수 없음")
            raise HTTPException(
                status_code=400,
                detail=f"Space '{request.space_key}'에서 페이지를 찾을 수 없습니다."
            )

        print(f"✅ {len(pages)}개 페이지 조회 완료\n")

        print("2️⃣ 문서 처리 중...")
        success_count = 0
        skip_count = 0  # ← ✅ 스킵 카운트
        error_count = 0
        total_chunks = 0

        for idx, page in enumerate(pages, 1):
            try:
                page_title = page.get('title', '제목 없음')
                page_id = page.get('page_id', '')
                page_content = page.get('content', '')
                page_url = page.get('url', '')
                page_labels = page.get('labels', [])
                # ✅ 시간 정보 추출
                created_at = page.get('created_at')
                updated_at = page.get('updated_at')
                version_number = page.get('version_number', 1)

                print(f"\n [{idx}/{len(pages)}] 페이지 처리: {page_title}")

                # ✅ 1️⃣ 기존 문서 확인 (변경 감지)
                existing_doc = supabase_service.get_document_by_source_id(
                    source="confluence",
                    source_id=page_id
                )

                # ✅ 2️⃣ updated_at 비교
                if existing_doc:
                    existing_updated_at = existing_doc.get("updated_at")

                    # ISO 형식 변환 (비교를 위해)
                    confluence_updated_str = updated_at.isoformat() if updated_at else ""

                    if existing_updated_at == confluence_updated_str:
                        print(f"   ⏭️  건너뛰기 (변경 없음)")
                        print(f"      마지막 수정: {existing_updated_at}")
                        skip_count += 1
                        continue
                    else:
                        print(f"   🔄 업데이트 (변경됨)")
                        print(f"      기존: {existing_updated_at}")
                        print(f"      신규: {confluence_updated_str}")

                # ✅ 3️⃣ 토큰 필터링
                text_stats = token_chunk_service.get_text_stats(page_content)
                print(f"   📊 원본: {text_stats['char_count']}자 / {text_stats['token_count']}토큰")

                if text_stats['token_count'] < 30:
                    print(f"   ⚠️ 내용이 너무 짧아서 스킵")
                    skip_count += 1
                    continue

                print(f"   ├─ 문서 저장 중...")
                # ✅ 시간 정보 전달
                saved_doc = supabase_service.add_document(
                    source="confluence",
                    source_id=page_id,
                    title=page_title,
                    content=page_content,
                    metadata={
                        'url': page_url,
                        'page_url': page_url,
                        'labels': page_labels,
                        'source': 'confluence',
                        'confluence_id': page_id,
                        'token_count': text_stats['token_count'],
                        'space_key': request.space_key,
                        'version_number': version_number
                    },
                    # ✅ Confluence 생성/수정 시간 전달
                    created_at=created_at,
                    updated_at=updated_at
                )

                document_id = saved_doc.get("id")
                if not document_id:
                    print(f"   ❌ 문서 저장 실패")
                    error_count += 1
                    continue

                print(f"   ├─ ✅ 문서 저장/업데이트 완료 (ID: {document_id})")

                print(f"   ├─ 토큰 기반 청크 분할 중...")
                chunks = token_chunk_service.chunk_text(
                    page_content,
                    chunk_tokens=400,
                    overlap_tokens=50,
                    min_chunk_tokens=30
                )
                print(f"   ├─ ✅ {len(chunks)}개 청크로 분할")

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
                    total_chunks += 1

                print(f"   └─ ✅ {len(chunks)}개 청크 저장 완료")
                success_count += 1

            except Exception as e:
                print(f"   ❌ 오류 발생: {e}")
                logger.error(f"페이지 처리 실패: {e}", exc_info=True)
                error_count += 1
                continue

        print("\n" + "="*60)
        print("✅ Confluence 데이터 로드 완료!")
        print("="*60)

        print(f"\n📊 처리 결과:")
        print(f"   - 성공: {success_count}개")
        print(f"   - 스킵 (변경 없음): {skip_count}개")  # ← ✅ 추가
        print(f"   - 실패: {error_count}개")
        print(f"   - 전체: {len(pages)}개")
        print(f"   - 총 청크: {total_chunks}개")

        logger.info(
            "✅ Confluence 데이터 로드 완료",
            extra={
                "space_key": request.space_key,
                "total_pages": len(pages),
                "success_count": success_count,
                "skip_count": skip_count,  # ← ✅ 추가
                "error_count": error_count,
                "total_chunks": total_chunks
            }
        )

        return {
            "status": "success",
            "space_key": request.space_key,
            "total_pages": len(pages),
            "success_count": success_count,
            "skip_count": skip_count,  # ← ✅ 추가
            "error_count": error_count,
            "total_chunks": total_chunks,
            "message": f"✅ {success_count}개 문서 처리, {skip_count}개 건너뜀, {total_chunks}개 청크 저장"
        }

    except ValueError as e:
        logger.error(f"❌ 검증 오류: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"❌ 로드 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Confluence 데이터 로드 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/confluence/status")
async def get_confluence_status(
        user: dict = Depends(verify_supabase_token)
):
    """
    ✨ 관리자: 현재 Confluence 상태 확인

    Returns:
        현재 저장된 Confluence 문서 정보
    """

    logger = get_logger(__name__, user_id=user["user_id"])

    try:
        # Supabase에서 Confluence 문서 조회
        all_docs = supabase_service.list_documents(limit=1000)
        confluence_docs = [d for d in all_docs if d.get("source") == "confluence"]

        # Space별로 문서 분류
        space_stats = {}
        for doc in confluence_docs:
            space_key = doc.get("metadata", {}).get("space_key", "unknown")
            if space_key not in space_stats:
                space_stats[space_key] = {"count": 0, "docs": []}
            space_stats[space_key]["count"] += 1
            space_stats[space_key]["docs"].append({
                "id": doc.get("id"),
                "title": doc.get("title")
            })

        logger.info(
            "Confluence 상태 조회",
            extra={
                "total_docs": len(confluence_docs),
                "space_count": len(space_stats)
            }
        )

        return {
            "status": "success",
            "total_documents": len(confluence_docs),
            "total_spaces": len(space_stats),
            "space_stats": space_stats
        }

    except Exception as e:
        logger.error(f"❌ 상태 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
