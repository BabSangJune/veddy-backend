# backend/services/reranker_service.py (✅ CrossEncoder 버전 호환 완료)

from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
import torch
import logging
from config import RERANKER_CONFIG

logger = logging.getLogger(__name__)

class RerankerService:
    """
    Cross-Encoder 기반 리랭킹 서비스 (버전 호환)
    dragonkue/bge-reranker-v2-m3-ko 모델 사용
    """

    def __init__(self, model_name: str = None):
        """리랭커 초기화 (버전 호환)"""
        # 🆕 config 우선 사용
        model_name = model_name or RERANKER_CONFIG['model_name']
        max_length = RERANKER_CONFIG['max_length']

        logger.info(f"🔧 리랭커 모델 로딩 중: {model_name}")

        try:
            # ✅ 최신 버전 시도 (3.0+)
            try:
                self.model = CrossEncoder(
                    model_name,
                    max_length=max_length,
                    default_activation_function=torch.nn.Sigmoid()
                )
                logger.info("✅ 리랭커 모델 로딩 완료 (new API v3+)")
            except TypeError:
                # ✅ 구버전 fallback (2.x)
                self.model = CrossEncoder(
                    model_name,
                    max_length=max_length,
                    activation_fct=torch.nn.Sigmoid()
                )
                logger.info("✅ 리랭커 모델 로딩 완료 (legacy API v2.x)")
        except Exception as e:
            logger.error(f"❌ 리랭커 모델 로딩 실패: {e}")
            raise

    def rerank(
            self,
            query: str,
            chunks: List[Dict[str, Any]],
            top_k: int = None
    ) -> List[Dict[str, Any]]:
        """검색 결과를 리랭킹 (기존 코드 그대로)"""
        if top_k is None:
            top_k = RERANKER_CONFIG['top_k']

        if not chunks:
            return []

        try:
            pairs = []
            for chunk in chunks:
                content = chunk.get('content', '')
                pairs.append([query, content])

            logger.info(f"🔍 리랭킹 시작 (청크 수: {len(pairs)})")
            scores = self.model.predict(pairs)

            for i, chunk in enumerate(chunks):
                chunk['rerank_score'] = float(scores[i])

            reranked = sorted(
                chunks,
                key=lambda x: x.get('rerank_score', 0),
                reverse=True
            )[:top_k]

            logger.info(f"✅ 리랭킹 완료 (상위 {top_k}개 반환)")

            # 디버그 로그
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
            return chunks[:top_k]

# 글로벌 싱글톤
_reranker_instance = None

def get_reranker_service() -> RerankerService:
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = RerankerService()
    return _reranker_instance

reranker_service = get_reranker_service()
