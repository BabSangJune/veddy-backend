# services/token_chunk_service.py
from transformers import AutoTokenizer
from typing import List
import logging

logger = logging.getLogger(__name__)

class TokenChunkService:
    """
    dragonkue/BGE-m3-ko 토크나이저 기반 토큰 청킹 서비스
    """

    def __init__(self, model_name: str = "dragonkue/BGE-m3-ko"):
        """
        초기화: 토크나이저 로드 (한 번만)
        """
        logger.info(f"🔧 TokenChunkService 초기화 중: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model_name = model_name
        logger.info("✅ TokenChunkService 초기화 완료")

    def chunk_text(
            self,
            text: str,
            chunk_tokens: int = 400,
            overlap_tokens: int = 50,
            min_chunk_tokens: int = 50
    ) -> List[str]:
        """
        토큰 기반 텍스트 청킹

        Args:
            text: 입력 텍스트
            chunk_tokens: 청크당 토큰 수 (권장: 300-512)
            overlap_tokens: 오버랩 토큰 수 (권장: 50-100)
            min_chunk_tokens: 최소 토큰 수 (너무 짧은 청크 필터링)

        Returns:
            청크 리스트
        """
        if not text or not text.strip():
            return []

        logger.debug(f"📄 청킹 시작: {len(text)}자, target={chunk_tokens}tokens")

        # 1. 토큰화 (특수 토큰 제외)
        tokens = self.tokenizer.encode(
            text,
            add_special_tokens=False,
            truncation=False
        )

        logger.debug(f"🔢 토큰화 완료: {len(tokens)} tokens")

        # 2. 청크 생성
        chunks = []
        start = 0

        while start < len(tokens):
            # 청크 토큰 범위
            end = min(start + chunk_tokens, len(tokens))
            chunk_token_ids = tokens[start:end]

            # 토큰 → 텍스트 디코딩
            chunk_text = self.tokenizer.decode(
                chunk_token_ids,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True
            )

            # 최소 토큰 수 체크
            chunk_token_len = len(chunk_token_ids)
            if chunk_token_len >= min_chunk_tokens and chunk_text.strip():
                chunks.append(chunk_text.strip())
                logger.debug(f"✅ 청크 생성: {chunk_token_len}tokens")

            # 다음 시작점 (오버랩 적용)
            start = end - overlap_tokens

            # 마지막 청크 처리
            if end >= len(tokens):
                break

        logger.info(f"✅ 청킹 완료: {len(chunks)}개 청크 생성")
        return chunks

    def get_text_stats(self, text: str) -> dict:
        """텍스트 통계 (디버깅용)"""
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        return {
            'char_count': len(text),
            'token_count': len(tokens),
            'avg_tokens_per_char': len(tokens) / len(text) if text else 0
        }

# 글로벌 싱글톤 인스턴스
token_chunk_service = TokenChunkService()
