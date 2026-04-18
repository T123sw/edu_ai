import os
import sys
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


SELENIUM_WAY_DIR = Path(__file__).resolve().parents[1] / "src" / "selenium_way"
if str(SELENIUM_WAY_DIR) not in sys.path:
    sys.path.insert(0, str(SELENIUM_WAY_DIR))

import methods  # noqa: E402


class FakeResponse:
    def __init__(self, content, content_type="image/jpeg", status_code=200):
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class ImageHelperTests(unittest.TestCase):
    def test_extract_image_urls_from_html_supports_common_attrs(self):
        html = """
        <html>
            <body>
                <img src="/static/a.jpg" />
                <img data-src="https://cdn.example.com/b.png?x=1" />
                <img srcset="/img/c-small.webp 1x, /img/c-large.webp 2x" />
                <img src="data:image/png;base64,abcd" />
                <img src="/icons/logo.svg" />
                <source data-srcset="//cdn.example.com/d.jpeg 1x, //cdn.example.com/d@2x.jpeg 2x" />
            </body>
        </html>
        """

        image_urls = methods.extract_image_urls_from_html(html, "https://example.com/articles/1")

        self.assertEqual(
            image_urls,
            [
                "https://example.com/static/a.jpg",
                "https://cdn.example.com/b.png?x=1",
                "https://example.com/img/c-small.webp",
                "https://cdn.example.com/d.jpeg",
            ],
        )

    def test_guess_image_suffix_prefers_url_then_content_type(self):
        self.assertEqual(methods.guess_image_suffix("https://example.com/a.png?size=1"), ".png")
        self.assertEqual(methods.guess_image_suffix("https://example.com/download", "image/webp"), ".webp")
        self.assertEqual(methods.guess_image_suffix("https://example.com/download", "application/octet-stream"), ".jpg")

    def test_download_images_from_page_saves_unique_files(self):
        html = """
        <html>
            <body>
                <img src="https://example.com/assets/cover" />
                <img src="https://example.com/assets/cover?variant=2" />
                <img src="https://example.com/assets/diagram.png" />
            </body>
        </html>
        """

        def fake_get(url, headers=None, timeout=None):
            if "diagram" in url:
                return FakeResponse(b"png-bytes", "image/png")
            return FakeResponse(b"jpeg-bytes", "image/jpeg")

        tmpdir = Path(__file__).resolve().parent / f"_tmp_image_test_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            with patch.object(methods.requests, "get", side_effect=fake_get):
                saved_files = methods.download_images_from_page(
                    output_dir=str(tmpdir),
                    html=html,
                    page_url="https://example.com/post/42",
                    page_name="example-post",
                )

            basenames = sorted(os.path.basename(path) for path in saved_files)
            self.assertEqual(
                basenames,
                [
                    "example-post_001.jpg",
                    "example-post_002.jpg",
                    "example-post_003.png",
                ],
            )
            for path in saved_files:
                self.assertTrue(os.path.exists(path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
