# benchmark_ef_search.py
import time
import asyncio
from typing import List, Dict
from services.embedding_service import embedding_service
from services.supabase_service import supabase_service

# 테스트용 질문들 (실제 사용 사례 반영)
TEST_QUERIES = [
    "휴가 신청 방법",
    "IMO DCS",
    "EU MRV",
    "FOR SHIP",
    "FOR SHORE"
]

def benchmark_single_query(query: str, ef_search: int) -> Dict:
    """단일 쿼리 벤치마크"""
    try:
        # 1. 임베딩 생성
        query_embedding = embedding_service.embed_text(query)

        # 2. 검색 시간 측정
        start_time = time.time()
        results = supabase_service.search_chunks(
            embedding=query_embedding,
            limit=5,
            threshold=0.3,
            ef_search=ef_search
        )
        elapsed = time.time() - start_time

        # 3. 결과 분석
        avg_similarity = sum(r.get('similarity', 0) for r in results) / len(results) if results else 0

        return {
            'query': query,
            'ef_search': ef_search,
            'time_ms': round(elapsed * 1000, 2),
            'result_count': len(results),
            'avg_similarity': round(avg_similarity, 3)
        }
    except Exception as e:
        print(f"❌ 오류: {e}")
        return None

def run_benchmark():
    """전체 벤치마크 실행"""
    print("=" * 70)
    print("🧪 HNSW ef_search 벤치마크 시작")
    print("=" * 70)

    # 테스트할 ef_search 값들
    ef_values = [20, 40, 50, 60, 80, 100]

    all_results = []

    for ef in ef_values:
        print(f"\n📊 ef_search = {ef}")
        print("-" * 70)

        ef_results = []
        for query in TEST_QUERIES:
            result = benchmark_single_query(query, ef)
            if result:
                ef_results.append(result)
                print(f"  {query:20s} | {result['time_ms']:6.2f}ms | "
                      f"{result['result_count']}개 | 유사도 {result['avg_similarity']:.3f}")

        # 평균 계산
        avg_time = sum(r['time_ms'] for r in ef_results) / len(ef_results)
        avg_similarity = sum(r['avg_similarity'] for r in ef_results) / len(ef_results)

        print(f"\n  ⚡ 평균: {avg_time:.2f}ms | 평균 유사도: {avg_similarity:.3f}")

        all_results.append({
            'ef_search': ef,
            'avg_time_ms': round(avg_time, 2),
            'avg_similarity': round(avg_similarity, 3),
            'queries': ef_results
        })

    # 최종 요약
    print("\n" + "=" * 70)
    print("📈 최종 요약")
    print("=" * 70)
    print(f"{'ef_search':<12} {'평균 속도':<15} {'평균 유사도':<15} {'권장 상황'}")
    print("-" * 70)

    for result in all_results:
        ef = result['ef_search']
        time_ms = result['avg_time_ms']
        similarity = result['avg_similarity']

        # 권장 상황
        if ef <= 30:
            recommendation = "⚡ 실시간 대화"
        elif ef <= 60:
            recommendation = "⚖️ 균형 (추천)"
        else:
            recommendation = "🎯 정확도 우선"

        print(f"{ef:<12} {time_ms:.2f}ms{'':<9} {similarity:.3f}{'':<9} {recommendation}")

    print("=" * 70)

    return all_results

if __name__ == "__main__":
    results = run_benchmark()
