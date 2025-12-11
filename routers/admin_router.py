# routers/admin_router.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import asyncio
import json
import time

from services.confluence_service import ConfluenceService
from services.supabase_service import supabase_service
from services.embedding_service import embedding_service
from services.token_chunk_service import token_chunk_service
from auth.auth_service import verify_supabase_token
from logging_config import get_logger

router = APIRouter(prefix="/api/admin", tags=["admin"])

class LoadConfluenceDataRequest(BaseModel):
    """Confluence 데이터 로드 요청"""
    space_key: str
    atlassian_id: str
    api_token: str


# ===== 1️⃣ POST 엔드포인트 (초기 요청) =====

@router.post("/confluence/load")
async def load_confluence_data(
        request: LoadConfluenceDataRequest,
        user: dict = Depends(verify_supabase_token)
):
    """
    ✨ Confluence 데이터 로드 요청 (초기)

    즉시 응답을 반환합니다.
    클라이언트는 이 응답의 stream_endpoint를 사용해 SSE 스트림에 연결합니다.
    """
    logger = get_logger(__name__, user_id=user["user_id"])

    logger.info(
        "📚 Confluence 데이터 로드 요청 (POST)",
        extra={
            "space_key": request.space_key,
            "atlassian_id": request.atlassian_id[:20] + "***"
        }
    )

    try:
        # ✅ 즉시 응답 반환
        return {
            "status": "accepted",
            "message": f"✅ Space '{request.space_key}'의 데이터 로드를 시작합니다.",
            "space_key": request.space_key,
            "stream_endpoint": f"/api/admin/confluence/load-stream"
        }

    except Exception as e:
        logger.error(f"❌ 요청 처리 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"요청 처리 중 오류: {str(e)}"
        )


# ===== 2️⃣ GET SSE 엔드포인트 (진행 상황) =====

# routers/admin_router.py

@router.get("/confluence/load-stream")
async def load_confluence_data_stream(
        space_key: str,
        atlassian_id: str,
        api_token: str,
        user: dict = Depends(verify_supabase_token)
):
    """
    ✨ SSE: Confluence 데이터 로드 (실시간 진행 상황)
    Query Parameter 형식으로 자격증명 전달
    """
    logger = get_logger(__name__, user_id=user["user_id"])

    async def event_generator():
        """SSE 이벤트 생성기"""
        try:
            # 1️⃣ 시작 이벤트
            yield f"data: {json.dumps({'status': 'started', 'message': 'Confluence 데이터 로드 시작'})}\n\n"

            confluence_service = ConfluenceService.initialize(
                space_key=space_key,
                atlassian_id=atlassian_id,
                api_token=api_token
            )

            pages = confluence_service.get_all_pages_with_content()

            if not pages:
                yield f"data: {json.dumps({'status': 'error', 'message': f'{space_key}에서 페이지를 찾을 수 없음'})}\n\n"
                return

            total_pages = len(pages)
            success_count = 0
            skip_count = 0
            error_count = 0
            total_chunks = 0

            # 2️⃣ 페이지 로드 완료 알림
            yield f"data: {json.dumps({
                'status': 'pages_loaded',
                'total_pages': total_pages,
                'message': f'총 {total_pages}개 페이지 로드 완료. 처리 시작합니다.',
                'progress_percent': 5
            })}\n\n"

            # 3️⃣ 각 페이지 처리
            for idx, page in enumerate(pages, 1):
                try:
                    page_title = page.get('title', '제목 없음')
                    page_id = page.get('page_id', '')
                    page_content = page.get('content', '')
                    page_url = page.get('url', '')
                    page_labels = page.get('labels', [])
                    created_at = page.get('created_at')
                    updated_at = page.get('updated_at')
                    version_number = page.get('version_number', 1)

                    # 진행 상황 알림 (처리 시작)
                    progress = int(5 + ((idx - 1) / total_pages) * 90)  # 5% ~ 95%
                    yield f"data: {json.dumps({
                        'status': 'processing',
                        'message': f'[{idx}/{total_pages}] {page_title} 처리 중...',
                        'current_page': page_title,
                        'processed_pages': idx,
                        'total_pages': total_pages,
                        'progress_percent': progress,
                        'success_count': success_count,
                        'skip_count': skip_count,
                        'error_count': error_count,
                        'total_chunks': total_chunks
                    })}\n\n"

                    # 기존 문서 확인
                    existing_doc = supabase_service.get_document_by_source_id(
                        source="confluence",
                        source_id=page_id
                    )

                    # updated_at 비교해서 변경 없으면 스킵
                    if existing_doc:
                        existing_updated_at = existing_doc.get("updated_at")
                        confluence_updated_str = updated_at.isoformat() if updated_at else ""
                        if existing_updated_at == confluence_updated_str:
                            skip_count += 1
                            continue

                    # 토큰 필터링
                    text_stats = token_chunk_service.get_text_stats(page_content)
                    if text_stats['token_count'] < 30:
                        skip_count += 1
                        continue

                    # 문서 저장
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
                            'space_key': space_key,
                            'version_number': version_number
                        },
                        created_at=created_at,
                        updated_at=updated_at
                    )

                    document_id = saved_doc.get("id")
                    if not document_id:
                        error_count += 1
                        continue

                    # 기존 청크 삭제
                    if existing_doc:
                        supabase_service.delete_chunks_by_document_id(document_id)

                    # 청크 분할
                    chunks = token_chunk_service.chunk_text(
                        page_content,
                        chunk_tokens=400,
                        overlap_tokens=50,
                        min_chunk_tokens=30
                    )

                    # ✅ 임베딩 전 진행 상황 알림
                    yield f"data: {json.dumps({
                        'status': 'embedding',
                        'message': f'[{idx}/{total_pages}] {page_title} 임베딩 중... ({len(chunks)}개 청크)',
                        'current_page': page_title,
                        'processed_pages': idx,
                        'total_pages': total_pages,
                        'progress_percent': progress,
                        'success_count': success_count,
                        'skip_count': skip_count,
                        'error_count': error_count,
                        'total_chunks': total_chunks
                    })}\n\n"

                    # 벡터 임베딩
                    embeddings = embedding_service.embed_batch(chunks)

                    # ✅ 임베딩 후 청크 저장 진행 상황
                    for chunk_num, (chunk_content, embedding) in enumerate(zip(chunks, embeddings), 1):
                        supabase_service.add_chunk(
                            document_id=document_id,
                            chunk_number=chunk_num,
                            content=chunk_content,
                            embedding=embedding
                        )
                        total_chunks += 1

                    success_count += 1

                    # ✅ 페이지 완료 알림
                    yield f"data: {json.dumps({
                        'status': 'page_completed',
                        'message': f'[{idx}/{total_pages}] {page_title} 완료 ({len(chunks)}개 청크)',
                        'current_page': page_title,
                        'processed_pages': idx,
                        'total_pages': total_pages,
                        'progress_percent': progress,
                        'success_count': success_count,
                        'skip_count': skip_count,
                        'error_count': error_count,
                        'total_chunks': total_chunks
                    })}\n\n"

                except Exception as e:
                    logger.error(f"페이지 처리 실패: {e}", exc_info=True)
                    error_count += 1
                    yield f"data: {json.dumps({
                        'status': 'page_error',
                        'message': f'❌ 페이지 처리 실패: {str(e)}',
                        'processed_pages': idx,
                        'total_pages': total_pages,
                        'error_count': error_count
                    })}\n\n"
                    continue

            # ✅ 최종 완료
            yield f"data: {json.dumps({
                'status': 'completed',
                'success_count': success_count,
                'skip_count': skip_count,
                'error_count': error_count,
                'total_chunks': total_chunks,
                'progress_percent': 100,
                'message': f'✅ {success_count}개 문서 처리 완료 ({total_chunks}개 청크 생성)'
            })}\n\n"

            logger.info(
                "✅ Confluence 데이터 로드 완료",
                extra={
                    "space_key": space_key,
                    "success": success_count,
                    "skip": skip_count,
                    "error": error_count,
                    "chunks": total_chunks
                }
            )

        except Exception as e:
            logger.error(f"SSE 스트림 오류: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': f'오류: {str(e)}'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")



# ===== 3️⃣ GET 상태 조회 =====

@router.get("/confluence/status")
async def get_confluence_status(
        user: dict = Depends(verify_supabase_token)
):
    """
    ✨ 관리자: 현재 Confluence 상태 확인
    """
    logger = get_logger(__name__, user_id=user["user_id"])

    try:
        all_docs = supabase_service.list_documents(limit=1000)
        confluence_docs = [d for d in all_docs if d.get("source") == "confluence"]

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


@router.get("/confluence/progress")
async def get_confluence_progress(
        user: dict = Depends(verify_supabase_token)
):
    """
    ✨ 폴링용: 현재 처리 진행 상황 조회
    """
    return {
        "status": "processing",
        "message": "진행 중..."
    }
