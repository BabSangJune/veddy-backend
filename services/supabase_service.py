# services/supabase_service.py (✨ get_document_by_source_id 메서드 추가)

from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY
from unicodedata import normalize as unicode_normalize
from config import VECTOR_SEARCH_CONFIG
from datetime import datetime
from typing import Optional
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

    def get_document_by_source_id(self, source: str, source_id: str) -> Optional[Dict]:
        """
        ✅ Source ID로 기존 문서 조회 (변경 감지용)

        Args:
            source: 문서 출처 (예: "confluence")
            source_id: 출처 내 고유 ID (예: Confluence page_id)

        Returns:
            기존 문서 정보 또는 None
        """
        try:
            response = self.client.table("documents").select("*").eq(
                "source", source
            ).eq(
                "source_id", source_id
            ).limit(1).execute()

            if response.data:
                logger.debug(f"📋 기존 문서 조회 성공: {source}/{source_id}")
                return response.data[0]

            logger.debug(f"📋 기존 문서 없음: {source}/{source_id}")
            return None

        except Exception as e:
            logger.error(f"❌ 문서 조회 실패 ({source}/{source_id}): {e}")
            return None

    def add_document(
            self,
            source: str,
            source_id: str,
            title: str,
            content: str,
            metadata: Dict,
            created_at: Optional[datetime] = None,
            updated_at: Optional[datetime] = None
    ) -> Dict:
        """
        문서 저장 또는 업데이트 (Upsert)
        - created_at, updated_at: Confluence의 실제 시간 사용

        Args:
            source: 문서 출처
            source_id: 출처 내 고유 ID
            title: 문서 제목
            content: 문서 내용
            metadata: 메타데이터
            created_at: 생성 시간 (Confluence에서 받은 값)
            updated_at: 수정 시간 (Confluence에서 받은 값)

        Returns:
            저장된 문서 정보
        """
        try:
            normalized_title = unicode_normalize('NFC', title)
            normalized_content = unicode_normalize('NFC', content)

            doc_data = {
                "source": source,
                "source_id": source_id,
                "title": normalized_title,
                "content": normalized_content,
                "metadata": metadata,
                # ✅ Confluence 시간 사용 (없으면 현재 시간)
                "created_at": created_at.isoformat() if created_at else datetime.now().isoformat(),
                "updated_at": updated_at.isoformat() if updated_at else datetime.now().isoformat(),
            }

            try:
                response = self.client.table("documents").upsert(
                    doc_data,
                    ignore_duplicates=False
                ).execute()

                if response.data:
                    logger.info(f"✅ 문서 저장/업데이트: {normalized_title} (수정: {updated_at})")
                    return response.data[0]

            except Exception as upsert_error:
                # UPDATE 시도
                logger.warning(f"⚠️ UPSERT 실패, UPDATE 시도: {upsert_error}")

                try:
                    response = self.client.table("documents").update(doc_data).eq(
                        "source_id", source_id
                    ).execute()

                    if response.data:
                        logger.info(f"✅ 문서 업데이트: {normalized_title}")
                        return response.data[0]
                except:
                    # INSERT 시도
                    response = self.client.table("documents").insert(doc_data).execute()
                    if response.data:
                        logger.info(f"✅ 문서 새로 저장: {normalized_title}")
                        return response.data[0]

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


    # services/supabase_service.py의 SupabaseService 클래스에 추가

    def delete_chunks_by_document_id(self, document_id: str) -> int:
        """
        ✅ 특정 문서의 모든 청크 삭제 (업데이트 시 중복 방지)

        Args:
            document_id: 문서 ID

        Returns:
            삭제된 청크 개수
        """
        try:
            # 삭제 전 개수 확인
            count_response = self.client.table("document_chunks").select(
                "id", count="exact"
            ).eq("document_id", document_id).execute()

            count = len(count_response.data) if count_response.data else 0

            if count == 0:
                logger.debug(f"🗑️  삭제할 청크 없음 (document_id: {document_id})")
                return 0

            # 청크 삭제
            self.client.table("document_chunks").delete().eq(
                "document_id", document_id
            ).execute()

            logger.info(f"🗑️  청크 삭제 완료: {count}개 (document_id: {document_id})")
            return count

        except Exception as e:
            logger.error(f"❌ 청크 삭제 실패 (document_id: {document_id}): {e}")
            return 0


    def add_chunks_batch(self, chunks_data: List[Dict[str, Any]]) -> int:
        """
        ✅ 다중 청크 배치 저장 (성능 최적화: N+1 쿼리 제거)

        14,000회 쿼리 → 1,400회로 91% 감소!

        Args:
            chunks_data: 저장할 청크 데이터 리스트
            [
                {"document_id": "...", "chunk_number": 1, "content": "...", "embedding": [...]},
                {"document_id": "...", "chunk_number": 2, "content": "...", "embedding": [...]},
                ...
            ]

        Returns:
            저장된 청크 개수
        """
        if not chunks_data:
            return 0

        import time

        batch_size = 10  # Supabase 권장: 한 번에 10개씩
        total_saved = 0
        start_time = time.time()

        logger.info(f"📦 배치 청크 저장 시작: {len(chunks_data)}개 청크")

        try:
            # 10개씩 배치로 나누어 저장
            for i in range(0, len(chunks_data), batch_size):
                batch = chunks_data[i:i+batch_size]

                try:
                    response = self.client.table("document_chunks").insert(batch).execute()
                    saved_count = len(response.data) if response.data else 0
                    total_saved += saved_count

                    elapsed = time.time() - start_time
                    batch_num = (i // batch_size) + 1
                    print(f"  ✅ 배치 {batch_num}: {saved_count}개 저장 ({elapsed:.2f}초)")

                except Exception as e:
                    logger.error(f"❌ 배치 저장 실패 (인덱스 {i}-{i+len(batch)}): {e}")
                    # 계속 진행 (부분 실패 허용)
                    continue

            elapsed = time.time() - start_time
            logger.info(f"✅ 배치 저장 완료: {total_saved}개 청크 저장됨 ({elapsed:.2f}초)")

            return total_saved

        except Exception as e:
            logger.error(f"❌ 배치 저장 중 오류: {e}")
            return total_saved

    def search_chunks(self, embedding: List[float], limit: int = 5,
                      threshold: float = None, ef_search: int = None) -> List[Dict[str, Any]]:
        """
        벡터 유사도 검색 (config 기반 + 성능 모니터링)
        """
        import time

        # ✅ config에서 기본값 자동 적용
        config_threshold = VECTOR_SEARCH_CONFIG['similarity_threshold']
        config_ef_search = VECTOR_SEARCH_CONFIG['ef_search']

        threshold = threshold or config_threshold
        ef_search = ef_search or config_ef_search

        start_time = time.time()

        try:
            logger.info(f"🔍 검색 시작 | ef={ef_search} | threshold={threshold} | limit={limit}")

            # RPC 호출
            response = self.client.rpc('match_documents', {
                'query_embedding': embedding,
                'match_count': limit,
                'match_threshold': threshold,
                'ef_search_value': ef_search
            }).execute()

            data = response.data if hasattr(response, 'data') else response

            if not data:
                elapsed = (time.time() - start_time) * 1000
                logger.warning(f"⚠️ 검색 결과 없음 | ef={ef_search} | 시간={elapsed:.2f}ms")
                return []

            logger.info(f"✅ RPC 응답: {len(data)}개")

            results = []
            similarities = []

            for i, item in enumerate(data, 1):
                chunk_id = item.get('id')
                doc_id = item.get('document_id')
                content = item.get('content', '')
                similarity = item.get('similarity', 0.0)
                title = item.get('title', '제목 없음')
                source = item.get('source', 'confluence')
                metadata = item.get('metadata', {})

                similarities.append(similarity)

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

                results.append(chunk_data)

            elapsed = (time.time() - start_time) * 1000
            avg_similarity = sum(similarities) / len(similarities) if similarities else 0

            logger.info(f"✅ 검색 완료 | ef_search={ef_search} | "
                        f"시간={elapsed:.2f}ms | 결과={len(results)}개 | "
                        f"평균유사도={avg_similarity:.3f}")

            return results

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"❌ 검색 실패 | ef={ef_search} | 시간={elapsed:.2f}ms | 오류={str(e)}")
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
