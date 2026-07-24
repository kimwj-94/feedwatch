from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from crawler.general import crawl_general_source
from shared.models import Item, Source


def response_with(html: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=html.encode(),
        headers={"Content-Type": "text/html"},
        text=html,
        url="https://example.com/list",
        raise_for_status=lambda: None,
    )


class GeneralCrawlerTests(unittest.TestCase):
    def test_static_selector_collects_links_without_browser(self) -> None:
        source = Source(
            id="src_1",
            name="Board",
            url="https://example.com/list",
            selector=".posts a",
        )
        with patch("crawler.general.requests.get", return_value=response_with(
            '<div class="posts"><a href="/post/1"> First post </a></div>'
        )), patch("crawler.general._crawl_rendered_page") as rendered:
            items = crawl_general_source(source)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "First post")
        self.assertEqual(items[0].url, "https://example.com/post/1")
        rendered.assert_not_called()

    def test_render_js_uses_browser_when_static_html_has_no_matching_nodes(self) -> None:
        source = Source(
            id="src_1",
            name="Dynamic board",
            url="https://example.com/list",
            selector="#boardList a",
            metadata={"render_js": True},
        )
        rendered_item = Item(
            id="item_1",
            source_id=source.id,
            source_name=source.name,
            group_ids=[],
            title="Rendered post",
            url="https://example.com/post/1",
            hash="hash",
        )
        with patch("crawler.general.requests.get", return_value=response_with(
            '<tbody id="boardList"></tbody>'
        )), patch(
            "crawler.general._crawl_rendered_page",
            return_value=[rendered_item],
        ) as rendered:
            items = crawl_general_source(source)

        self.assertEqual(items, [rendered_item])
        rendered.assert_called_once_with(source, "#boardList a", 20)

    def test_missing_static_selector_still_fails_without_render_opt_in(self) -> None:
        source = Source(
            id="src_1",
            name="Board",
            url="https://example.com/list",
            selector="#missing a",
        )
        with patch("crawler.general.requests.get", return_value=response_with("<html></html>")):
            with self.assertRaisesRegex(RuntimeError, "선택자에 맞는 글이 없습니다"):
                crawl_general_source(source)


if __name__ == "__main__":
    unittest.main()
