from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class DocumentCreate(BaseModel):
    """문서 생성 요청"""
    source: str  # 'confluence', 'notion', 'manual'
    source_id: str
    title: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


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
    """채팅 요청"""
    user_id: str
    query: str


class ChatResponse(BaseModel):
    """채팅 응답"""
    user_query: str
    ai_response: str
    source_chunks: List[Dict[str, Any]]  # 참고한 청크들
    usage: Dict[str, int]  # token 사용량


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
