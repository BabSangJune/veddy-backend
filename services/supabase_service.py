# services/supabase_service.py
from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY
import uuid

class SupabaseService:
    def __init__(self, use_service_role: bool = False):
        """Supabase 클라이언트 초기화"""
        key = SUPABASE_SERVICE_ROLE_KEY if use_service_role else SUPABASE_KEY
        self.client: Client = create_client(SUPABASE_URL, key)
        print("✅ Supabase 클라이언트 초기화 완료")

    # ==================== documents 테이블 ====================

    def add_document(self, source: str, source_id: str, title: str,
                     content: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """문서 추가 또는 업데이트"""
        data = {
            "source": source,
            "source_id": source_id,
            "title": title,
            "content": content,
            "metadata": metadata or {},
            "is_active": True
        }

        response = self.client.table("documents").upsert(
            data,
            on_conflict="source_id"  # source_id 기준 upsert
        ).execute()
        return response.data[0] if response.data else {}

    def get_document(self, source_id: str) -> Optional[Dict[str, Any]]:
        """source_id로 문서 조회"""
        response = self.client.table("documents").select("*").eq("source_id", source_id).execute()
        return response.data[0] if response.data else None

    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """UUID로 문서 조회"""
        response = self.client.table("documents").select("*").eq("id", document_id).execute()
        return response.data[0] if response.data else None

    def list_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """문서 목록 조회 (활성화된 것만)"""
        response = (
            self.client.table("documents")
            .select("*")
            .eq("is_active", True)
            .limit(limit)
            .execute()
        )
        return response.data

    # ==================== document_chunks 테이블 ====================

    def add_chunk(self, document_id: str, content: str, embedding: List[float],
                  chunk_number: int) -> Dict[str, Any]:
        """청크 추가 (UUID 기반)"""
        data = {
            "document_id": document_id,  # UUID string
            "content": content,
            "embedding": embedding,
            "chunk_number": chunk_number
        }

        response = self.client.table("document_chunks").insert(data).execute()
        return response.data[0] if response.data else {}

    def get_chunks_by_document(self, document_id: str) -> List[Dict[str, Any]]:
        """특정 문서의 모든 청크 조회"""
        response = (
            self.client.table("document_chunks")
            .select("*")
            .eq("document_id", document_id)
            .order("chunk_number")
            .execute()
        )
        return response.data

    def search_chunks(self, embedding: List[float], limit: int = 5,
                      threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        벡터 유사도 검색 (match_documents RPC 함수 사용)
        """
        try:
            response = self.client.rpc(
                'match_documents',
                {
                    'query_embedding': embedding,
                    'match_threshold': threshold,
                    'match_count': limit
                }
            ).execute()

            return response.data if response.data else []

        except Exception as e:
            print(f"❌ 벡터 검색 오류: {e}")
            return []

    # ==================== messages 테이블 ====================

    def save_message(self, user_id: str, user_query: str, ai_response: str,
                     source_chunk_ids: List[str], usage: Dict) -> Dict[str, Any]:
        """대화 메시지 저장 (UUID 기반)"""
        data = {
            "user_id": user_id,
            "user_query": user_query,
            "ai_response": ai_response,
            "source_chunk_ids": source_chunk_ids,  # UUID 리스트
            "usage": usage
        }

        try:
            response = self.client.table("messages").insert(data).execute()
            return response.data[0] if response.data else {}
        except Exception as e:
            print(f"⚠️ 메시지 저장 실패: {e}")
            return {}

    def get_user_messages(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """사용자의 대화 기록 조회"""
        response = (
            self.client.table("messages")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data

    # ==================== document_sources 테이블 ====================

    def add_source(self, source_type: str, source_name: str,
                   api_url: Optional[str] = None, api_token: Optional[str] = None,
                   sync_interval: int = 86400) -> Dict[str, Any]:
        """데이터 소스 추가"""
        data = {
            "source_type": source_type,
            "source_name": source_name,
            "api_url": api_url,
            "api_token": api_token,
            "sync_interval": sync_interval,
            "is_active": True
        }

        response = self.client.table("document_sources").insert(data).execute()
        return response.data[0] if response.data else {}

    def list_active_sources(self) -> List[Dict[str, Any]]:
        """활성화된 소스 목록"""
        response = (
            self.client.table("document_sources")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        return response.data

    # ==================== 유틸리티 ====================

    def test_connection(self) -> bool:
        """Supabase 연결 테스트"""
        try:
            response = self.client.table("documents").select("id").limit(1).execute()
            return True
        except Exception as e:
            print(f"❌ Supabase 연결 실패: {e}")
            return False

    def get_stats(self) -> Dict[str, int]:
        """데이터베이스 통계"""
        try:
            docs = self.client.table("documents").select("id", count="exact").execute()
            chunks = self.client.table("document_chunks").select("id", count="exact").execute()
            messages = self.client.table("messages").select("id", count="exact").execute()

            return {
                "documents": docs.count if hasattr(docs, 'count') else 0,
                "chunks": chunks.count if hasattr(chunks, 'count') else 0,
                "messages": messages.count if hasattr(messages, 'count') else 0
            }
        except Exception as e:
            print(f"⚠️ 통계 조회 실패: {e}")
            return {"documents": 0, "chunks": 0, "messages": 0}


# 글로벌 인스턴스
supabase_service = SupabaseService()
