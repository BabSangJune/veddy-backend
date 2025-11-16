from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY


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
            "metadata": metadata or {}
        }
        response = self.client.table("documents").upsert(data).execute()
        return response.data[0] if response.data else {}
    
    def get_document(self, source_id: str) -> Optional[Dict[str, Any]]:
        """source_id로 문서 조회"""
        response = self.client.table("documents") \
            .select("*") \
            .eq("source_id", source_id) \
            .execute()
        return response.data[0] if response.data else None
    
    def list_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """모든 활성 문서 조회"""
        response = self.client.table("documents") \
            .select("*") \
            .eq("is_active", True) \
            .limit(limit) \
            .execute()
        return response.data
    
    # ==================== document_chunks 테이블 ====================
    
    def add_chunk(self, document_id: str, chunk_number: int, 
                  content: str, embedding: List[float]) -> Dict[str, Any]:
        """청크 추가"""
        data = {
            "document_id": document_id,
            "chunk_number": chunk_number,
            "content": content,
            "embedding": embedding
        }
        response = self.client.table("document_chunks").insert(data).execute()
        return response.data[0] if response.data else {}
    
    def search_chunks(self, embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """벡터 유사도 검색"""
        response = self.client.rpc(
            "match_documents",
            {
                "query_embedding": embedding,
                "match_count": limit
            }
        ).execute()
        return response.data if response.data else []
    
    def get_chunks_by_document(self, document_id: str) -> List[Dict[str, Any]]:
        """문서의 모든 청크 조회"""
        response = self.client.table("document_chunks") \
            .select("*") \
            .eq("document_id", document_id) \
            .order("chunk_number", desc=False) \
            .execute()
        return response.data
    
    # ==================== messages 테이블 ====================
    
    def save_message(self, user_id: str, user_query: str, ai_response: str,
                     source_chunk_ids: Optional[List[str]] = None,
                     usage: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        """메시지 저장"""
        data = {
            "user_id": user_id,
            "user_query": user_query,
            "ai_response": ai_response,
            "source_chunk_ids": source_chunk_ids or [],
            "usage": usage or {}
        }
        response = self.client.table("messages").insert(data).execute()
        return response.data[0] if response.data else {}
    
    def get_user_messages(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """사용자의 메시지 조회"""
        response = self.client.table("messages") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return response.data
    
    # ==================== 테스트 ====================
    
    def test_connection(self) -> bool:
        """Supabase 연결 테스트"""
        try:
            response = self.client.table("documents").select("*").limit(1).execute()
            print("✅ Supabase 연결 성공!")
            return True
        except Exception as e:
            print(f"❌ Supabase 연결 실패: {e}")
            return False


# 글로벌 인스턴스
supabase_service = SupabaseService()
