# services/supabase_service.py

from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY


class SupabaseService:
    def __init__(self, use_service_role: bool = False):
        """Supabase 클라이언트 초기화"""
        key = SUPABASE_SERVICE_ROLE_KEY if use_service_role else SUPABASE_KEY
        self.client: Client = create_client(SUPABASE_URL, key)
        print("✅ Supabase 클라이언트 초기화 완료")

    # ==================== documents ====================

    def add_document(self, source: str, source_id: str, title: str,
                     content: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:

        data = {
            "source": source,
            "source_id": source_id,
            "title": title,
            "content": content,
            "metadata": metadata or {},
            "is_active": True
        }
        try:
            response = self.client.table("documents").upsert(
                data, on_conflict="source_id"
            ).execute()
            return response.data[0] if response.data else {}
        except Exception as e:
            print(f"❌ 문서 추가 실패: {e}")
            return {}

    def list_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """문서 목록"""
        try:
            response = self.client.table("documents").select("*").eq(
                "is_active", True
            ).limit(limit).execute()
            return response.data
        except Exception as e:
            print(f"❌ 목록 조회 실패: {e}")
            return []

    # ==================== chunks ====================

    def add_chunk(self, document_id: str, chunk_number: int,
                  content: str, embedding: List[float]) -> Dict[str, Any]:
        """청크 추가"""
        data = {
            "document_id": document_id,
            "chunk_number": chunk_number,
            "content": content,
            "embedding": embedding
        }
        try:
            response = self.client.table("document_chunks").insert(data).execute()
            return response.data[0] if response.data else {}
        except Exception as e:
            print(f"❌ 청크 추가 실패: {e}")
            return {}


    # services/supabase_service.py

    def search_chunks(self, embedding: List[float], limit: int = 5,
                      threshold: float = 0.2) -> List[Dict[str, Any]]:
        """
        벡터 유사도 검색 (URL 포함)

        Args:
            embedding: 쿼리 임베딩 벡터
            limit: 반환할 최대 결과 수
            threshold: 유사도 임계값 (0~1)

        Returns:
            검색된 청크 목록
        """
        try:
            print(f"🔍 검색 시작 (limit={limit}, threshold={threshold})")

            # RPC 호출
            response = self.client.rpc('match_documents', {
                'query_embedding': embedding,
                'match_count': limit,
                'match_threshold': threshold
            }).execute()

            # response.data 추출
            data = response.data if hasattr(response, 'data') else response

            if not data:
                print("⚠️ 검색 결과 없음")
                return []

            print(f"✅ RPC 응답: {len(data)}개")

            results = []

            for i, item in enumerate(data, 1):
                chunk_id = item.get('id')
                doc_id = item.get('document_id')
                content = item.get('content', '')
                similarity = item.get('similarity', 0.0)

                print(f"  [{i}] chunk_id={chunk_id}, doc_id={doc_id}, sim={similarity:.3f}")

                # 기본 청크 정보
                chunk_data = {
                    'id': chunk_id,
                    'document_id': doc_id,
                    'content': content,
                    'similarity': similarity,
                    'title': '제목 없음',
                    'source': 'confluence',
                    'url': '',
                    'metadata': {}
                }

                # 문서 정보 가져오기
                if doc_id:
                    try:
                        doc_response = self.client.table('documents').select(
                            'id, title, source, metadata'
                        ).eq('id', doc_id).single().execute()

                        if doc_response and doc_response:
                            doc_data = doc_response.data
                            metadata = doc_data.get('metadata', {})

                            chunk_data['title'] = doc_data.get('title', '제목 없음')
                            chunk_data['source'] = doc_data.get('source', 'confluence')
                            chunk_data['url'] = metadata.get('url') or metadata.get('page_url', '')
                            chunk_data['metadata'] = metadata

                            print(f"      ✅ 제목: {chunk_data['title']}")
                            if chunk_data['url']:
                                print(f"      🔗 URL: {chunk_data['url']}")

                    except Exception as doc_error:
                        print(f"      ⚠️ 문서 정보 조회 실패: {doc_error}")

                results.append(chunk_data)

            print(f"✅ 최종 결과: {len(results)}개 반환\n")
            return results

        except Exception as e:
            print(f"❌ 검색 오류: {e}")
            import traceback
            traceback.print_exc()
            return []


        # ==================== messages ====================

    def save_message(self, user_id: str, user_query: str, ai_response: str,
                     source_chunk_ids: Optional[List[str]] = None,
                     usage: Optional[Dict] = None) -> Dict[str, Any]:
        """메시지 저장"""
        data = {
            "user_id": user_id,
            "user_query": user_query,
            "ai_response": ai_response,
            "source_chunk_ids": source_chunk_ids or [],
            "usage": usage or {}
        }
        try:
            response = self.client.table("messages").insert(data).execute()
            return response.data[0] if response.data else {}
        except Exception as e:
            print(f"⚠️ 메시지 저장 실패: {e}")
            return {}
# 글로벌 인스턴스
supabase_service = SupabaseService()
