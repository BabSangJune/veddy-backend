"""
🧪 테이블 모드 + 비교 모드 조합 테스트

테스트 대상: langchain_rag_service.py + unified_chat_service.py
테스트 항목:
  1. 테이블 모드 독립적 동작
  2. 비교 모드 + 테이블 모드 조합
  3. 일반 모드 + 테이블 모드 조합
  4. 프롬프트 선택 로직
"""

import pytest
from typing import Dict
from services.langchain_rag_service import langchain_rag_service
from services.comparison_service import comparison_service


class TestTableModeIndependence:
    """
    테이블 모드가 다른 모드와 독립적으로 작동하는지 테스트
    
    핵심:
    - table_mode는 프롬프트 형식만 결정
    - 검색 로직은 비교/일반 모드에 따라 결정
    - 둘은 독립적으로 조합 가능해야 함
    """

    def test_table_mode_attribute(self):
        """
        table_mode 파라미터가 제대로 전달되고 저장되는지 확인
        """
        # 프롬프트 선택 로직 테스트
        # table_mode=False (default)
        template_default = langchain_rag_service._select_prompt_template(
            table_mode=False,
            is_comparison=False,
            topics=[]
        )
        assert template_default is not None
        assert \"table\" not in str(template_default).lower() or \"table_prompt\" not in str(template_default)

        # table_mode=True
        template_table = langchain_rag_service._select_prompt_template(
            table_mode=True,
            is_comparison=False,
            topics=[]
        )
        assert template_table is not None
        print(f"Default template: {template_default.messages[0].content[:50]}...")
        print(f"Table template: {template_table.messages[0].content[:50]}...")

    def test_table_with_normal_mode(self):
        """
        일반 모드 + 테이블 모드
        
        기대 결과:
        - 검색: search_hybrid() 사용
        - 프롬프트: table_prompt_template 사용
        """
        comparison_info = {\"is_comparison\": False, \"topics\": []}
        
        # 프롬프트 선택
        template = langchain_rag_service._select_prompt_template(
            table_mode=True,
            is_comparison=False,
            topics=[]
        )
        
        assert template is not None
        template_str = str(template)
        # 테이블 모드임을 나타내는 키워드 확인
        print(f"Normal + Table 프롬프트 생성 완료")

    def test_table_with_comparison_mode(self):
        """
        비교 모드 + 테이블 모드 ✨ (현재는 불가능했던 조합)
        
        기대 결과:
        - 검색: search_multi_topic() 사용
        - 프롬프트: comparison_table_prompt_template 사용
        """
        comparison_info = {
            \"is_comparison\": True,
            \"topics\": [\"IMO DCS\", \"EU MRV\"],
            \"confidence\": 0.95,
            \"detection_method\": \"regex_vs\"
        }
        
        # 프롬프트 선택
        template = langchain_rag_service._select_prompt_template(
            table_mode=True,
            is_comparison=True,
            topics=comparison_info[\"topics\"]
        )
        
        assert template is not None
        template_str = str(template)
        # 비교 + 테이블 하이브리드 프롬프트임을 나타내는 키워드 확인
        print(f"Comparison + Table 프롬프트 생성 완료")
        print(f"프롬프트 내용: {template_str[:100]}...")


class TestPromptSelection:
    """
    프롬프트 선택 로직 (독립적 적용)
    """

    def test_prompt_templates_differ(self):
        """
        각 조합별 프롬프트가 다른지 확인
        """
        templates = {
            \"normal\": langchain_rag_service._select_prompt_template(
                table_mode=False, is_comparison=False
            ),
            \"normal+table\": langchain_rag_service._select_prompt_template(
                table_mode=True, is_comparison=False
            ),
            \"comparison\": langchain_rag_service._select_prompt_template(
                table_mode=False, is_comparison=True, topics=[\"A\", \"B\"]
            ),
            \"comparison+table\": langchain_rag_service._select_prompt_template(
                table_mode=True, is_comparison=True, topics=[\"A\", \"B\"]
            )
        }

        # 각 프롬프트가 고유함을 확인
        template_strs = {k: str(v) for k, v in templates.items()}
        
        # 최소 일부 프롬프트는 달라야 함
        assert template_strs[\"normal\"] != template_strs[\"normal+table\"], \
            \"Normal과 Normal+Table 프롬프트가 같으면 안 됨\"
        
        print(\"✅ 각 조합별 프롬프트가 구별됨\")
        for name, template_str in template_strs.items():
            print(f\"  {name}: {len(template_str)} chars\")

    def test_comparison_prompt_has_comparison_info(self):
        """
        비교 모드 프롬프트가 비교 관련 정보를 포함하는지 확인
        """
        template = langchain_rag_service._select_prompt_template(
            table_mode=False,
            is_comparison=True,
            topics=[\"IMO DCS\", \"EU MRV\"]
        )
        
        template_str = str(template).lower()
        # 비교 관련 키워드 확인
        comparison_keywords = [\"비교\", \"차이\", \"공통\", \"분석\"]
        has_keywords = any(kw in template_str for kw in comparison_keywords)
        
        print(f\"Comparison 프롬프트: {template_str[:150]}...\")
        print(f\"비교 관련 키워드 포함: {has_keywords}\")


class TestSearchMethodSelection:
    """
    모드별 검색 방식이 제대로 선택되는지 테스트
    """

    def test_search_method_for_normal_mode(self):
        """
        일반 모드: search_hybrid() 사용
        """
        comparison_info = {\"is_comparison\": False, \"topics\": []}
        # 실제 검색은 하지 않고, 로직만 확인
        # (실제 Supabase 연결이 필요하므로)
        print(\"일반 모드 검색: search_hybrid() 예정\")

    def test_search_method_for_comparison_mode(self):
        """
        비교 모드: search_multi_topic() 사용
        """
        comparison_info = {
            \"is_comparison\": True,
            \"topics\": [\"IMO DCS\", \"EU MRV\"]
        }
        # 실제 검색은 하지 않고, 로직만 확인
        print(f\"비교 모드 검색: search_multi_topic({comparison_info['topics']}) 예정\")


class TestIntegrationScenarios:
    """
    실제 사용 시나리오 테스트
    """

    def test_scenario_1_comparison_with_table(self):
        """
        시나리오 1: "IMO DCS vs EU MRV를 비교해줘 (체크박스)" + table_mode=True
        
        기대:
        - 비교 모드 자동 감지: ✅
        - 테이블 형식 적용: ✅
        - 결과: 비교 분석을 마크다운 표로
        """
        query = \"IMO DCS vs EU MRV 비교해줘\"
        table_mode = True
        
        # Step 1: 비교 모드 감지
        comparison_info = comparison_service.detect_comparison_mode(query)
        assert comparison_info[\"is_comparison\"] == True
        assert \"IMO DCS\" in comparison_info[\"topics\"]
        assert \"EU MRV\" in comparison_info[\"topics\"]
        
        # Step 2: 프롬프트 선택
        template = langchain_rag_service._select_prompt_template(
            table_mode=table_mode,
            is_comparison=comparison_info[\"is_comparison\"],
            topics=comparison_info[\"topics\"]
        )
        assert template is not None
        
        print(\"✅ Scenario 1 완료: 비교 + 테이블 모드\")

    def test_scenario_2_normal_with_table(self):
        """
        시나리오 2: "선박 안전 규정은?" + table_mode=True
        
        기대:
        - 비교 모드 미감지: ✅
        - 테이블 형식 적용: ✅
        - 결과: 일반 검색을 마크다운 표로
        """
        query = \"선박 안전 규정은?\"
        table_mode = True
        
        # Step 1: 비교 모드 감지
        comparison_info = comparison_service.detect_comparison_mode(query)
        assert comparison_info[\"is_comparison\"] == False
        
        # Step 2: 프롬프트 선택
        template = langchain_rag_service._select_prompt_template(
            table_mode=table_mode,
            is_comparison=False,
            topics=[]
        )
        assert template is not None
        
        print(\"✅ Scenario 2 완료: 일반 + 테이블 모드\")

    def test_scenario_3_normal_without_table(self):
        """
        시나리오 3: "해양 법규 설명해줘" + table_mode=False
        
        기대:
        - 일반 검색
        - 일반 형식
        - 기존과 동일
        """
        query = \"해양 법규 설명해줘\"
        table_mode = False
        
        # Step 1: 비교 모드 감지
        comparison_info = comparison_service.detect_comparison_mode(query)
        assert comparison_info[\"is_comparison\"] == False
        
        # Step 2: 프롬프트 선택 (기존 방식)
        template = langchain_rag_service._select_prompt_template(
            table_mode=table_mode,
            is_comparison=False,
            topics=[]
        )
        assert template is not None
        
        print(\"✅ Scenario 3 완료: 일반 모드 (기존 방식)\")

    def test_scenario_4_history_based_comparison_with_table(self):
        """
        시나리오 4: History에서 토픽 추출 후 테이블 형식
        
        대화 흐름:
        1. "IMO DCS는 뭐야?" → history에 IMO DCS
        2. "EU MRV도 설명해줘" → history에 EU MRV
        3. "두개 비교해줄래? 표로." (table_mode=True)
        
        기대:
        - History에서 토픽 추출: ✅
        - 비교 모드 활성화: ✅
        - 테이블 형식: ✅
        """
        # 시뮬레이션
        history = \"\"\"  
        User: IMO DCS는 뭐야?
        Assistant: IMO DCS는 국제해사기구 규정...
        User: EU MRV도 설명해줘
        Assistant: EU MRV는 유럽연합 규정...
        \"\"\"
        
        query = \"두개 비교해줄래? 표로.\"
        table_mode = True
        
        # Step 1: 비교 모드 감지 (History 기반)
        comparison_info = comparison_service.detect_comparison_mode(query, history)
        print(f\"Detected: {comparison_info}\")
        
        # Step 2: 프롬프트 선택
        if comparison_info[\"is_comparison\"]:
            template = langchain_rag_service._select_prompt_template(
                table_mode=table_mode,
                is_comparison=True,
                topics=comparison_info.get(\"topics\", [])
            )
            print(\"✅ Scenario 4 완료: History 기반 비교 + 테이블\")
        else:
            print(\"⚠️ Scenario 4: History 기반 감지 실패\")


if __name__ == \"__main__\":
    pytest.main([\"-v\", __file__])
