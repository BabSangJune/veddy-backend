# backend/services/reranker_service.py

from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
import torch
import logging
from config import RERANKER_CONFIG

logger = logging.getLogger(__name__)

class RerankerService:
    """
    Cross-Encoder 기반 리랭킹 서비스
    dragonkue/bge-reranker-v2-m3-ko 모델 사용
    """

    def __init__(self, model_name: str = None):
        """리랭커 초기화"""
        # 🆕 config 우선 사용
        model_name = model_name or RERANKER_CONFIG['model_name']
        max_length = RERANKER_CONFIG['max_length']

        logger.info(f"🔧 리랭커 모델 로딩 중: {model_name}")

        try:
            self.model = CrossEncoder(
                model_name,
                max_length=max_length,
                activation_fct=torch.nn.Sigmoid()  # ✅ 경고 제거 (변경됨)
            )
            logger.info("✅ 리랭커 모델 로딩 완료")
        except Exception as e:
            logger.error(f"❌ 리랭커 모델 로딩 실패: {e}")
            raise

    def rerank(
            self,
            query: str,
            chunks: List[Dict[str, Any]],
            top_k: int = None  # 🆕 None이면 config에서 가져오기
    ) -> List[Dict[str, Any]]:
        """
        검색 결과를 리랭킹
        """
        # 🆕 config에서 top_k 가져오기
        if top_k is None:
            top_k = RERANKER_CONFIG['top_k']

        if not chunks:
            return []

        try:
            # 1. 쿼리-청크 페어 생성
            pairs = []
            for chunk in chunks:
                content = chunk.get('content', '')
                pairs.append([query, content])

            # 2. Cross-Encoder 스코어 계산
            logger.info(f"🔍 리랭킹 시작 (청크 수: {len(pairs)})")
            scores = self.model.predict(pairs)

            # 3. 스코어를 청크에 추가
            for i, chunk in enumerate(chunks):
                chunk['rerank_score'] = float(scores[i])

            # 4. 스코어 순으로 정렬
            reranked = sorted(
                chunks,
                key=lambda x: x.get('rerank_score', 0),
                reverse=True
            )[:top_k]

            logger.info(f"✅ 리랭킹 완료 (상위 {top_k}개 반환)")

            # 5. 디버그 로그 (점수 비교)
            for i, chunk in enumerate(reranked, 1):
                original_score = chunk.get('score', 0)
                rerank_score = chunk.get('rerank_score', 0)
                logger.debug(
                    f"  #{i} | 원본: {original_score:.4f} → 리랭크: {rerank_score:.4f} | "
                    f"{chunk.get('title', 'N/A')[:30]}"
                )

            return reranked

        except Exception as e:
            logger.error(f"❌ 리랭킹 오류: {e}", exc_info=True)
            # 오류 시 원본 반환
            return chunks[:top_k]


# 글로벌 인스턴스 (싱글톤)
_reranker_instance = None

def get_reranker_service() -> RerankerService:
    """리랭커 서비스 싱글톤 반환"""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = RerankerService()
    return _reranker_instance


# 편의 함수
reranker_service = get_reranker_service()
