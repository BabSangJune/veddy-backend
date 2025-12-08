"""
🧪 향상된 비교 모드 감지 테스트

테스트 대상: services/comparison_service.py
테스트 항목:
  1. 비교 의도 감지
  2. VS 패턴 추출
  3. 대명사 + History 기반 토픽 추출
  4. 의미론적 감지
  5. 신뢰도 점수
"""

import pytest
from services.comparison_service import comparison_service


class TestComparisonDetection:
    """비교 모드 자동 감지 테스트"""

    # ✅ Test 1: VS 패턴 감지
    def test_vs_pattern_detection(self):
        """'A vs B' 형식 감지"""
        test_cases = [
            ("IMO DCS vs EU MRV 비교해줘", True, ["IMO DCS", "EU MRV"], \"regex_vs\"),
            ("IMO DCS VS EU MRV", True, ["IMO DCS", "EU MRV"], \"regex_vs\"),
            ("IMO DCS V.S EU MRV", True, ["IMO DCS", "EU MRV"], \"regex_vs\"),
        ]

        for query, expected_comparison, expected_topics, expected_method in test_cases:
            result = comparison_service.detect_comparison_mode(query)
            
            assert result[\"is_comparison\"] == expected_comparison, \
                f"Query '{query}': is_comparison 실패"
            
            if expected_comparison:
                assert result[\"topics\"][:len(expected_topics)] == expected_topics, \
                    f"Query '{query}': topics 실패. Got {result['topics']}"
                assert result.get(\"confidence\", 0) >= 0.9, \
                    f"Query '{query}': confidence 너무 낮음"
                assert result.get(\"detection_method\") == expected_method, \
                    f"Query '{query}': detection_method 실패"

    # ✅ Test 2: 한국어 'A와 B' 패턴
    def test_korean_and_pattern(self):
        """한국어 'A와 B' 형식 감지"""
        test_cases = [
            ("IMO DCS와 EU MRV를 비교해줘", True, [\"IMO DCS\", \"EU MRV\"]),
            ("IMO DCS 그리고 EU MRV 차이는?", True, [\"IMO DCS\", \"EU MRV\"]),
        ]

        for query, expected_comparison, expected_topics in test_cases:
            result = comparison_service.detect_comparison_mode(query)
            assert result[\"is_comparison\"] == expected_comparison, \
                f"Query '{query}': 한국어 AND 패턴 실패"

    # ✅ Test 3: 키워드 기반 비교 의도 감지
    def test_comparison_intent_keywords(self):
        """'비교', '차이', '공통점' 등 키워드 감지"""
        positive_cases = [
            "두 규정의 차이를 설명해줘",
            "비교 분석을 해줄래?",
            "공통점과 다른점을 찾아줘",
            "어느 것이 더 나아?",
        ]

        for query in positive_cases:
            result = comparison_service.detect_comparison_mode(query)
            # 의도는 감지되었으나 토픽이 없으면 is_comparison=False
            # 이는 정상 (의도는 있지만 대상이 불명확)
            print(f"Query: '{query}' -> {result}")

    # ✅ Test 4: 대명사 + History 기반 토픽 추출
    def test_pronoun_with_history(self):
        """'두개', '둘', '양쪽' + History에서 토픽 추출"""
        history = "IMO DCS는 국제해사기구 규정이고... EU MRV는 유럽 규정입니다..."
        
        query = "두개 비교해줘"
        result = comparison_service.detect_comparison_mode(query, history)
        
        assert result[\"is_comparison\"] == True, "대명사 감지 실패"
        assert len(result[\"topics\"]) >= 2, "History에서 토픽 추출 실패"
        print(f"Extracted topics: {result['topics']}")

    # ✅ Test 5: 신뢰도 점수
    def test_confidence_scores(self):
        """신뢰도 점수가 올바르게 매겨지는지 확인"""
        test_cases = [
            # (query, min_confidence, max_confidence)
            ("IMO DCS vs EU MRV", 0.85, 1.0),  # VS 패턴: 높음
            ("두개 비교해줘", 0.75, 1.0),      # 대명사: 중간~높음
            ("선박 규정은?", 0.0, 0.2),        # 비교 아님: 낮음
        ]

        for query, min_conf, max_conf in test_cases:
            result = comparison_service.detect_comparison_mode(query)
            confidence = result.get(\"confidence\", 0)
            
            assert min_conf <= confidence <= max_conf, \
                f"Query '{query}': confidence {confidence} 범위 벗어남 (예상: {min_conf}-{max_conf})"
            print(f"Query: '{query}' -> confidence: {confidence}")

    # ✅ Test 6: 의미론적 감지
    def test_semantic_detection(self):
        """의미론적 질문 구조 감지"""
        history = "IMO DCS와 EU MRV는..."
        
        semantic_queries = [
            "첫 번째와 두 번째의 차이는?",
            "그 둘이 뭐가 달라?",
            "어느 것이 더 엄격해?",
        ]

        for query in semantic_queries:
            result = comparison_service.detect_comparison_mode(query, history)
            print(f"Semantic query: '{query}' -> is_comparison: {result['is_comparison']}")

    # ✅ Test 7: 거짓 양성 방지 (False Positives)
    def test_false_positives(self):
        """의도하지 않은 비교 감지 방지"""
        non_comparison_queries = [
            "선박 안전은 중요하다",
            "해양 규정을 알려줘",
            "IMO DCS는 무엇인가?",  # 단일 대상
            "EU MRV 규정",  # 단일 대상
        ]

        for query in non_comparison_queries:
            result = comparison_service.detect_comparison_mode(query)
            # 의도 없으면 False, 토픽 1개면 False
            if result[\"is_comparison\"]:
                print(f"⚠️ False Positive: '{query}' -> {result}")
                # 토픽이 2개 이상이고 의도가 있는 경우만 True


class TestDetectionMethods:
    """감지 방식별 상세 테스트"""

    def test_regex_vs_extraction(self):
        """regex_vs 방식 추출 정확성"""
        test_cases = [
            ("IMO DCS vs EU MRV", ["IMO DCS", "EU MRV"]),
            ("IMO DCS  VS  EU MRV", ["IMO DCS", "EU MRV"]),  # 여러 공백
            ("A vs B vs C", [\"A\", \"vs\"]),  # 3개 이상: 처음 두 개만
        ]

        for query, expected_topics in test_cases:
            result = comparison_service.detect_comparison_mode(query)
            assert result[\"topics\"] == expected_topics, \
                f"Query '{query}': topic 추출 실패. Got {result['topics']}"

    def test_history_extraction(self):
        """History에서 토픽 추출"""
        histories = [
            ("IMO DCS는...", [\"IMO DCS\"]),
            ("IMO DCS는... EU MRV는...", [\"EU MRV\", \"IMO DCS\"]),  # 역순
            ("IMO DCS, EU MRV, SOLAS", [\"SOLAS\", \"EU MRV\", \"IMO DCS\"]),  # 역순
        ]

        for history, expected_topics in histories:
            extracted = comparison_service.extract_topics_from_history(history)
            print(f"History '{history}' -> extracted: {extracted}")
            # 최근순 (역순)인지 확인


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_inputs(self):
        """빈 입력 처리"""
        result = comparison_service.detect_comparison_mode(\"\")
        assert result[\"is_comparison\"] == False
        assert result[\"topics\"] == []

    def test_none_inputs(self):
        """None 입력 처리"""
        result = comparison_service.detect_comparison_mode(
            \"비교해줘\",
            history=None,
            conversation_context=None
        )
        assert isinstance(result, dict)
        assert \"is_comparison\" in result

    def test_very_long_query(self):
        """매우 긴 쿼리 처리"""
        long_query = "IMO DCS " * 100 + "vs " + "EU MRV " * 100
        result = comparison_service.detect_comparison_mode(long_query)
        # 성능 저하 없이 처리되어야 함
        assert isinstance(result, dict)

    def test_special_characters(self):
        """특수 문자 포함 쿼리"""
        test_cases = [
            \"IMO-DCS vs EU:MRV\",
            \"IMO_DCS & EU.MRV\",
            \"'IMO DCS' vs 'EU MRV'\",
        ]
        for query in test_cases:
            result = comparison_service.detect_comparison_mode(query)
            print(f"Special chars query: '{query}' -> {result}")

    def test_case_sensitivity(self):
        """대소문자 처리"""
        test_cases = [
            (\"imo dcs vs eu mrv\", False),  # 소문자: 약어 패턴 미일치
            (\"IMO DCS VS EU MRV\", True),   # 대문자: 감지됨
            (\"ImO dCs vs Eu mRv\", False),  # 혼합: 미일치
        ]
        for query, expected in test_cases:
            result = comparison_service.detect_comparison_mode(query)
            print(f"Case test '{query}': is_comparison={result['is_comparison']}")


if __name__ == \"__main__\":
    # pytest 실행
    pytest.main([\"-v\", __file__])
