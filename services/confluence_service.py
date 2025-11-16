import requests
from typing import List, Dict, Any, Optional
from config import CONFLUENCE_URL, CONFLUENCE_API_TOKEN, CONFLUENCE_SPACE_KEY
import base64
from urllib.parse import quote


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
        """
        공간(Space)의 모든 페이지 조회

        Args:
            limit: 한 번에 조회할 최대 페이지 수

        Returns:
            페이지 정보 리스트
        """
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
        """
        특정 페이지의 상세 내용 조회

        Args:
            page_id: Confluence 페이지 ID

        Returns:
            페이지 정보
        """
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

    def extract_text_from_html(self, html: str) -> str:
        """
        Confluence 저장소 형식(HTML)에서 텍스트 추출

        Args:
            html: Confluence 저장소 형식 HTML

        Returns:
            추출된 텍스트
        """
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []

            def handle_data(self, data):
                if data.strip():
                    self.text.append(data)

            def get_text(self):
                return " ".join(self.text)

        extractor = TextExtractor()
        try:
            extractor.feed(html)
            return extractor.get_text()
        except:
            return ""

    def get_all_pages_with_content(self) -> List[Dict[str, Any]]:
        """
        공간의 모든 페이지와 그 내용을 조회

        Returns:
            페이지 정보 (제목, ID, URL, 내용) 리스트
        """
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
                # HTML 내용 추출
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
