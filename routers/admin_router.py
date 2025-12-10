# routers/admin_router.py (✨ 신규 파일)

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
    ✨ 관리자: Confluence 데이터 로드

    역할:
    - 관리자가 입력한 자격증명으로 Confluence Service 초기화
    - Space Key에서 모든 문서 조회
    - Supabase에 저장 및 임베딩

    Args:
        request: Space Key, 이메일, API Token
        user: 인증된 사용자

    Returns:
        로드 결과 (성공/실패 개수)
    """

    logger = get_logger(__name__, user_id=user["user_id"])

    # ✅ 1. 입력값 검증
    logger.info(
        "📚 Confluence 데이터 로드 요청",
        extra={
            "space_key": request.space_key,
            "atlassian_id": request.atlassian_id[:20] + "***"  # Atlassian ID 마스킹
        }
    )

    try:
        # ✅ 2. Confluence Service 초기화 (관리자 입력값으로)
        print("\n" + "="*60)
        print("📚 Confluence 데이터 로드 시작")
        print("="*60)

        confluence_service = ConfluenceService.initialize(
            space_key=request.space_key,
            atlassian_id=request.atlassian_id,
            api_token=request.api_token
        )

        # ✅ 3. Confluence에서 문서 조회
        print("\n1️⃣ Confluence에서 문서 조회 중...")
        pages = confluence_service.get_all_pages_with_content()

        if not pages:
            logger.warning(f"⚠️ {request.space_key}에서 페이지를 찾을 수 없음")
            raise HTTPException(
                status_code=400,
                detail=f"Space '{request.space_key}'에서 페이지를 찾을 수 없습니다. Space Key를 확인해주세요."
            )

        print(f"✅ {len(pages)}개 페이지 조회 완료\n")

        # ✅ 4. 각 페이지별로 처리
        print("2️⃣ 문서 처리 중...")
        success_count = 0
        error_count = 0
        total_chunks = 0

        for idx, page in enumerate(pages, 1):
            try:
                page_title = page.get('title', '제목 없음')
                page_id = page.get('page_id', '')
                page_content = page.get('content', '')
                page_url = page.get('url', '')
                page_labels = page.get('labels', [])

                print(f"\n [{idx}/{len(pages)}] 페이지 처리: {page_title}")

                # ✅ 토큰 기반 필터링
                text_stats = token_chunk_service.get_text_stats(page_content)
                print(f"   📊 원본: {text_stats['char_count']}자 / {text_stats['token_count']}토큰")

                # 너무 짧은 내용 스킵
                if text_stats['token_count'] < 30:
                    print(f"   ⚠️ 내용이 너무 짧아서 스킵")
                    continue

                # ✅ 1. 문서 저장
                print(f"   ├─ 문서 저장 중...")
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
                        'space_key': request.space_key
                    }
                )

                document_id = saved_doc.get("id")
                if not document_id:
                    print(f"   ❌ 문서 저장 실패")
                    error_count += 1
                    continue

                print(f"   ├─ ✅ 문서 저장 완료 (ID: {document_id})")

                # ✅ 2. 토큰 기반 청킹
                print(f"   ├─ 토큰 기반 청크 분할 중...")
                chunks = token_chunk_service.chunk_text(
                    page_content,
                    chunk_tokens=400,
                    overlap_tokens=50,
                    min_chunk_tokens=30
                )
                print(f"   ├─ ✅ {len(chunks)}개 청크로 분할")

                # ✅ 3. 임베딩 & 저장
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

        # ✅ 5. 최종 통계
        print("\n" + "="*60)
        print("✅ Confluence 데이터 로드 완료!")
        print("="*60)

        print(f"\n📊 처리 결과:")
        print(f"   - 성공: {success_count}개")
        print(f"   - 실패: {error_count}개")
        print(f"   - 전체: {len(pages)}개")
        print(f"   - 총 청크: {total_chunks}개")

        logger.info(
            "✅ Confluence 데이터 로드 완료",
            extra={
                "space_key": request.space_key,
                "total_pages": len(pages),
                "success_count": success_count,
                "error_count": error_count,
                "total_chunks": total_chunks
            }
        )

        return {
            "status": "success",
            "space_key": request.space_key,
            "total_pages": len(pages),
            "success_count": success_count,
            "error_count": error_count,
            "total_chunks": total_chunks,
            "message": f"✅ {success_count}개 문서, {total_chunks}개 청크가 저장되었습니다."
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
