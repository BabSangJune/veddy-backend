from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class DocumentCreate(BaseModel):
    """문서 생성 요청"""
    source: str = Field(..., description="출처 (confluence, notion, manual)")
    source_id: str = Field(..., description="외부 ID")
    title: str = Field(..., min_length=1)
    content: str
    meta: Optional[Dict[str, Any]] = None

class Document(DocumentCreate):
    """문서 응답"""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class ChunkCreate(BaseModel):
    """청크 생성 요청"""
    document_id: str
    chunk_number: int
    content: str
    embedding: List[float]  # 1024-dim 벡터

class Chunk(ChunkCreate):
    """청크 응답"""
    id: str
    created_at: datetime

class ChatRequest(BaseModel):
    """채팅 요청 (✅ Phase 3-A Final)"""
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1, max_length=1000)
    table_mode: bool = Field(
        default=False,
        description="표 형식 답변 모드 활성화 (True: 마크다운 표 우선, False: 일반 답변)"
    )

    # ✅ 새로 추가 (Phase 3-A Final)
    history: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="이전 대화 맥락 (없으면 DB에서 자동 조회)"
    )

    comparison_info: Optional[Dict] = Field(
        default=None,
        description="비교 모드 정보 (예: {'is_comparison': True, 'topics': ['A', 'B']})"
    )

class ChatResponse(BaseModel):
    """채팅 응답"""
    user_query: str
    ai_response: str
    source_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Dict[str, int] = Field(default_factory=dict)

class MessageCreate(BaseModel):
    """메시지 저장 요청"""
    user_id: str
    user_query: str
    ai_response: str
    source_chunk_ids: Optional[List[str]] = None
    usage: Optional[Dict[str, int]] = None

class Message(MessageCreate):
    """메시지 응답"""
    id: str
    created_at: datetime
