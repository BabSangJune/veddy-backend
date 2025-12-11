from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
import time
from config import EMBEDDING_MODEL_NAME, EMBEDDING_MODEL_DIMENSION, EMBEDDING_BATCH_SIZE


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

    def embed_batch(self, texts: List[str], batch_size: int = None) -> List[List[float]]:
        """
        배치 임베딩 (메모리 효율적 - 2000+ 문서 지원)

        Args:
            texts: 임베딩할 텍스트 리스트
            batch_size: 한 번에 처리할 텍스트 개수 (기본: EMBEDDING_BATCH_SIZE=32)

        Returns:
            임베딩 벡터 리스트
        """
        if not texts:
            return []

        batch_size = batch_size or EMBEDDING_BATCH_SIZE
        all_embeddings = []

        print(f"🔤 배치 임베딩 시작: {len(texts)}개 텍스트 | 배치크기={batch_size}")
        start_time = time.time()

        # 배치로 나누어 처리 (메모리 효율성)
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]

            try:
                embeddings = self.model.encode(batch, convert_to_tensor=False)
                all_embeddings.extend([emb.astype(np.float32).tolist() for emb in embeddings])

                progress = min(i + batch_size, len(texts))
                elapsed = time.time() - start_time
                progress_percent = (progress / len(texts)) * 100
                print(f"  ✅ 진행: {progress}/{len(texts)} ({progress_percent:.1f}%) | {elapsed:.2f}초")

            except Exception as e:
                print(f"  ❌ 배치 임베딩 실패 (인덱스 {i}-{i+len(batch)}): {e}")
                raise

        total_time = time.time() - start_time
        print(f"✅ 배치 임베딩 완료: {len(all_embeddings)}개 | 소요시간: {total_time:.2f}초")

        return all_embeddings


# 글로벌 인스턴스 (앱 시작 시 한 번만 로드)
embedding_service = EmbeddingService()
