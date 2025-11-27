# services/langchain_rag_service.py (✅ 사용자 클라이언트 지원 추가)

import re
from unicodedata import normalize as unicode_normalize
from typing import List, Dict, Any, Generator, Optional

# LangChain 1.0 Import
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from langchain.agents import create_agent

from services.embedding_service import embedding_service
from services.supabase_service import supabase_service, SupabaseService  # ✅ 클래스 import 추가
from config import OPENAI_API_KEY

# ===== 커스텀 임베딩 래퍼 =====
class CustomEmbeddings(Embeddings):
    """BGE-m3-ko를 LangChain Embeddings로 래핑"""
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return embedding_service.embed_batch(texts)

    def embed_query(self, text: str) -> List[float]:
        return embedding_service.embed_text(text)

# ===== Supabase Retriever =====
class SupabaseRetriever:
    """Supabase 검색 래퍼 (URL 포함)"""
    def __init__(self, embeddings: Embeddings, supabase_client: SupabaseService, k: int = 5, threshold: float = 0.3):
        self.embeddings = embeddings
        self.supabase_client = supabase_client  # ✅ 클라이언트 주입
        self.k = k
        self.threshold = threshold

    def search(self, query: str) -> tuple[str, List[Dict]]:
        """
        문서 검색 실행 (URL 완벽 보존)
        """
        try:
            query_embedding = self.embeddings.embed_query(query)
            chunks = self.supabase_client.search_chunks(  # ✅ 주입된 클라이언트 사용
                embedding=query_embedding,
                limit=self.k,
                threshold=self.threshold
            )

            if not chunks:
                return "관련 문서를 찾을 수 없습니다.", []

            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                title = chunk.get('title', '제목 없음')
                content = chunk.get('content', '')
                source = chunk.get('source', '출처 미상')
                url = chunk.get('url', '')
                similarity = chunk.get('similarity', 0.0)

                # ✅ URL 보존 (절대 삭제 금지)
                url_section = ""
                if url and url.strip():  # URL이 있고 공백이 아니면
                    url_section = f"\n📍 출처: {source}\n🔗 URL: {url}"
                else:
                    url_section = f"\n📍 출처: {source}"

                context_parts.append(
                    f"[문서 {i}] {title}\n"
                    f"유사도: {similarity:.2f}\n"
                    f"내용:\n{content}{url_section}"
                )

            formatted_context = "\n\n---\n\n".join(context_parts)
            return formatted_context, chunks

        except Exception as e:
            return f"검색 중 오류: {str(e)}", []

# ===== 베디 프롬프트 템플릿 (개선) =====
VEDDY_SYSTEM_PROMPT = """너는 베슬링크의 내부 AI 어시스턴트 '베디(VEDDY)'야.

## 너의 역할과 정체성
이름: 베디 (Vessellink's Buddy)
성격: 친절하고 신뢰할 수 있으며, 온순하고 성실함
목표: 베슬링크 직원들의 업무 효율화와 정보 접근성 개선
전문성: 사내 문서(Confluence 위키, 규정, 매뉴얼)에 기반한 정확한 답변

## 답변 포맷 규칙 (반드시 준수)
✅ 필수 포맷:
** 제일 중요 **
답변 시 다음 Markdown 규칙을 따르세요:
1. 문단 구분: 빈 줄 2개 (\\n\\n)
2. 제목: # 또는 ##, ### 사용
3. 리스트: - 또는 1. 로 시작
4. 강조: **굵게** 또는 *기울임*

그 외
1. **제목 (1줄)**
2. **빈 줄**
3. **본문 (번호 리스트)**
   각 번호는 반드시 새로운 줄에서 시작하세요.
   각 번호 사이에는 빈 줄 1줄을 반드시 추가하세요.
4. **하위 항목 (들여쓰기)**
   - 세부 사항 1
   - 세부 사항 2
   각 항목 사이에도 빈 줄을 추가하세요.
5. **빈 줄**
6. **참고 문서 섹션**
   📚 참고 문서:
   - 문서명 > (섹션명)
   URL: https://...
7. **마무리**
   혹시 더 궁금한 점이 있으신가요?

## 정확한 답변 예시
EU MRV의 정의 및 적용 대상

1. **정의**
EU MRV는 유럽연합이 해운업계의 온실가스 배출 투명성을 확보하고, 감축을 유도하기 위해 도입한 선박의 연료소비와 CO2 배출량에 대한 모니터링, 보고 및 검증 제도입니다.

2. **포함 가스**
   - 2024년 이전: CO2만 포함
   - 2024년 이후: CO2, CH4(메탄), N2O(질소) 포함

3. **적용 대상**
   - 총톤수(GT) 5,000 이상인 선박
   - 2025년부터: 5,000GT 이상의 Offshore ships 및 일부 400~5,000GT 선박 추가
   - 화물 또는 여객을 운송하는 선박

📚 참고 문서:
- EU MRV 제품 사양서 > (1) EU MRV 정의
URL: [https://lab021.atlassian.net/wiki/spaces/TxYP20CKMWxg/pages/3017932877/EU+MRV](https://lab021.atlassian.net/wiki/spaces/TxYP20CKMWxg/pages/3017932877/EU+MRV)

혹시 더 궁금한 점이 있으신가요?

## 답변의 원칙 (절대 준수)
### A) 문서 기반 답변만 제공
✅ 제공된 문서에만 있는 내용으로 답변
❌ 문서에 없는 추측이나 일반 지식 추가 금지

### B) 할루시네이션 방지
불확실한 경우:
- "정확한 정보를 찾을 수 없습니다."
- "다음 정보를 찾았습니다. 더 자세한 내용은 [문서명]을 참고해 주세요."

### C) 톤 & 매너
✅ 높임말 사용
✅ 따뜻하고 친근한 표현
❌ 낮춤말 사용 금지

### D) 포맷 엄격성
✅ "제목 → 본문(번호) → 참고 문서" 구조 필수
✅ 각 섹션 사이 빈 줄 필수 (반드시!)
✅ 참고 문서에 URL 반드시 포함 (완전한 형태로)
❌ 띄어쓰기 없는 연속 텍스트 금지
❌ 줄바꿈 없이 쭉 이어지는 텍스트 금지

## 절대 금지 사항
❌ 문서에 없는 내용 추가
❌ 띄어쓰기 없는 연속 텍스트
❌ 줄바꿈 없이 계속되는 긴 문단
❌ 출처 없는 주장
❌ 개인 의견이나 추천
❌ 번호 없는 긴 문단
❌ 참고 문서에 URL을 빼먹음
❌ URL을 단축하거나 삭제함

## URL 처리 규칙 (매우 중요!)
✅ 반드시 따라야 할 것:
- 검색 결과에 URL이 있다면, 참고 문서에 반드시 포함하세요
- URL은 완전한 형태(https://...)로 유지하세요
- URL을 짧게 만들거나 일부만 표시하지 마세요
- 형식: "- [문서명] > (섹션명)\\n   URL: https://..."

❌ 절대 금지:
- URL 삭제 또는 생략
- URL 변경 또는 단축
- "자세히 보기" 같은 텍스트만 표시 (URL 없이)
- 마크다운 링크 형식 사용 금지: [텍스트](URL)

✅ 올바른 예:
📚 참고 문서:
- EU MRV 제품 사양서 > (1) EU MRV 정의
URL: [https://lab021.atlassian.net/wiki/spaces/TxYP20CKMWxg/pages/3017932877/EU+MRV](https://lab021.atlassian.net/wiki/spaces/TxYP20CKMWxg/pages/3017932877/EU+MRV)

## 특수 상황 대응
### 문서에 정보가 없을 때:
정보 부족

죄송하지만, 정확한 정보를 찾을 수 없습니다.

이 내용은 현재 문서에 명시되어 있지 않습니다. 자세한 사항은 담당 팀에 문의해 주세요.

혹시 다른 궁금한 점이 있으신가요?
"""

TABLE_MODE_PROMPT = """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 표 형식 답변 모드 활성화 - 절대 준수 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**사용자가 표 모드를 활성화했습니다. 다음 규칙을 반드시 따르세요:**

【필수 규칙】
1. 답변의 첫 줄은 제목만 작성
2. 제목 다음 줄부터 즉시 마크다운 표 시작
3. 번호 리스트(1., 2., 3.)는 절대 사용 금지
4. 하이픈 리스트(-, *)도 절대 사용 금지
5. 모든 항목은 표의 행으로만 표현

【표 형식】
| 항목 | 설명 | 추가정보 |
|------|------|----------|
| 값1 | 내용1 | 비고1 |
| 값2 | 내용2 | 비고2 |

【올바른 답변 예시】

선박 배출가스 규제 종류

| 규제명 | 설명 | 적용 대상 |
|--------|------|-----------|
| IMO DCS | 국제해사기구 연료 데이터 수집 제도 | 5,000GT 이상 선박 |
| EU MRV | 유럽연합 온실가스 모니터링 및 보고 | EU 항구 입출항 선박 |
| ETS | 유럽연합 배출권 거래제 | EU MRV 대상 선박 |
| FuelEU | EU 해운 탄소중립 규제 | EU 항구 기항 선박 |

표 아래에 2~3문장의 간단한 설명을 추가할 수 있습니다.

📚 참고 문서:
- 문서명
URL: https://...

【잘못된 답변 예시 - 절대 금지】

선박 배출가스 규제 종류

1. IMO DCS
   - 설명: 국제해사기구...
   
2. EU MRV
   - 설명: 유럽연합...

❌ 위와 같은 번호 리스트 형식은 절대 사용하지 마세요!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
지금부터 모든 답변은 위의 "올바른 답변 예시"처럼 표 형식으로만 작성하세요.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ===== 사용자 메시지 템플릿 =====
USER_MESSAGE_TEMPLATE = """아래 검색된 문서를 기반으로 질문에 정확하게 답변해 주세요.

【검색된 문서】
{context}

【사용자 질문】
{query}

【답변 작성 지침 - 매우 중요!】
1. 반드시 위의 "답변 포맷 규칙"을 따라 작성하세요
2. 제목은 한 줄로만 작성하세요
3. 제목 다음에는 반드시 빈 줄(개행)을 추가하세요
4. 본문은 번호 리스트(1., 2., 3., ...)로 구성하세요
5. 각 번호는 반드시 새로운 줄에서 시작하세요
6. 각 번호 다음에는 본문을 작성한 후 반드시 빈 줄을 추가하세요 (절대 중요!)
7. 하위 항목이 있으면 2칸 들여쓰기 후 " - 항목" 형식으로 작성하세요
8. 각 하위 항목 사이에도 빈 줄을 추가하세요
9. 모든 내용 다음에는 빈 줄을 추가한 후 참고 문서 섹션을 시작하세요
10. 검색 결과에 포함된 URL은 반드시 참고 문서에 포함하세요 (절대 생략 금지!)
11. 문서에 없는 내용은 절대 추가하지 마세요
12. 띄어쓰기 없는 연속 텍스트는 절대 금지입니다
13. 줄바꿈 없이 계속되는 긴 문단은 절대 금지입니다

예시:
제목

1. 첫 번째
   내용1

2. 두 번째
   내용2

📚 참고 문서:
- 문서명
URL: https://..."""

TABLE_USER_MESSAGE_TEMPLATE = """아래 검색된 문서를 기반으로 질문에 답변하세요.

【검색된 문서】
{context}

【사용자 질문】
{query}

【‼️ 표 형식 답변 필수】
위의 시스템 프롬프트에 명시된 대로, 반드시 마크다운 표 형식으로 답변하세요.

예시 형식:
제목

| 항목 | 설명 | 비고 |
|------|------|------|
| ... | ... | ... |

추가 설명 (선택)

📚 참고 문서:
- 문서명
URL: https://...

번호 리스트나 하이픈 리스트는 절대 사용하지 마세요!"""

# ===== LangChain 1.0 RAG 서비스 (✅ 사용자 클라이언트 지원) =====
class LangChainRAGService:
    """LangChain 1.0 기반 RAG 서비스 (베디 프롬프트 적용)"""

    def __init__(self):
        """Agent 초기화"""
        print("🔧 LangChain 1.0 RAG Service 초기화 중...")

        # 1. 임베딩
        self.embeddings = CustomEmbeddings()

        # 2. LLM (개선된 설정)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=OPENAI_API_KEY,
            streaming=True
        )

        # 3. 프롬프트 템플릿
        self.base_prompt_template = ChatPromptTemplate.from_messages([
            ("system", VEDDY_SYSTEM_PROMPT),
            ("user", USER_MESSAGE_TEMPLATE)
        ])

        self.table_prompt_template = ChatPromptTemplate.from_messages([
            ("system", VEDDY_SYSTEM_PROMPT + TABLE_MODE_PROMPT),
            ("user", TABLE_USER_MESSAGE_TEMPLATE)
        ])

        print("✅ LangChain 1.0 RAG Service 초기화 완료")

    def _normalize_response(self, response: str) -> str:
        """
        ✅ 응답 텍스트 정규화 (자모 분리 복구)
        """
        import re
        from unicodedata import normalize as unicode_normalize

        # 1. ✅ 유니코드 정규화 (가장 중요!)
        text = unicode_normalize('NFC', response)

        # 2. 줄바꿈 통일
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')

        # 3. 3개 이상 줄바꿈 → 2개
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 4. 각 줄 공백 정리
        lines = []
        for line in text.split('\n'):
            stripped = line.rstrip()
            stripped = re.sub(r' +', ' ', stripped)
            lines.append(stripped)
        text = '\n'.join(lines)

        # 5. 최종 정리
        return text.strip()

    def process_query(
            self,
            user_id: str,
            query: str,
            table_mode: bool = False,
            supabase_client: Optional[SupabaseService] = None  # ✅ 사용자 클라이언트 주입
    ) -> Dict[str, Any]:
        """RAG 쿼리 처리 (일반 응답) - 🆕 표 모드 + 사용자 클라이언트 추가"""
        try:
            # ✅ 클라이언트 선택: 전달된 것이 있으면 사용, 없으면 글로벌 사용
            client = supabase_client if supabase_client else supabase_service

            # 1. Retriever 생성 (사용자 클라이언트 사용)
            retriever = SupabaseRetriever(
                embeddings=self.embeddings,
                supabase_client=client,  # ✅ 사용자 클라이언트 전달
                k=5,
                threshold=0.3
            )

            # 2. 문서 검색
            context_text, raw_chunks = retriever.search(query)

            # 3. 프롬프트 선택
            prompt_template = self.table_prompt_template if table_mode else self.base_prompt_template

            # 4. 메시지 생성
            messages = prompt_template.format_messages(
                context=context_text,
                query=query
            )

            # 5. LLM 호출
            response = self.llm.invoke(messages)
            ai_response = response.content

            # ✅ 6. 응답 정규화
            ai_response = self._normalize_response(ai_response)

            # 7. 소스 ID 추출
            source_chunk_ids = [
                chunk.get('id') for chunk in raw_chunks
                if chunk.get('id')
            ]

            # 8. 메시지 저장 (사용자 클라이언트 사용)
            client.save_message(
                user_id=user_id,
                user_query=query,
                ai_response=ai_response,
                source_chunk_ids=source_chunk_ids,
                usage={}
            )

            return {
                "user_query": query,
                "ai_response": ai_response,
                "source_chunks": raw_chunks,
                "usage": {}
            }

        except Exception as e:
            print(f"❌ RAG 처리 중 오류: {e}")
            raise

    def process_query_streaming(
            self,
            user_id: str,
            query: str,
            table_mode: bool = False,
            supabase_client: Optional[SupabaseService] = None  # ✅ 사용자 클라이언트 주입
    ) -> Generator[str, None, None]:
        """RAG 스트리밍 응답 (토큰별 정규화 추가) - 🆕 표 모드 + 사용자 클라이언트 추가"""
        try:
            # ✅ 클라이언트 선택
            client = supabase_client if supabase_client else supabase_service

            # 1. Retriever 생성
            retriever = SupabaseRetriever(
                embeddings=self.embeddings,
                supabase_client=client,  # ✅ 사용자 클라이언트 전달
                k=5,
                threshold=0.3
            )

            # 2. 문서 검색
            context_text, raw_chunks = retriever.search(query)

            # 3. 프롬프트 선택
            prompt_template = self.table_prompt_template if table_mode else self.base_prompt_template

            print(f"[RAG] table_mode: {table_mode}")
            if table_mode:
                print(f"[RAG] 표 모드 프롬프트 사용 중")

            # 4. 메시지 생성
            messages = prompt_template.format_messages(
                context=context_text,
                query=query
            )

            # 5. 스트리밍 LLM 호출
            full_response = ""
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    token = chunk.content
                    # ✅ 각 토큰 정규화
                    normalized_token = unicode_normalize('NFC', token)
                    full_response += normalized_token
                    yield normalized_token

            # 6. 최종 응답 정규화 (저장용)
            final_normalized = self._normalize_response(full_response)

            # 7. 소스 ID 추출
            source_chunk_ids = [
                chunk.get('id') for chunk in raw_chunks
                if chunk.get('id')
            ]

            # 8. 메시지 저장 (사용자 클라이언트 사용)
            client.save_message(
                user_id=user_id,
                user_query=query,
                ai_response=final_normalized,
                source_chunk_ids=source_chunk_ids,
                usage={}
            )

        except Exception as e:
            print(f"❌ 스트리밍 중 오류: {e}")
            yield f"\n\n[오류 발생]\n{str(e)}"

# 글로벌 인스턴스
langchain_rag_service = LangChainRAGService()
