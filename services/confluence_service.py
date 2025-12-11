# services/confluence_service.py (✨ Singleton 패턴 적용 + ✅ REST API v2)

import requests
from typing import List, Dict, Any, Optional
from config import CONFLUENCE_URL, CONFLUENCE_API_TOKEN, CONFLUENCE_SPACE_KEY
import base64
import re
from unicodedata import normalize as unicode_normalize


class ConfluenceService:
    # ✨ 클래스 변수: 싱글톤 인스턴스
    _instance = None

    def __init__(self, space_key: str, atlassian_id: str, api_token: str):
        """Confluence 클라이언트 초기화

        Args:
            space_key: Confluence Space Key (필수)
            atlassian_id: Atlassian ID (이메일) (필수)
            api_token: Confluence API Token (필수)
        """
        # ✨ 필수 입력 검증
        if not space_key or not isinstance(space_key, str):
            raise ValueError("❌ Space Key는 필수이며, 문자열이어야 합니다")

        if not atlassian_id or not isinstance(atlassian_id, str):
            raise ValueError("❌ Atlassian ID는 필수이며, 문자열이어야 합니다")

        if not api_token or not isinstance(api_token, str):
            raise ValueError("❌ API Token은 필수이며, 문자열이어야 합니다")

        # ✨ 정보 저장
        self.base_url = CONFLUENCE_URL
        self.space_key = space_key.strip()
        self.atlassian_id = atlassian_id.strip()
        self.api_token = api_token.strip()

        # 기본 인증 (atlassian_id:token)
        auth_string = f"{self.atlassian_id}:{self.api_token}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        print(f"✅ Confluence 클라이언트 초기화 완료 (Space: {self.space_key}, Atlassian ID: {self.atlassian_id})")

    @classmethod
    def initialize(cls, space_key: str, atlassian_id: str, api_token: str) -> 'ConfluenceService':
        """Confluence Service 초기화 (Singleton 패턴)

        Args:
            space_key: Confluence Space Key (필수)
            atlassian_id: Atlassian ID (이메일) (필수)
            api_token: Confluence API Token (필수)

        Returns:
            ConfluenceService 싱글톤 인스턴스

        Example:
            confluence_service = ConfluenceService.initialize('SpaceKey', 'atlassian@example.com', 'token123')
        """
        cls._instance = cls(space_key, atlassian_id, api_token)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'ConfluenceService':
        """현재 싱글톤 인스턴스 반환

        Returns:
            ConfluenceService 싱글톤 인스턴스

        Raises:
            ValueError: 인스턴스가 초기화되지 않았을 경우

        Example:
            service = ConfluenceService.get_instance()
        """
        if cls._instance is None:
            raise ValueError("❌ Confluence Service가 초기화되지 않았습니다. initialize()를 먼저 호출하세요")
        return cls._instance

    def set_space_key(self, space_key: str) -> None:
        """Space Key 동적 변경

        Args:
            space_key: 새로 설정할 Confluence Space Key (필수)

        Raises:
            ValueError: Space Key가 비어있을 경우
        """
        if not space_key or not isinstance(space_key, str):
            raise ValueError("❌ Space Key는 필수이며, 문자열이어야 합니다")

        old_key = self.space_key
        self.space_key = space_key.strip()
        print(f"✅ Space Key 변경: '{old_key}' → '{self.space_key}'")

    def set_credentials(self, atlassian_id: str, api_token: str) -> None:
        """Confluence 자격증명 동적 변경

        Args:
            atlassian_id: Atlassian ID (이메일) (필수)
            api_token: Confluence API Token (필수)

        Raises:
            ValueError: atlassian_id나 api_token이 비어있을 경우
        """
        if not atlassian_id or not isinstance(atlassian_id, str):
            raise ValueError("❌ Atlassian ID는 필수이며, 문자열이어야 합니다")

        if not api_token or not isinstance(api_token, str):
            raise ValueError("❌ API Token은 필수이며, 문자열이어야 합니다")

        old_atlassian_id = self.atlassian_id
        self.atlassian_id = atlassian_id.strip()
        self.api_token = api_token.strip()

        # ✨ 새로운 인증정보로 헤더 업데이트
        auth_string = f"{self.atlassian_id}:{self.api_token}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        print(f"✅ 자격증명 변경: '{old_atlassian_id}' → '{self.atlassian_id}'")

    def set_all(self, space_key: str, atlassian_id: str, api_token: str) -> None:
        """Space Key와 자격증명 한 번에 설정

        Args:
            space_key: Confluence Space Key (필수)
            atlassian_id: Atlassian ID (이메일) (필수)
            api_token: Confluence API Token (필수)

        Raises:
            ValueError: 필수 파라미터가 비어있을 경우
        """
        self.set_space_key(space_key)
        self.set_credentials(atlassian_id, api_token)
        print(f"✅ 모든 설정 완료: Space={self.space_key}, Atlassian ID={self.atlassian_id}")

    def get_pages_from_space(self, limit: int = 50) -> List[Dict[str, Any]]:
        """공간(Space)의 모든 페이지 조회 (✅ 수동 필터링)"""

        print(f"\n🔍 Space 조회:")
        print(f"  - 찾는 Space Key: {self.space_key}")

        try:
            # Step 1️⃣: 모든 Space 조회
            spaces_url = f"{self.base_url}/api/v2/spaces"
            spaces_params = {
                "limit": 100  # ← spaceKey 파라미터 제거, 모든 space 조회
            }

            print(f"  - 1️⃣ 모든 Space 조회 URL: {spaces_url}")

            response = requests.get(spaces_url, headers=self.headers, params=spaces_params)
            response.raise_for_status()

            all_spaces = response.json().get("results", [])
            print(f"  - 📋 조회된 전체 Space: {len(all_spaces)}개")
            for s in all_spaces:
                print(f"    - {s.get('key')}: {s.get('name')} (ID: {s.get('id')})")

            # Step 2️⃣: 우리가 찾는 Space 필터링
            target_space = None
            for space in all_spaces:
                if space.get("key") == self.space_key:
                    target_space = space
                    break

            if not target_space:
                print(f"❌ Space '{self.space_key}' 찾을 수 없음")
                print(f"   사용 가능한 Space Key: {[s.get('key') for s in all_spaces]}")
                return []

            space_id = target_space.get("id")
            space_key = target_space.get("key")

            print(f"  - ✅ 찾은 Space:")
            print(f"    - Key: {space_key}")
            print(f"    - ID: {space_id}")
            print(f"    - Name: {target_space.get('name')}")

            # Step 3️⃣: Space ID로 페이지 조회
            pages_url = f"{self.base_url}/api/v2/spaces/{space_id}/pages"
            pages_params = {
                "limit": limit,
                "expand": "body.storage"
            }

            print(f"  - 2️⃣ 페이지 조회 URL: {pages_url}")

            response = requests.get(pages_url, headers=self.headers, params=pages_params)
            response.raise_for_status()

            data = response.json()
            pages = data.get("results", [])

            print(f"✅ {len(pages)}개 페이지 조회 완료 (Space: {space_key})")
            return pages

        except requests.exceptions.RequestException as e:
            print(f"❌ Confluence API 요청 오류: {e}")
            if hasattr(e, 'response'):
                print(f"  - 응답: {e.response.text}")
            return []

    def get_page_content(self, page_id: str) -> Optional[Dict[str, Any]]:
        """특정 페이지의 상세 내용 조회 (✅ REST API v2)"""
        # ✅ v2 엔드포인트 사용
        url = f"{self.base_url}/api/v2/pages/{page_id}"

        params = {
            "body-format": "storage"  # HTML 형식으로 받기
        }

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            data = response.json()

            # ✅ 디버그: 시간 정보 확인 (v2 필드)
            print(f"\n🔍 Confluence API v2 응답 (Page ID: {page_id}):")
            print(f"  - createdAt: {data.get('createdAt')}")
            print(f"  - version.createdAt: {data.get('version', {}).get('createdAt')}")
            print(f"  - Full data keys: {data.keys()}")

            return data

        except requests.exceptions.RequestException as e:
            print(f"❌ 페이지 조회 오류: {e}")
            return None

    # ===== ✅ 전처리 함수들 =====

    def clean_html(self, html_content: str) -> str:
        """
        ✅ HTML 정제 (Confluence 매크로 완벽 제거)
        """
        text = html_content

        # ===== 1. Confluence 구조화된 매크로 제거 =====
        text = re.sub(r'<ac:structured-macro[^>]*>.*?</ac:structured-macro>', '', text, flags=re.DOTALL)

        # ===== 2. Confluence ADF 확장 제거 =====
        text = re.sub(r'<ac:adf-extension>.*?</ac:adf-extension>', '', text, flags=re.DOTALL)

        # ===== 3. 기타 Confluence 태그 제거 =====
        text = re.sub(r'<ac:[^>]*>.*?</ac:[^>]*>', '', text, flags=re.DOTALL)
        text = re.sub(r'<ac:[^/>]*/?>', '', text)
        text = re.sub(r'<ri:[^/>]*/?>', '', text)

        # ===== 4. Confluence 속성 제거 =====
        text = re.sub(r'<ac:parameter[^>]*>.*?</ac:parameter>', '', text, flags=re.DOTALL)
        text = re.sub(r'<ac:adf-attribute[^>]*>.*?</ac:adf-attribute>', '', text, flags=re.DOTALL)
        text = re.sub(r'<ac:rich-text-body>', '', text)
        text = re.sub(r'</ac:rich-text-body>', '', text)
        text = re.sub(r'<ac:adf-node[^>]*>.*?</ac:adf-node>', '', text, flags=re.DOTALL)

        # ===== 5. 링크 변환 =====
        text = re.sub(
            r'<a\s+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>',
            lambda m: f"{m.group(2)} (URL: {m.group(1)})",
            text
        )

        # ===== 6. 강조 변환 =====
        text = re.sub(r'<strong>([^<]+)</strong>', r'**\1**', text)
        text = re.sub(r'<b>([^<]+)</b>', r'**\1**', text)
        text = re.sub(r'<em>([^<]+)</em>', r'*\1*', text)
        text = re.sub(r'<i>([^<]+)</i>', r'*\1*', text)

        # ===== 7. 제목 변환 =====
        for level in range(1, 7):
            text = re.sub(
                rf'<h{level}[^>]*>([^<]+)</h{level}>',
                lambda m: '\n' + ('#' * min(level + 1, 6)) + ' ' + m.group(1) + '\n\n',
                text
            )

        # ===== 8. 단락 =====
        text = re.sub(r'<p[^>]*>', '', text)
        text = re.sub(r'</p>', '\n\n', text)

        # ===== 9. 줄바꿈 =====
        text = re.sub(r'<br\s*/?>', '\n', text)

        # ===== 10. 블록 요소 =====
        text = re.sub(r'<div[^>]*>', '\n', text)
        text = re.sub(r'</div>', '\n', text)
        text = re.sub(r'<section[^>]*>', '\n', text)
        text = re.sub(r'</section>', '\n', text)

        # ===== 11. 리스트 =====
        text = re.sub(r'<li[^>]*>([^<]+)</li>', r'\n- \1', text)
        text = re.sub(r'<ul[^>]*>', '\n', text)
        text = re.sub(r'</ul>', '\n', text)
        text = re.sub(r'<ol[^>]*>', '\n', text)
        text = re.sub(r'</ol>', '\n', text)

        # ===== 12. 테이블 =====
        text = re.sub(r'<tr[^>]*>', '\n', text)
        text = re.sub(r'</tr>', '\n', text)
        text = re.sub(r'<td[^>]*>([^<]*)</td>', r' | \1', text)
        text = re.sub(r'<th[^>]*>([^<]*)</th>', r' | \1', text)
        text = re.sub(r'<table[^>]*>', '\n', text)
        text = re.sub(r'</table>', '\n\n', text)

        # ===== 13. 나머지 HTML 태그 제거 =====
        text = re.sub(r'<[^>]+>', '', text)

        # ===== 14. HTML 엔티티 디코딩 =====
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')
        text = text.replace('&quot;', '"')
        text = text.replace('&apos;', "'")

        return text

    def normalize_text(self, text: str) -> str:
        """
        ✅ 텍스트 정규화
        """
        # 1. 유니코드 정규화 (NFC)
        text = unicode_normalize('NFC', text)

        # 2. 줄바꿈 통일
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')

        # 3. 3개 이상의 연속 줄바꿈 → 2개
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 4. 각 줄의 앞뒤 공백 제거
        lines = []
        for line in text.split('\n'):
            stripped = line.rstrip()
            stripped = re.sub(r'  +', ' ', stripped)
            lines.append(stripped)

        text = '\n'.join(lines)

        # 5. 최종 정리
        return text.strip()

    def extract_text_from_html(self, html: str) -> str:
        """
        ✅ HTML에서 텍스트 추출 (전처리 완전 적용)
        """
        # 1. HTML 정제
        cleaned = self.clean_html(html)

        # 2. 텍스트 정규화
        normalized = self.normalize_text(cleaned)

        return normalized

    def get_all_pages_with_content(self) -> List[Dict[str, Any]]:
        """공간의 모든 페이지와 그 내용을 조회 (✅ REST API v2 + 시간 정보 + URL 수정)"""
        from datetime import datetime
        from dateutil import parser as date_parser

        pages = self.get_pages_from_space(limit=100)
        pages_with_content = []

        for i, page in enumerate(pages, 1):
            page_id = page.get("id")
            title = page.get("title", "Untitled")

            # ✅ API에서 받은 상대 URL (예: /spaces/SD/pages/106201423)
            relative_url = page.get("_links", {}).get("webui", "")

            # ✅ 디버그: URL 확인
            print(f"  [{i}/{len(pages)}] {title} ({page_id})")
            print(f"    📍 Relative URL: {relative_url}")

            # ✅ 도메인 + 상대 URL = 완전한 URL
            full_url = f"{self.base_url}{relative_url}" if relative_url else ""
            print(f"    🔗 Full URL: {full_url}")

            url = full_url  # ← 이걸 사용

            # 상세 내용 조회 (v2)
            full_page = self.get_page_content(page_id)

            if full_page:
                # ✅ v2 응답에서 HTML 추출
                storage_html = full_page.get("body", {}).get("storage", {}).get("value", "")
                content = self.extract_text_from_html(storage_html)

                # ✅ v2의 시간 정보 사용 (createdAt, version.createdAt)
                # 1. 페이지 생성 시간
                created_at_str = full_page.get("createdAt")

                # 2. 페이지 수정 시간
                updated_at_str = full_page.get("version", {}).get("createdAt")

                try:
                    created_at = date_parser.parse(created_at_str) if created_at_str else datetime.now()
                except:
                    created_at = datetime.now()

                try:
                    updated_at = date_parser.parse(updated_at_str) if updated_at_str else datetime.now()
                except:
                    updated_at = datetime.now()

                print(f"    📅 Created: {created_at}")
                print(f"    📅 Updated: {updated_at}")

                pages_with_content.append({
                    "page_id": page_id,
                    "title": title,
                    "url": url,  # ✅ 정상 URL (도메인 포함)
                    "content": content,
                    "labels": [label.get("name") for label in
                               full_page.get("labels", {}).get("results", [])],
                    # ✅ 정확한 시간 정보
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "version_number": full_page.get("version", {}).get("number", 1)
                })

        return pages_with_content


confluence_service = None
