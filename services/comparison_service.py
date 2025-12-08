# services/comparison_service.py
"""
🔍 비교 모드 전담 서비스
역할:
- 비교 쿼리 자동 감지
- History에서 토픽 추출
- 비교 컨텍스트 생성

책임: 비교 기능만 담당 (독립적, 테스트 용이)
"""

from typing import Dict, List
from logging_config import get_logger
import re
import json

logger = get_logger(__name__)

class ComparisonService:
    """비교 모드 전담 서비스 (자동 감지 강화)"""

    # 비교 감지 키워드 (더 상세함)
    COMPARISON_KEYWORDS = [
        "비교", "차이", "다른점", "공통점", "차별점",
        "vs", "VS", "V.S", "와", "그리고",  # ← "와" 추가
        "비교하", "비교해", "차이를", "다르", "같은",
    ]

    PRONOUN_KEYWORDS = [
        "두개", "둘", "양쪽", "이 두", "저 두",
        "둘 다", "양쪽 모두", "이것과 저것",
        "첫번째와 두번째", "그리고",
    ]

    # 용어 정규화 (IMO DCS, IMO_DCS, IMODCS 모두 감지)
    ACRONYM_PATTERN = r'([A-Z][A-Z0-9]*(?:\s+[A-Z][A-Z0-9]*)?)'

    @staticmethod
    def detect_comparison_mode(
            query: str,
            history: str = "",
            conversation_context: List[Dict] = None
    ) -> Dict:
        """
        향상된 비교 모드 감지

        인자:
        - query: 현재 사용자 쿼리
        - history: 텍스트 형태 History
        - conversation_context: Message 객체 리스트 (구조화된 History)

        반환:
        {
            "is_comparison": bool,
            "topics": [str, str],
            "confidence": float,  # ← 신뢰도 추가
            "detection_method": str  # "regex" | "keyword" | "history" | "semantic"
        }
        """

        logger.debug(f"🔍 비교 모드 감지 시작", extra={
            "query_len": len(query),
            "has_history": bool(history),
        })

        # ✅ Step 1: 비교 의도 확인 (필수)
        is_comparison_intent = ComparisonService._check_comparison_intent(query)

        if not is_comparison_intent:
            logger.debug("❌ 비교 의도 없음")
            return {"is_comparison": False, "topics": [], "confidence": 0.0}

        # ✅ Step 2: 명시적 vs 패턴 ("A vs B")
        result = ComparisonService._extract_vs_pattern(query)
        if result["topics"]:
            logger.debug(f"✅ VS 패턴 감지: {result['topics']}")
            return result

        # ✅ Step 3: 대명사 + History 기반 토픽 추출
        if any(p in query for p in ComparisonService.PRONOUN_KEYWORDS):
            topics = ComparisonService._extract_topics_from_context(
                query, history, conversation_context
            )
            if len(topics) >= 2:
                logger.debug(f"✅ 대명사 + History: {topics[:2]}")
                return {
                    "is_comparison": True,
                    "topics": topics[:2],
                    "confidence": 0.85,
                    "detection_method": "history"
                }

        # ✅ Step 4: 질문 구조 분석 (의미론적)
        result = ComparisonService._semantic_detection(query, history)
        if result["is_comparison"]:
            logger.debug(f"✅ 의미론적 감지: {result['topics']}")
            return result

        # ✅ Step 5: 마지막 시도 - 모든 대문자 약어 추출
        topics = ComparisonService._extract_all_acronyms(query)
        if len(topics) >= 2:
            logger.debug(f"⚠️ 약어 직접 추출: {topics[:2]}")
            return {
                "is_comparison": True,
                "topics": topics[:2],
                "confidence": 0.6,  # ← 낮은 신뢰도
                "detection_method": "acronym"
            }

        logger.debug("❌ 비교 패턴 미감지")
        return {"is_comparison": False, "topics": [], "confidence": 0.0}

    @staticmethod
    def _check_comparison_intent(query: str) -> bool:
        """비교 의도 있는지 확인 (필수 조건)"""
        comparison_words = ComparisonService.COMPARISON_KEYWORDS
        return any(word in query.lower() for word in comparison_words)

    @staticmethod
    def _extract_vs_pattern(query: str) -> Dict:
        """'A vs B' 또는 'A와 B' 패턴 추출"""

        # 패턴 1: "A vs B" 형식
        vs_match = re.search(
            r'([^\s,\.]+?)\s*(?:vs|VS|V\.S|versus)\s*([^\s,\.]+)',
            query,
            re.IGNORECASE
        )
        if vs_match:
            return {
                "is_comparison": True,
                "topics": [vs_match.group(1).strip(), vs_match.group(2).strip()],
                "confidence": 0.95,
                "detection_method": "regex_vs"
            }

        # 패턴 2: "A와 B" 형식 (한국어)
        and_match = re.search(
            r'([A-Z][A-Z0-9\s]*)\s*(?:과|와|그리고)\s*([A-Z][A-Z0-9\s]*)',
            query
        )
        if and_match:
            topic1 = and_match.group(1).strip()
            topic2 = and_match.group(2).strip()
            # 검증: 둘 다 의미있는 토픽인지
            if len(topic1) > 1 and len(topic2) > 1:
                return {
                    "is_comparison": True,
                    "topics": [topic1, topic2],
                    "confidence": 0.90,
                    "detection_method": "regex_and"
                }

        return {"is_comparison": False, "topics": [], "confidence": 0.0}

    @staticmethod
    def _extract_topics_from_context(
            query: str,
            history_text: str,
            conversation_context: List[Dict] = None
    ) -> List[str]:
        """
        History와 Conversation Context에서 토픽 추출

        예: "두개 비교해줘" + History "IMO DCS... EU MRV..."
            → ["IMO DCS", "EU MRV"]
        """
        topics = []

        # 1. Conversation Context 활용 (구조화됨, 우선순위 높음)
        if conversation_context:
            for msg in reversed(conversation_context[-10:]):  # 최근 10개만
                content = msg.get("content", "")
                found = re.findall(ComparisonService.ACRONYM_PATTERN, content)
                for topic in found:
                    normalized = re.sub(r'[^\w\s]', '', topic).strip()
                    if normalized and normalized not in [t.replace(' ', '') for t in topics]:
                        topics.append(topic)
                        if len(topics) >= 3:
                            break

        # 2. History 텍스트 활용 (폴백)
        if len(topics) < 2 and history_text:
            found = re.findall(ComparisonService.ACRONYM_PATTERN, history_text)
            for topic in found:
                normalized = re.sub(r'[^\w\s]', '', topic).strip()
                if normalized and normalized not in [t.replace(' ', '') for t in topics]:
                    topics.append(topic)
                    if len(topics) >= 3:
                        break

        logger.debug(f"📚 Context 추출 결과: {topics}")
        return topics

    @staticmethod
    def _semantic_detection(query: str, history: str) -> Dict:
        """
        의미론적 감지 (향상된 버전)

        예:
        - "첫 번째와 두 번째의 차이는?"
        - "그 둘이 뭐가 달라?"
        - "같은 점과 다른 점을 설명해줘"
        """

        # 비교 구조 감지 패턴
        comparison_structures = [
            r'(?:첫|①|1(?:번째)?)\s*(?:과|와|그리고)\s*(?:두|②|2(?:번째)?)',  # 첫 번째와 두 번째
            r'(?:이것|그것|A)\s*(?:과|와|그리고)\s*(?:저것|B)',  # 이것과 저것, A와 B
            r'(?:전자|후자|앞|뒤)\s*(?:과|와|그리고)',  # 전자와 후자
            r'(?:어느\s*것이|뭐가)\s*(?:다르|더|낫|좋)',  # 뭐가 더 좋아?, 어느게 나아?
        ]

        for pattern in comparison_structures:
            if re.search(pattern, query):
                # History에서 토픽 추출
                topics = ComparisonService.extract_topics_from_history(history)
                if len(topics) >= 2:
                    logger.debug(f"✅ 의미론적 감지: {topics}")
                    return {
                        "is_comparison": True,
                        "topics": topics[:2],
                        "confidence": 0.80,
                        "detection_method": "semantic"
                    }

        return {"is_comparison": False, "topics": [], "confidence": 0.0}

    @staticmethod
    def _extract_all_acronyms(query: str) -> List[str]:
        """쿼리에서 모든 대문자 약어 추출"""
        matches = re.findall(ComparisonService.ACRONYM_PATTERN, query)

        seen = set()
        topics = []
        for match in matches:
            normalized = re.sub(r'[^\w\s]', '', match).strip()
            if normalized and normalized not in seen and len(normalized) >= 2:
                topics.append(match)
                seen.add(normalized)

        return topics

    @staticmethod
    def extract_topics_from_history(history: str) -> List[str]:
        """History에서 주요 토픽 추출 (기존 코드 유지)"""
        if not history:
            return []

        acronym_pattern = r'\b[A-Z]{2,}(?:\s+[A-Z]{2,})?\b'
        matches = re.findall(acronym_pattern, history)

        if not matches:
            return []

        seen = set()
        topics = []

        for match in reversed(matches):
            normalized = re.sub(r'[^\w\s]', '', match).strip()
            if normalized and normalized not in seen and len(topics) < 3:
                topics.append(match)
                seen.add(normalized)

        return list(reversed(topics))

# ✅ 싱글톤 인스턴스
comparison_service = ComparisonService()
