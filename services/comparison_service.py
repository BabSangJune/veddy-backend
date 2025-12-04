# services/comparison_service.py
"""
🔍 비교 모드 전담 서비스

역할:
- 비교 쿼리 자동 감지
- History에서 토픽 추출
- 비교 컨텍스트 생성

책임: 비교 기능만 담당 (독립적, 테스트 용이)
"""

import re
from typing import Dict, List
from logging_config import get_logger

logger = get_logger(__name__)


class ComparisonService:
    """비교 모드 전담 서비스"""

    # 비교 감지 키워드
    COMPARISON_KEYWORDS = ["비교", "차이", "다른점", "공통점", "vs", "VS"]

    # 대명사 (두개, 둘 등 → History에서 자동 추출)
    PRONOUNS = ["두개", "둘", "양쪽", "이 두", "저 두"]

    @staticmethod
    def detect_comparison_mode(query: str, history: str = "") -> Dict:
        """
        대화 히스토리를 활용한 스마트 비교 감지

        패턴:
        1. "IMO DCS vs EU MRV" → regex로 직접 추출
        2. "두개 차이를 비교해줘" → History에서 자동 추출
        3. "IMO 하고 EU" → 질문에서 직접 추출

        반환:
        {
            "is_comparison": True/False,
            "topics": ["A", "B"]  # 비교 대상 2개
        }

        예시:
        detect_comparison_mode("IMO DCS vs EU MRV")
        {"is_comparison": True, "topics": ["IMO DCS", "EU MRV"]}

        detect_comparison_mode("두개 차이?", "IMO DCS... EU MRV...")
        {"is_comparison": True, "topics": ["IMO DCS", "EU MRV"]}
        """

        # 1️⃣ 비교 키워드 확인 (필수)
        is_comparison = any(kw in query for kw in ComparisonService.COMPARISON_KEYWORDS)

        if not is_comparison:
            return {"is_comparison": False, "topics": []}

        # 2️⃣ "A vs B" 패턴 (명시적 비교)
        vs_match = re.search(
            r'([^\s,]+?)\s*(?:vs|VS|와)\s*([^\s,]+)',
            query,
            re.IGNORECASE
        )

        if vs_match:
            topic1, topic2 = vs_match.groups()
            logger.debug(f"✅ VS 패턴 감지: {topic1} vs {topic2}")
            return {
                "is_comparison": True,
                "topics": [topic1.strip(), topic2.strip()]
            }

        # 3️⃣ "두개", "둘" 등 대명사 (History에서 추출)
        if any(p in query for p in ComparisonService.PRONOUNS) and history:
            topics = ComparisonService.extract_topics_from_history(history)
            if len(topics) >= 2:
                logger.debug(f"✅ 대명사 감지, History에서 추출: {topics[:2]}")
                return {
                    "is_comparison": True,
                    "topics": topics[:2]  # 최근 2개만
                }

        # 4️⃣ 질문에서 직접 추출 (대문자 약어)
        words = query.split()
        topics = [w for w in words
                 if len(w) > 1 and w.isupper() and w not in [",", "와", "의", "는"]]

        if len(topics) >= 2:
            logger.debug(f"✅ 직접 추출: {topics[:2]}")
            return {
                "is_comparison": True,
                "topics": topics[:2]
            }

        # ❌ 비교 대상 찾지 못함
        logger.debug("❌ 비교 패턴 미감지")
        return {"is_comparison": False, "topics": []}

    @staticmethod
    def extract_topics_from_history(history: str) -> List[str]:
        """
        History에서 주요 토픽 추출 (IMO DCS, EU MRV 등 약어)

        특징:
        - 대문자 약어만 추출 (IMO, EU, DCS, MRV 등)
        - 중복 제거
        - 최신순 정렬 (가장 최근 것부터)

        예시:
        extract_topics_from_history("IMO DCS는... EU MRV는...")
        ["EU MRV", "IMO DCS"]  # 최신순
        """

        if not history:
            return []

        # 대문자 약어 패턴 (2글자 이상 대문자, 또는 "A B" 형식)
        acronym_pattern = r'\b[A-Z]{2,}(?:\s+[A-Z]{2,})?\b'
        matches = re.findall(acronym_pattern, history)

        if not matches:
            logger.debug("⚠️ History에서 토픽 미발견")
            return []

        # 중복 제거 & 최신순 (역순으로 순회)
        seen = set()
        topics = []

        for match in reversed(matches):
            normalized = re.sub(r'[^\w\s]', '', match).strip()

            # 이미 본 토픽이거나 빈 문자열이면 제외
            if normalized and normalized not in seen and len(topics) < 3:
                topics.append(match)
                seen.add(normalized)

        # 원래 순서 복원 (최신순 유지)
        result = list(reversed(topics))
        logger.debug(f"✅ History 토픽 추출: {result}")
        return result

    @staticmethod
    def format_comparison_prompt(topics: List[str]) -> str:
        """
        비교 모드용 프롬프트 프리픽스 생성

        예시:
        format_comparison_prompt(["IMO DCS", "EU MRV"])
        "다음 두 항목을 비교하세요: IMO DCS, EU MRV"
        """
        if not topics or len(topics) < 2:
            return ""

        return f"다음 두 항목을 비교하여 차이점, 공통점, 적용 범위를 설명해주세요:\n- {topics[0]}\n- {topics[1]}"


# ✅ 싱글톤 인스턴스
comparison_service = ComparisonService()
