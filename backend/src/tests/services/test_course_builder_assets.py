from __future__ import annotations

from app.services import course_knowledge_builder as builder


def test_materialize_remote_assets_downloads_and_rewrites_images(monkeypatch, tmp_path) -> None:
    class Response:
        status_code = 200
        content = b"png-bytes"
        headers = {"content-type": "image/png"}

        @staticmethod
        def raise_for_status():
            return None

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        @staticmethod
        def get(url):
            assert url == "https://raw.githubusercontent.com/org/repo/rev/chapter/assets/chart.png"
            return Response()

    monkeypatch.setattr(builder.httpx, "Client", Client)

    rewritten, assets = builder._materialize_remote_assets(
        "正文\n\n![复杂度图](assets/chart.png)",
        raw_url="https://raw.githubusercontent.com/org/repo/rev/chapter/page.md",
        asset_dir=tmp_path / "lesson.assets",
        markdown_asset_prefix="lesson.assets",
        allowed_hosts=("raw.githubusercontent.com",),
    )

    assert "assets/chart.png" not in rewritten
    assert "lesson.assets/" in rewritten
    assert len(assets) == 1
    assert (tmp_path / assets[0]["relative_path"]).is_file()

