from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
from config import EMBEDDING_MODEL_NAME, EMBEDDING_MODEL_DIMENSION


class EmbeddingService:
    def __init__(self):
        """BGE-m3-ko 모델 로드"""
        print(f"📚 Embedding 모델 로드 중: {EMBEDDING_MODEL_NAME}")
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("✅ Embedding 모델 로드 완료")

    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트를 벡터로 변환"""
        embedding = self.model.encode(text, convert_to_tensor=False)
        return embedding.astype(np.float32).tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트를 한 번에 벡터로 변환 (효율적)"""
        embeddings = self.model.encode(texts, convert_to_tensor=False)
        return [emb.astype(np.float32).tolist() for emb in embeddings]


# 글로벌 인스턴스 (앱 시작 시 한 번만 로드)
embedding_service = EmbeddingService()
