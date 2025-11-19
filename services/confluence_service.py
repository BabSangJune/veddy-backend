# services/confluence_service.py (최종 버전)

import requests
from typing import List, Dict, Any, Optional
from config import CONFLUENCE_URL, CONFLUENCE_API_TOKEN, CONFLUENCE_SPACE_KEY
import base64
import re
from unicodedata import normalize as unicode_normalize


class ConfluenceService:
    def __init__(self):
        """Confluence 클라이언트 초기화"""
        self.base_url = CONFLUENCE_URL
        self.space_key = CONFLUENCE_SPACE_KEY

        # 기본 인증 (email:token)
        auth_string = f"applause1319@naver.com:{CONFLUENCE_API_TOKEN}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        print("✅ Confluence 클라이언트 초기화 완료")

    def get_pages_from_space(self, limit: int = 50) -> List[Dict[str, Any]]:
        """공간(Space)의 모든 페이지 조회"""
        url = f"{self.base_url}/rest/api/content"

        params = {
            "spaceKey": self.space_key,
            "limit": limit,
            "expand": "body.storage,metadata.labels,space"
        }

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            data = response.json()
            pages = data.get("results", [])

            print(f"✅ {len(pages)}개 페이지 조회 완료")
            return pages

        except requests.exceptions.RequestException as e:
            print(f"❌ Confluence API 요청 오류: {e}")
            return []

    def get_page_content(self, page_id: str) -> Optional[Dict[str, Any]]:
        """특정 페이지의 상세 내용 조회"""
        url = f"{self.base_url}/rest/api/content/{page_id}"

        params = {
            "expand": "body.storage,metadata.labels,space"
        }

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            return response.json()

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
        """공간의 모든 페이지와 그 내용을 조회"""
        pages = self.get_pages_from_space(limit=100)

        pages_with_content = []

        for i, page in enumerate(pages, 1):
            page_id = page.get("id")
            title = page.get("title", "Untitled")
            url = page.get("_links", {}).get("webui", "")

            print(f"  [{i}/{len(pages)}] {title} ({page_id})")

            # 상세 내용 조회
            full_page = self.get_page_content(page_id)

            if full_page:
                # HTML 내용 추출 (전처리 적용!)
                storage_html = full_page.get("body", {}).get("storage", {}).get("value", "")
                content = self.extract_text_from_html(storage_html)

                pages_with_content.append({
                    "page_id": page_id,
                    "title": title,
                    "url": url,
                    "content": content,
                    "labels": [label.get("name") for label in
                               full_page.get("metadata", {}).get("labels", {}).get("results", [])]
                })

        return pages_with_content


# 글로벌 인스턴스
confluence_service = ConfluenceService()
