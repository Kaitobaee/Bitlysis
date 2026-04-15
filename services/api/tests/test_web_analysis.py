from bs4 import BeautifulSoup

import app.services.web_analyzer as web_analyzer

from app.services.web_analyzer import (
    _build_website_screenshot_url,
    _compose_argumentative_summary,
    _discover_related_websites_from_text,
    _extract_news_related_links,
    _is_generic_news_summary,
    _extract_outline_from_soup,
    _extract_related_websites,
    analyze_url_or_text,
)


def test_web_analysis_text_output_is_richer():
    result = analyze_url_or_text(
        "Bitlysis la mot ung dung phan tich du lieu voi CTA ro rang va 24 mau du lieu.",
        "business",
    )

    assert result.website_screenshot is None
    assert result.highlights
    assert result.recommendations
    assert result.evidence
    assert result.findings


def test_web_summary_focuses_on_content_not_counts():
    result = analyze_url_or_text(
        "Trường tập trung đào tạo theo định hướng ứng dụng, mở rộng hợp tác quốc tế và tăng cường hỗ trợ học tập cho sinh viên.",
        "academic",
    )

    summary_lower = result.summary.lower()
    assert "từ," not in summary_lower
    assert "câu," not in summary_lower
    assert "đoạn" not in summary_lower


def test_web_analysis_screenshot_url_for_web_pages():
    web_analyzer._capture_real_website_screenshot = lambda _url: b"fakepng"  # type: ignore[attr-defined]
    screenshot_url = _build_website_screenshot_url("https://example.com/path?q=1")

    assert screenshot_url is not None
    assert screenshot_url.startswith("data:image/png;base64,")


def test_web_analysis_outline_ignores_navigation_headings():
        soup = BeautifulSoup(
                """
                <html>
                    <body>
                        <nav><h2>Language Toggle navigation</h2></nav>
                        <main>
                            <h1>Trường Đại Học Văn Hiến</h1>
                            <h2>Giới thiệu</h2>
                        </main>
                        <footer><h3>Footer Menu</h3></footer>
                    </body>
                </html>
                """,
                "html.parser",
        )

        outline = _extract_outline_from_soup(soup)
        texts = [node.text for node in outline]

        assert "Trường Đại Học Văn Hiến" in texts
        assert all("navigation" not in text.lower() for text in texts)
        assert all("footer" not in text.lower() for text in texts)


def test_web_analysis_summary_prefix_is_not_duplicated():
        summary = _compose_argumentative_summary(
                analysis_mode="business",
                base_summary="Góc nhìn kinh doanh: Phân tích kinh doanh: nguồn url 'Trường Đại Học Văn Hiến' tập trung vào sinh, khoa, tuy.",
                findings=[
                        "Trọng tâm kinh doanh: cơ hội, rủi ro, tác động, và ưu tiên hành động.",
                        "Cần ưu tiên quyết định theo giá trị tạo ra và chi phí cơ hội.",
                ],
                evidence=[{"label": "Độ dài nội dung", "detail": "35 câu, 1 đoạn được trích xuất."}],
                recommendations=["Ưu tiên 1-2 hành động có tác động cao và chi phí thực thi thấp."],
        )

        assert "Góc nhìn kinh doanh: Phân tích kinh doanh:" not in summary


def test_extract_related_websites_from_html_links():
        soup = BeautifulSoup(
                """
                <html>
                    <body>
                        <main>
                            <a href="/gioi-thieu">Giới thiệu</a>
                            <a href="https://example.org/tin-tuc">Tin tức học thuật</a>
                            <a href="#top">Top</a>
                        </main>
                    </body>
                </html>
                """,
                "html.parser",
        )

        related = _extract_related_websites(soup, "https://vanhien.edu.vn/")

        assert len(related) == 2
        assert related[0]["relation"] == "internal"
        assert related[1]["relation"] == "external"


def test_discover_related_websites_from_text_returns_empty_for_too_short_input():
    related = _discover_related_websites_from_text("A")
    assert related == []


def test_text_analysis_includes_related_websites_with_summary(monkeypatch):
    monkeypatch.setattr(
        web_analyzer,
        "_discover_related_websites_from_text",
        lambda _text, max_items=4: [
            {
                "title": "Machine learning",
                "url": "https://en.wikipedia.org/wiki/Machine_learning",
                "relation": "related",
                "summary": "Tổng quan về học máy và các phương pháp huấn luyện mô hình.",
            }
        ],
    )

    result = analyze_url_or_text(
        "Nội dung tập trung vào trí tuệ nhân tạo, học máy và ứng dụng trong giáo dục.",
        "business",
    )

    assert result.source_type == "text"
    assert result.related_websites
    assert result.related_websites[0]["url"].startswith("https://")
    assert result.related_websites[0]["summary"]


def test_discover_related_websites_from_text_prioritizes_news(monkeypatch):
    monkeypatch.setattr(web_analyzer, "_extract_urls_from_text", lambda _text, max_items=4: [])
    monkeypatch.setattr(
        web_analyzer,
        "_extract_news_related_links",
        lambda _keywords, max_items=4: [
            {
                "title": "Bài báo AI giáo dục",
                "url": "https://news.example.com/ai-giao-duc",
                "relation": "news",
                "summary": "Bài báo phân tích xu hướng AI trong giáo dục.",
            }
        ],
    )
    monkeypatch.setattr(
        web_analyzer,
        "_extract_wikipedia_related_links",
        lambda _keywords, max_items=4: [
            {
                "title": "Fallback wiki",
                "url": "https://vi.wikipedia.org/wiki/Tri_tue_nhan_tao",
                "relation": "related",
                "summary": "Mô tả tri thức nền.",
            }
        ],
    )

    related = _discover_related_websites_from_text(
        "Nội dung nói về AI trong giáo dục và ứng dụng thực tế tại trường học.",
        max_items=2,
    )

    assert related
    assert related[0]["relation"] == "news"
    assert "summary" in related[0]


def test_extract_news_related_links_returns_list_for_empty_keywords():
    related = _extract_news_related_links([])
    assert related == []


def test_detect_generic_google_news_summary_text():
    sample = "Comprehensive up-to-date news coverage, aggregated from sources all over the world by Google News."
    assert _is_generic_news_summary(sample)