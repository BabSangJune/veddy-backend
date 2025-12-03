# services/supabase_service.py

from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY
from unicodedata import normalize as unicode_normalize
import logging

logger = logging.getLogger(__name__)

class SupabaseService:
    # ✅ 클래스 레벨 클라이언트 (싱글톤)
    _service_role_client: Optional[Client] = None

    def __init__(self, access_token: Optional[str] = None):
        """
        Supabase 클라이언트 초기화

        Args:
            access_token: 사용자 JWT 토큰 (None이면 Service Role 사용)
        """
        if access_token:
            # 🔐 사용자 토큰으로 클라이언트 생성 (RLS 적용됨)
            self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            self.client.postgrest.auth(access_token)
            logger.info("✅ Supabase 사용자 클라이언트 초기화 (RLS 활성화)")
        else:
            # 🔑 Service Role 클라이언트 (관리자용, RLS 우회)
            # ✅ 클래스 레벨 싱글톤 재사용
            if SupabaseService._service_role_client is None:
                SupabaseService._service_role_client = create_client(
                    SUPABASE_URL,
                    SUPABASE_SERVICE_ROLE_KEY
                )
                logger.info("✅ Supabase Service Role 클라이언트 초기화 (최초)")
            else:
                logger.debug("♻️  기존 Service Role 클라이언트 재사용")

            self.client = SupabaseService._service_role_client

    def test_connection(self) -> bool:
        """Supabase 연결 테스트"""
        try:
            response = self.client.table("documents").select("id").limit(1).execute()
            logger.info("✅ Supabase 연결 테스트 성공")
            return True
        except Exception as e:
            logger.error(f"❌ 연결 테스트 실패: {e}")
            return False

    # ==================== documents ====================

    def add_document(self, source: str, source_id: str, title: str, content: str, metadata: Dict) -> Dict:
        """
        문서 저장 (✅ 정규화 추가)
        """
        try:
            # ✅ 저장 전 유니코드 정규화 (NFC)
            normalized_title = unicode_normalize('NFC', title)
            normalized_content = unicode_normalize('NFC', content)

            doc_data = {
                "source": source,
                "source_id": source_id,
                "title": normalized_title,
                "content": normalized_content,
                "metadata": metadata
            }

            response = self.client.table("documents").insert(doc_data).execute()

            if response:
                logger.info(f"✅ 문서 저장: {normalized_title}")
                return response.data[0]
            else:
                logger.error(f"❌ 문서 저장 실패")
                return {}

        except Exception as e:
            logger.error(f"❌ 문서 저장 중 오류: {e}")
            raise

    def list_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """문서 목록"""
        try:
            response = self.client.table("documents").select("*").eq(
                "is_active", True
            ).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ 목록 조회 실패: {e}")
            return []

    # ==================== chunks ====================

    def add_chunk(self, document_id: str, chunk_number: int, content: str, embedding: List[float]) -> Dict:
        """
        문서 청크 저장 (✅ 정규화 추가)
        """
        try:
            # ✅ 저장 전 유니코드 정규화 (NFC)
            normalized_content = unicode_normalize('NFC', content)

            chunk_data = {
                "document_id": document_id,
                "chunk_number": chunk_number,
                "content": normalized_content,
                "embedding": embedding
            }

            response = self.client.table("document_chunks").insert(chunk_data).execute()

            if response:
                return response.data[0]
            else:
                logger.error(f"❌ 청크 저장 실패")
                return {}

        except Exception as e:
            logger.error(f"❌ 청크 저장 중 오류: {e}")
            raise

    def search_chunks(self, embedding: List[float], limit: int = 5,
                      threshold: float = 0.2, ef_search: int = 50) -> List[Dict[str, Any]]:
        """
        벡터 유사도 검색 (HNSW ef_search 지원)

        Args:
            embedding: 쿼리 임베딩 벡터
            limit: 반환할 최대 결과 수
            threshold: 유사도 임계값 (0~1)
            ef_search: HNSW 검색 품질 파라미터 (20~100)
                       20-30: 빠른 검색
                       50-60: 균형 (기본 추천)
                       80-100: 정확도 우선

        Returns:
            검색된 청크 목록
        """
        try:
            logger.info(f"🔍 검색 시작 (limit={limit}, threshold={threshold}, ef_search={ef_search})")

            # RPC 호출 (ef_search 파라미터 추가)
            response = self.client.rpc('match_documents', {
                'query_embedding': embedding,
                'match_count': limit,
                'match_threshold': threshold,
                'ef_search_value': ef_search  # ✅ 추가
            }).execute()

            # response.data 추출
            data = response.data if hasattr(response, 'data') else response

            if not data:
                logger.warning("⚠️ 검색 결과 없음")
                return []

            logger.info(f"✅ RPC 응답: {len(data)}개")

            results = []
            for i, item in enumerate(data, 1):
                chunk_id = item.get('id')
                doc_id = item.get('document_id')
                content = item.get('content', '')
                similarity = item.get('similarity', 0.0)
                title = item.get('title', '제목 없음')
                source = item.get('source', 'confluence')
                metadata = item.get('metadata', {})

                logger.debug(f" [{i}] chunk_id={chunk_id}, doc_id={doc_id}, sim={similarity:.3f}")

                # 청크 데이터 구성
                chunk_data = {
                    'id': chunk_id,
                    'document_id': doc_id,
                    'content': content,
                    'similarity': similarity,
                    'title': title,
                    'source': source,
                    'url': metadata.get('url') or metadata.get('page_url', ''),
                    'metadata': metadata
                }

                if chunk_data['url']:
                    logger.debug(f" 🔗 URL: {chunk_data['url']}")

                results.append(chunk_data)

            logger.info(f"✅ 최종 결과: {len(results)}개 반환")
            return results

        except Exception as e:
            logger.error(f"❌ 검색 오류: {e}")
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
            logger.error(f"⚠️ 메시지 저장 실패: {e}")
            return {}

# ✅ 글로벌 인스턴스 (Service Role - 관리용)
supabase_service = SupabaseService()
