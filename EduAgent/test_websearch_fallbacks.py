import unittest
from unittest.mock import patch

from tools.search.websearch import search


class FakeResponse:
    def __init__(self, text="", status_code=200, headers=None, json_data=None, url=""):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self._json_data = json_data
        self.url = url
        self.encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self._json_data is None:
            raise ValueError("not json")
        return self._json_data


class WebSearchFallbackTests(unittest.TestCase):
    def test_search_uses_baidu_when_ddg_and_bing_are_challenged(self):
        def fake_get(url, **kwargs):
            if "duckduckgo.com" in url:
                return FakeResponse(
                    """
                    <html><body>
                      <form id="challenge-form" action="/anomaly.js">
                        Unfortunately, bots use DuckDuckGo too.
                      </form>
                    </body></html>
                    """,
                    status_code=202,
                    url=url,
                )
            if "bing.com/search" in url:
                return FakeResponse(
                    """
                    <html><body>
                      <script>var CfConfig = {"siteKey":"turnstile"};</script>
                    </body></html>
                    """,
                    url=url,
                )
            if "baidu.com/s" in url:
                return FakeResponse(
                    """
                    <html><body>
                      <div class="result c-container">
                        <h3 class="t"><a href="http://www.baidu.com/link?url=abc">变量定义示例</a></h3>
                        <div class="c-abstract">变量是用于保存值的命名存储位置。</div>
                      </div>
                    </body></html>
                    """,
                    url=url,
                )
            if "baidu.com/link" in url:
                return FakeResponse(
                    status_code=302,
                    headers={"Location": "https://example.com/variable"},
                    url=url,
                )
            raise AssertionError(f"unexpected URL: {url}")

        with patch("tools.search.websearch.requests.get", side_effect=fake_get):
            results = search(
                "变量定义 示例",
                top_k=3,
                endpoint="http://localhost:8090/search",
                timeout=5,
            )

        self.assertEqual(
            results,
            [
                {
                    "title": "变量定义示例",
                    "url": "https://example.com/variable",
                    "snippet": "变量是用于保存值的命名存储位置。",
                    "engine": "baidu",
                }
            ],
        )

    def test_baidu_fallback_skips_internal_widgets(self):
        def fake_get(url, **kwargs):
            if "duckduckgo.com" in url:
                return FakeResponse('<form id="challenge-form"></form>', status_code=202, url=url)
            if "baidu.com/s" in url:
                return FakeResponse(
                    """
                    <html><body>
                      <div class="result-op">
                        <h3><a href="https://top.baidu.com/board?platform=pc">热榜</a></h3>
                      </div>
                      <div class="result c-container">
                        <h3 class="t"><a href="http://www.baidu.com/link?url=real">变量定义</a></h3>
                      </div>
                    </body></html>
                    """,
                    url=url,
                )
            if "baidu.com/link" in url:
                return FakeResponse(
                    status_code=302,
                    headers={"Location": "https://example.com/real-variable"},
                    url=url,
                )
            if "bing.com/search" in url:
                return FakeResponse("<html></html>", url=url)
            raise AssertionError(f"unexpected URL: {url}")

        with patch("tools.search.websearch.requests.get", side_effect=fake_get):
            results = search(
                "变量定义",
                top_k=3,
                endpoint="http://localhost:8090/search",
                timeout=5,
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/real-variable")


if __name__ == "__main__":
    unittest.main()
