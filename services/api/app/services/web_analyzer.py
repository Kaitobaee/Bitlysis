from __future__ import annotations

import json
import logging
import html
import re
import base64
import shutil
import subprocess
import tempfile
from collections import Counter
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import Settings, get_settings
from app.schemas.web_analysis import (
    CTAInfo,
    DataFact,
    HeadingNode,
    WebAnalysisChatResponse,
    WebAnalyzeResponse,
    WebChart,
)

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "into", "your", "have", "will", "are", "was", "were",
    "cua", "cho", "voi", "mot", "nhung", "trong", "khi", "duoc", "nguoi", "nhieu", "nhat", "tren", "dang",
    "https", "http", "www", "com", "html", "head", "body",
}


CTA_KEYWORDS = [
    "buy", "subscribe", "download", "learn more", "sign up", "register", "join", "get started", "contact", "order",
]

MODE_LABELS = {
    "academic": "báo cáo học thuật",
    "marketing_seo": "marketing/SEO",
    "business": "phân tích kinh doanh",
}


MODE_LENS = {
    "academic": {
        "summary_lead": "Góc nhìn học thuật",
        "findings": [
            "Luận điểm trung tâm cần được trình bày rõ theo cấu trúc vấn đề - phân tích - kết luận.",
            "Độ tin cậy học thuật phụ thuộc vào tính nhất quán khái niệm và chất lượng bằng chứng đối chiếu.",
        ],
        "highlights": [
            "Đánh giá ưu tiên bối cảnh nghiên cứu, logic lập luận, và giá trị tri thức của nội dung.",
            "Trọng tâm là mối liên hệ giữa luận điểm, bằng chứng, và hàm ý học thuật.",
        ],
        "recommendations": [
            "Bổ sung trích dẫn, giới hạn phạm vi, và mô tả phương pháp để tăng độ vững của kết luận.",
            "Chuẩn hóa thuật ngữ học thuật và cấu trúc lại các đoạn theo mạch lập luận rõ ràng.",
        ],
        "sections": [
            {"heading": "Bối cảnh và mục tiêu", "snippet": "Phần này làm rõ bối cảnh, đối tượng, và mục tiêu tri thức để định vị vấn đề nghiên cứu."},
            {"heading": "Bằng chứng và lập luận", "snippet": "Phần này đánh giá chất lượng bằng chứng và kiểm tra độ mạch lạc của chuỗi lập luận."},
        ],
    },
    "marketing_seo": {
        "summary_lead": "Góc nhìn marketing/SEO",
        "findings": [
            "Trọng tâm marketing: thông điệp, intent, keyword, và luồng CTA.",
            "Cần ưu tiên khả năng chuyển đổi và mức độ rõ ràng của lợi ích.",
        ],
        "highlights": [
            "Đánh giá theo phễu intent tìm kiếm và mức độ phủ keyword.",
            "Kiểm tra sự liên kết giữa tiêu đề, nội dung chính, và hành động mong muốn.",
        ],
        "recommendations": [
            "Tối ưu thông điệp giá trị ở phần đầu trang và CTA theo một mục tiêu chính.",
            "Nhóm keyword theo cluster và gắn với landing intent cụ thể.",
        ],
        "sections": [
            {"heading": "Thông điệp và định vị", "snippet": "Đánh giá sự rõ ràng của thông điệp và sự khác biệt giá trị."},
            {"heading": "Keyword, intent, CTA", "snippet": "Tóm tắt cơ hội tối ưu keyword, intent, và hành trình chuyển đổi."},
        ],
    },
    "business": {
        "summary_lead": "Góc nhìn kinh doanh",
        "findings": [
            "Trọng tâm kinh doanh: cơ hội, rủi ro, tác động, và ưu tiên hành động.",
            "Cần ưu tiên quyết định theo giá trị tạo ra và chi phí cơ hội.",
        ],
        "highlights": [
            "Đánh giá theo tác động đến kết quả kinh doanh và vận hành.",
            "Nhận diện nhanh các điểm nghẽn ảnh hưởng đến hiệu quả thực thi.",
        ],
        "recommendations": [
            "Ưu tiên 1-2 hành động có tác động cao và chi phí thực thi thấp.",
            "Đặt KPI đo lường rõ ràng cho từng bước cải tiến.",
        ],
        "sections": [
            {"heading": "Cơ hội và rủi ro", "snippet": "Tổng hợp điểm cơ hội, rủi ro, và mức độ ưu tiên theo tác động."},
            {"heading": "Kế hoạch hành động", "snippet": "Đề xuất bước triển khai ngắn hạn và KPI theo dõi kết quả."},
        ],
    },
}


def _compose_argumentative_summary(
    *,
    analysis_mode: str,
    base_summary: str,
    findings: list[str],
    evidence: list[dict[str, str]],
    recommendations: list[str],
) -> str:
    opening = _strip_redundant_summary_prefix(base_summary)
    if not opening:
        opening = "Nội dung được đánh giá theo cấu trúc lập luận và mục tiêu phân tích."

    thesis = _clean_text(findings[0]) if findings else "Luận điểm trung tâm chưa được trình bày đầy đủ."
    argument = _clean_text(findings[1]) if len(findings) > 1 else "Căn cứ lập luận cần được bổ sung để nâng cao tính thuyết phục."

    evidence_line = ""
    if evidence:
        first_evidence = evidence[0]
        label = _clean_text(str(first_evidence.get("label", "bang chung")))
        detail = _clean_text(str(first_evidence.get("detail", "")))
        if label and detail:
            evidence_line = f"Bằng chứng sơ bộ cho thấy {label.lower()}: {detail}."

    action = _clean_text(recommendations[0]) if recommendations else "Cần tiếp tục đối chiếu với bằng chứng bổ sung trước khi kết luận cuối cùng."

    mode_tail_map = {
        "academic": "Kết luận học thuật nên nhấn mạnh tính nhất quán khái niệm và giới hạn phạm vi diễn giải.",
        "marketing_seo": "Kết luận thực thi nên gắn trực tiếp với intent tìm kiếm và đề xuất tối ưu chuyển đổi.",
        "business": "Kết luận kinh doanh nên quy đổi rõ ràng thành ưu tiên hành động và tác động kỳ vọng.",
    }
    tail = mode_tail_map.get(analysis_mode, mode_tail_map["business"])

    parts = [
        opening,
        f"Luận điểm trung tâm: {thesis}",
        f"Phân tích bổ trợ: {argument}",
        evidence_line,
        f"Hàm ý hành động: {action}",
        tail,
    ]
    return " ".join([part for part in parts if part])


def _is_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _sanitize_extracted_text(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    cleaned = re.sub(r"##LOC\[[^\]]*\]##", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(language\s+toggle\s+navigation|toggle\s+navigation)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _ensure_findings_have_evidence(findings: list[str], evidence: list[dict[str, str]]) -> list[str]:
    if not findings:
        return findings
    if not evidence:
        return findings

    out: list[str] = []
    for idx, finding in enumerate(findings):
        finding_text = _clean_text(finding)
        if not finding_text:
            continue
        if "bằng chứng:" in finding_text.lower():
            out.append(finding_text)
            continue
        ev = evidence[idx % len(evidence)]
        ev_detail = _clean_text(str(ev.get("detail", "")))
        if ev_detail:
            out.append(f"{finding_text} Bằng chứng: {ev_detail}.")
        else:
            out.append(finding_text)
    return out


def _strip_redundant_summary_prefix(summary: str) -> str:
    cleaned = _clean_text(summary)
    if not cleaned:
        return ""

    cleaned = re.sub(r"^(?:[^:]{1,80}:\s*)+", "", cleaned)
    return cleaned


def _extract_keywords(text: str, limit: int = 8) -> tuple[list[str], list[int]]:
    words = re.findall(r"[a-zA-ZA-Za-z0-9]{3,}", text.lower())
    filtered = [word for word in words if word not in _STOPWORDS]
    freq = Counter(filtered)
    common = freq.most_common(limit)
    return [word for word, _ in common], [count for _, count in common]


def _extract_data_facts(text: str) -> list[DataFact]:
    facts: list[DataFact] = []
    number_patterns = [
        (r"(\d+(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\s*%", "percentage"),
        (r"\$\s*(\d+(?:[.,]\d{3})*(?:\.\d{1,2})?)", "currency"),
        (r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})", "date"),
        (r"\b(\d+(?:[.,]\d{3})*)\b", "number"),
    ]

    for pattern, fact_type in number_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(0)
            start = max(0, match.start() - 60)
            context = text[start:match.end()]
            parts = context.split()
            label = parts[-2] if len(parts) > 1 else fact_type
            facts.append(DataFact(label=label[:30], value=value, type=fact_type))

    return facts[:10]


def _extract_outline_from_soup(soup: BeautifulSoup) -> list[HeadingNode]:
    roots = soup.select("main, article, [role='main'], .content, .post-content, .entry-content")
    if not roots:
        roots = [soup]

    headings: list = []
    for root in roots:
        headings.extend(root.select("h1, h2, h3"))
    if not headings:
        return []

    stack: list[dict[str, int | HeadingNode]] = []
    result: list[HeadingNode] = []
    blocked_terms = [
        "menu",
        "navigation",
        "language",
        "toggle",
        "login",
        "register",
        "search",
        "footer",
        "header",
        "breadcrumb",
        "#loc",
    ]

    for heading in headings:
        level = int(heading.name[1])
        text = _clean_text(heading.get_text())
        if not text:
            continue
        if len(text) > 120:
            continue
        text_lower = text.lower()
        if any(term in text_lower for term in blocked_terms):
            continue
        if heading.find_parent(["nav", "footer", "aside", "header"]):
            continue
        node = HeadingNode(level=level, text=text)

        while stack and int(stack[-1]["level"]) >= level:
            stack.pop()

        if not stack:
            result.append(node)
        else:
            parent = stack[-1]["node"]
            if isinstance(parent, HeadingNode):
                parent.children.append(node)

        stack.append({"level": level, "node": node})

    return result


def _detect_cta(soup: BeautifulSoup) -> CTAInfo | None:
    for tag in soup.select("button, a[href]"):
        text_raw = _clean_text(tag.get_text())
        text = text_raw.lower()
        for keyword in CTA_KEYWORDS:
            if keyword in text:
                tag_type = "button" if tag.name == "button" else "link"
                return CTAInfo(text=text_raw[:120], type=tag_type, action_keyword=keyword.title())
    return None


def _extract_related_websites(soup: BeautifulSoup, current_url: str, *, max_items: int = 6) -> list[dict[str, str]]:
    current = urlparse(current_url)
    current_host = current.netloc.lower()
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    for tag in soup.select("a[href]"):
        href = _clean_text(str(tag.get("href", "")))
        if not href:
            continue
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        absolute = urljoin(current_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue

        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if not normalized or normalized in seen or normalized == current_url.rstrip("/"):
            continue
        seen.add(normalized)

        anchor_text = _clean_text(tag.get_text(" "))
        if anchor_text:
            title = anchor_text[:90]
        else:
            path_tail = parsed.path.rstrip("/").split("/")[-1]
            title = path_tail[:90] if path_tail else parsed.netloc

        relation = "internal" if parsed.netloc.lower() == current_host else "external"
        out.append({"title": title or parsed.netloc, "url": normalized, "relation": relation})
        if len(out) >= max_items:
            break

    return out


def _extract_urls_from_text(text: str, *, max_items: int = 4) -> list[str]:
    matches = re.findall(r"https?://[^\s\]\[\)<>'\"]+", text, flags=re.IGNORECASE)
    out: list[str] = []
    seen: set[str] = set()
    for raw in matches:
        url = raw.rstrip(".,;:!?)\"]'")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= max_items:
            break
    return out


def _summarize_related_url(url: str, *, timeout_seconds: float = 8.0) -> str:
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
    except Exception:  # noqa: BLE001
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    title = _clean_text(soup.title.get_text(" ") if soup.title else "")
    description = ""
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.IGNORECASE)})
    if meta_desc and meta_desc.get("content"):
        description = _clean_text(str(meta_desc.get("content")))

    first_paragraph = ""
    for p in soup.select("p"):
        candidate = _clean_text(p.get_text(" "))
        if len(candidate) >= 40:
            first_paragraph = candidate
            break

    summary_parts = [part for part in [description, first_paragraph] if part]
    summary = " ".join(summary_parts)
    if not summary:
        summary = title
    return summary[:260]


def _resolve_news_article_url(url: str, *, timeout_seconds: float = 8.0) -> str:
    parsed = urlparse(url)
    if parsed.netloc.lower() != "news.google.com":
        return url

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                },
            )
            final_url = str(response.url)
            final_host = urlparse(final_url).netloc.lower()
            if final_url.startswith(("http://", "https://")) and final_host and final_host != "news.google.com":
                return final_url
    except Exception:  # noqa: BLE001
        return url

    return url


def _is_generic_news_summary(text: str) -> bool:
    normalized = _clean_text(text).lower()
    generic_patterns = [
        "comprehensive up-to-date news coverage",
        "aggregated from sources all over the world by google news",
        "google news",
    ]
    return any(pattern in normalized for pattern in generic_patterns)


def _summarize_article_with_ai(settings: Settings, *, title: str, url: str, context_text: str) -> str:
    if not settings.llm_enabled:
        return ""

    seed = _clean_text(context_text)
    if not seed:
        seed = _clean_text(title)

    prompt = (
        "Bạn là AI tóm tắt báo chí. Hãy tóm tắt bài báo thành 1-2 câu tiếng Việt, nêu ý chính và tác động. "
        "Không nói chung chung, không lặp lại tên trang, không thêm dữ kiện ngoài nội dung đã cho.\n\n"
        f"Tiêu đề: {title}\n"
        f"URL: {url}\n"
        f"Nội dung tham chiếu: {seed[:1200]}\n"
    )
    messages = [
        {"role": "system", "content": "Trả lời ngắn gọn, rõ ràng, tiếng Việt, tối đa 2 câu."},
        {"role": "user", "content": prompt},
    ]

    ai_text: str | None = None
    try:
        ai_text = _call_openai_text(settings, messages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("article_summary_openai_fallback: %s", type(exc).__name__)

    if not ai_text:
        try:
            ai_text = _call_openrouter_text(settings, messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("article_summary_openrouter_fallback: %s", type(exc).__name__)

    if not ai_text:
        return ""

    cleaned = _clean_text(ai_text)
    if _is_generic_news_summary(cleaned):
        return ""
    return cleaned[:280]


def _extract_publisher_article_link(item: BeautifulSoup, fallback_link: str) -> str:
    if not fallback_link.startswith(("http://", "https://")):
        return fallback_link

    parsed_fallback = urlparse(fallback_link)
    if parsed_fallback.netloc.lower() != "news.google.com":
        return fallback_link

    desc_tag = item.find("description")
    if not desc_tag:
        return fallback_link

    desc_html = html.unescape(desc_tag.get_text(" "))
    desc_soup = BeautifulSoup(desc_html, "html.parser")
    for anchor in desc_soup.select("a[href]"):
        candidate = _clean_text(str(anchor.get("href", "")))
        if not candidate.startswith(("http://", "https://")):
            continue
        candidate_host = urlparse(candidate).netloc.lower()
        if candidate_host and candidate_host != "news.google.com":
            return candidate

    return fallback_link


def _extract_news_related_links(keywords: list[str], *, max_items: int = 4) -> list[dict[str, str]]:
    if not keywords:
        return []

    query = " ".join(keywords[:4]).strip()
    if len(query) < 4:
        return []

    rss_url = (
        "https://news.google.com/rss/search"
        f"?q={quote(query)}"
        "&hl=vi&gl=VN&ceid=VN:vi"
    )

    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            response = client.get(rss_url)
            response.raise_for_status()
    except Exception:  # noqa: BLE001
        return []

    feed = BeautifulSoup(response.text, "xml")
    items = feed.find_all("item")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    settings = get_settings()

    for item in items:
        link_tag = item.find("link")
        title_tag = item.find("title")
        desc_tag = item.find("description")
        if not link_tag:
            continue

        link = _clean_text(link_tag.get_text(" "))
        if not link.startswith(("http://", "https://")):
            continue
        link = _extract_publisher_article_link(item, link)
        link = _resolve_news_article_url(link)
        if link in seen:
            continue
        seen.add(link)

        title = _clean_text(title_tag.get_text(" ")) if title_tag else ""
        rss_summary = _clean_text(html.unescape(desc_tag.get_text(" "))) if desc_tag else ""
        if _is_generic_news_summary(rss_summary):
            rss_summary = ""
        page_summary = _summarize_related_url(link)
        if _is_generic_news_summary(page_summary):
            page_summary = ""
        seed_summary = page_summary or rss_summary or title
        ai_summary = _summarize_article_with_ai(
            settings,
            title=title,
            url=link,
            context_text=seed_summary,
        )
        summary = ai_summary or seed_summary

        out.append(
            {
                "title": title[:90] or urlparse(link).netloc,
                "url": link,
                "relation": "news",
                "summary": summary[:260],
            }
        )
        if len(out) >= max_items:
            break

    return out


def _extract_wikipedia_related_links(keywords: list[str], *, max_items: int = 4) -> list[dict[str, str]]:
    if not keywords:
        return []

    query = " ".join(keywords[:3]).strip()
    if len(query) < 4:
        return []

    endpoints = [
        "https://vi.wikipedia.org/w/api.php",
        "https://en.wikipedia.org/w/api.php",
    ]

    out: list[dict[str, str]] = []
    seen: set[str] = set()

    for endpoint in endpoints:
        try:
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                response = client.get(
                    endpoint,
                    params={
                        "action": "opensearch",
                        "search": query,
                        "limit": max_items,
                        "namespace": 0,
                        "format": "json",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:  # noqa: BLE001
            continue

        if not isinstance(payload, list) or len(payload) < 4:
            continue

        titles = payload[1] if isinstance(payload[1], list) else []
        descriptions = payload[2] if isinstance(payload[2], list) else []
        urls = payload[3] if isinstance(payload[3], list) else []

        for idx, link in enumerate(urls):
            link_str = _clean_text(str(link))
            if not link_str or not link_str.startswith(("http://", "https://")):
                continue
            if link_str in seen:
                continue
            seen.add(link_str)

            title = _clean_text(str(titles[idx])) if idx < len(titles) else ""
            summary = _clean_text(str(descriptions[idx])) if idx < len(descriptions) else ""
            out.append(
                {
                    "title": title or urlparse(link_str).netloc,
                    "url": link_str,
                    "relation": "related",
                    "summary": summary[:260],
                }
            )
            if len(out) >= max_items:
                return out

    return out


def _discover_related_websites_from_text(text: str, *, max_items: int = 4) -> list[dict[str, str]]:
    cleaned = _clean_text(text)
    # Allow short but meaningful keyword queries (e.g., "web3", "fintech", "ai")
    # to still trigger related-article discovery.
    if len(cleaned) < 3:
        return []

    out: list[dict[str, str]] = []
    seen: set[str] = set()

    # 1) Use URLs already mentioned in user content first.
    embedded_urls = _extract_urls_from_text(text, max_items=max_items)
    for url in embedded_urls:
        if url in seen:
            continue
        seen.add(url)
        parsed = urlparse(url)
        title = parsed.path.rstrip("/").split("/")[-1] or parsed.netloc
        summary = _summarize_related_url(url)
        out.append(
            {
                "title": _clean_text(title)[:90] or parsed.netloc,
                "url": url,
                "relation": "mentioned",
                "summary": summary,
            }
        )
        if len(out) >= max_items:
            return out

    # 2) Discover related news articles by keywords.
    labels, _ = _extract_keywords(cleaned, limit=6)
    discovered_news = _extract_news_related_links(labels, max_items=max_items)
    for item in discovered_news:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(
            {
                "title": _clean_text(item.get("title", ""))[:90],
                "url": _clean_text(url),
                "relation": "news",
                "summary": _clean_text(item.get("summary", ""))[:260],
            }
        )
        if len(out) >= max_items:
            return out

    # 3) Fallback to knowledge links when news links are insufficient.
    remaining = max(0, max_items - len(out))
    discovered = _extract_wikipedia_related_links(labels, max_items=remaining or max_items)
    for item in discovered:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(
            {
                "title": _clean_text(item.get("title", ""))[:90],
                "url": _clean_text(url),
                "relation": "related",
                "summary": _clean_text(item.get("summary", ""))[:260],
            }
        )
        if len(out) >= max_items:
            break

    return out


def _safe_str_list(value: object, *, max_items: int, max_chars: int = 220) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        item_str = _clean_text(str(item))
        if item_str:
            out.append(item_str[:max_chars])
        if len(out) >= max_items:
            break
    return out


def _safe_sections(value: object, *, max_items: int = 6) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        heading = _clean_text(str(item.get("heading", "")))[:120]
        snippet = _clean_text(str(item.get("snippet", "")))[:320]
        if heading and snippet:
            out.append({"heading": heading, "snippet": snippet})
        if len(out) >= max_items:
            break
    return out


def _safe_string_list(value: object, *, max_items: int = 6, max_chars: int = 220) -> list[str]:
    return _safe_str_list(value, max_items=max_items, max_chars=max_chars)


def _safe_evidence(value: object, *, max_items: int = 6) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = _clean_text(str(item.get("label", "")))[:120]
        detail = _clean_text(str(item.get("detail", "")))[:320]
        if label and detail:
            out.append({"label": label, "detail": detail})
        if len(out) >= max_items:
            break
    return out


def _dedupe_keep_order(values: list[str], *, max_items: int = 6) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        v = _clean_text(raw)
        if not v:
            continue
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
        if len(out) >= max_items:
            break
    return out


def _merge_sections(primary: list[dict[str, str]], secondary: list[dict[str, str]], *, max_items: int = 6) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in [*primary, *secondary]:
        heading = _clean_text(str(item.get("heading", "")))[:120]
        snippet = _clean_text(str(item.get("snippet", "")))[:320]
        if not heading or not snippet:
            continue
        key = f"{heading.lower()}::{snippet.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"heading": heading, "snippet": snippet})
        if len(out) >= max_items:
            break
    return out


def _apply_mode_lens(
    *,
    analysis_mode: str,
    summary: str,
    findings: list[str],
    highlights: list[str],
    recommendations: list[str],
    sections: list[dict[str, str]],
    evidence: list[dict[str, str]],
) -> tuple[str, list[str], list[str], list[str], list[dict[str, str]], list[dict[str, str]]]:
    profile = MODE_LENS.get(analysis_mode, MODE_LENS["business"])
    lead = str(profile["summary_lead"])
    base_summary = _strip_redundant_summary_prefix(summary)
    summary = f"{lead}: {base_summary}" if base_summary else lead

    findings_out = _dedupe_keep_order([*profile["findings"], *findings], max_items=6)
    highlights_out = _dedupe_keep_order([*profile["highlights"], *highlights], max_items=6)
    recommendations_out = _dedupe_keep_order([*profile["recommendations"], *recommendations], max_items=6)
    sections_out = _merge_sections(profile["sections"], sections, max_items=6)

    mode_evidence = {
        "label": "Mode lens",
        "detail": f"Đầu ra được điều chỉnh theo chế độ {analysis_mode}.",
    }
    evidence_out = [mode_evidence]
    seen_ev: set[str] = {f"{mode_evidence['label']}::{mode_evidence['detail']}".lower()}
    for item in evidence:
        label = _clean_text(str(item.get("label", "")))[:120]
        detail = _clean_text(str(item.get("detail", "")))[:320]
        if not label or not detail:
            continue
        key = f"{label}::{detail}".lower()
        if key in seen_ev:
            continue
        seen_ev.add(key)
        evidence_out.append({"label": label, "detail": detail})
        if len(evidence_out) >= 6:
            break

    return summary, findings_out, highlights_out, recommendations_out, sections_out, evidence_out


def _find_browser_executable() -> str | None:
    candidates = [
        shutil.which("chrome"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _capture_real_website_screenshot(source_url: str) -> bytes | None:
    browser = _find_browser_executable()
    if not browser:
        return None

    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = f"{temp_dir}\\website.png"
        command = [
            browser,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--window-size=1440,1800",
            "--virtual-time-budget=5000",
            f"--screenshot={output_path}",
            source_url,
        ]
        try:
            completed = subprocess.run(command, check=True, capture_output=True, timeout=30)
        except Exception as exc:  # noqa: BLE001
            logger.warning("website_screenshot_capture_failed: %s", type(exc).__name__)
            return None

        if completed.returncode != 0:
            return None
        try:
            with open(output_path, "rb") as handle:
                return handle.read()
        except OSError:
            return None


def _build_website_screenshot_url(source_url: str) -> str | None:
    parsed = urlparse(source_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    screenshot_bytes = _capture_real_website_screenshot(source_url)
    if screenshot_bytes:
        return f"data:image/png;base64,{base64.b64encode(screenshot_bytes).decode('ascii')}"

    source_text = _clean_text(source_url)
    host_text = _clean_text(parsed.netloc)
    preview_lines = [
        "Website preview",
        host_text,
        source_text[:72],
    ]
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='780' viewBox='0 0 1200 780'>"
        "<defs>"
        "<linearGradient id='bg' x1='0' x2='1' y1='0' y2='1'>"
        "<stop offset='0%' stop-color='#f8fafc'/>"
        "<stop offset='55%' stop-color='#eef2ff'/>"
        "<stop offset='100%' stop-color='#ffffff'/>"
        "</linearGradient>"
        "<linearGradient id='bar' x1='0' x2='1' y1='0' y2='0'>"
        "<stop offset='0%' stop-color='#0f766e'/>"
        "<stop offset='100%' stop-color='#2563eb'/>"
        "</linearGradient>"
        "</defs>"
        "<rect width='1200' height='780' rx='36' fill='url(#bg)'/>"
        "<rect x='58' y='54' width='1084' height='86' rx='22' fill='#ffffff' stroke='#dbe4ee'/>"
        "<rect x='84' y='78' width='220' height='22' rx='11' fill='url(#bar)' opacity='0.9'/>"
        "<rect x='84' y='112' width='620' height='12' rx='6' fill='#cbd5e1' opacity='0.9'/>"
        "<rect x='720' y='76' width='336' height='26' rx='13' fill='#e2e8f0'/>"
        "<rect x='720' y='110' width='182' height='14' rx='7' fill='#cbd5e1'/>"
        "<rect x='58' y='170' width='1084' height='552' rx='28' fill='#ffffff' stroke='#dbe4ee'/>"
        "<rect x='92' y='208' width='460' height='220' rx='24' fill='#f8fafc' stroke='#dbe4ee'/>"
        "<rect x='572' y='208' width='536' height='220' rx='24' fill='#f8fafc' stroke='#dbe4ee'/>"
        "<rect x='92' y='456' width='1016' height='230' rx='24' fill='#f8fafc' stroke='#dbe4ee'/>"
        "<text x='128' y='262' font-family='Arial, sans-serif' font-size='30' font-weight='700' fill='#0f172a'>"
        f"{html.escape(preview_lines[0])}"
        "</text>"
        "<text x='128' y='305' font-family='Arial, sans-serif' font-size='22' fill='#334155'>"
        f"{html.escape(preview_lines[1])}"
        "</text>"
        "<text x='128' y='350' font-family='Arial, sans-serif' font-size='20' fill='#475569'>"
        f"{html.escape(preview_lines[2])}"
        "</text>"
        "<rect x='128' y='386' width='184' height='18' rx='9' fill='url(#bar)' opacity='0.88'/>"
        "<text x='606' y='260' font-family='Arial, sans-serif' font-size='24' font-weight='700' fill='#0f172a'>"
        "Snapshot summary"
        "</text>"
        "<text x='606' y='305' font-family='Arial, sans-serif' font-size='20' fill='#334155'>"
        "Auto-generated preview from the analyzed page."
        "</text>"
        "<text x='606' y='346' font-family='Arial, sans-serif' font-size='20' fill='#334155'>"
        "Use it as a representative visual when screenshots are unavailable."
        "</text>"
        "<rect x='606' y='386' width='220' height='18' rx='9' fill='#cbd5e1'/>"
        "<rect x='606' y='518' width='920' height='18' rx='9' fill='#cbd5e1' opacity='0.8'/>"
        "<rect x='606' y='556' width='860' height='18' rx='9' fill='#cbd5e1' opacity='0.8'/>"
        "<rect x='606' y='594' width='760' height='18' rx='9' fill='#cbd5e1' opacity='0.8'/>"
        "<rect x='606' y='632' width='680' height='18' rx='9' fill='#cbd5e1' opacity='0.8'/>"
        "</svg>"
    )
    encoded_svg = quote(svg)
    return f"data:image/svg+xml;charset=utf-8,{encoded_svg}"


def _normalize_analysis_mode(mode: str | None) -> str:
    value = (mode or "").strip().lower()
    if value in {"academic", "study", "academic_report"}:
        return "academic"
    if value in {"marketing_seo", "marketing", "seo", "marketing-seo"}:
        return "marketing_seo"
    return "business"


def _build_web_llm_prompt(
    *,
    source_type: str,
    source_label: str,
    text: str,
    metrics: list[dict[str, str | int]],
    labels: list[str],
    values: list[int],
    cta: CTAInfo | None,
    data_facts: list[DataFact],
    analysis_mode: str,
) -> str:
    style = MODE_LABELS.get(analysis_mode, MODE_LABELS["business"])
    payload = {
        "source_type": source_type,
        "source_label": source_label,
        "analysis_style": analysis_mode,
        "analysis_style_label": style,
        "metrics": metrics,
        "top_keywords": [{"label": l, "count": v} for l, v in zip(labels[:8], values[:8])],
        "cta_detected": cta.model_dump() if cta else None,
        "data_facts": [fact.model_dump() for fact in data_facts[:8]],
        "text_excerpt": text[:7000],
    }
    return (
        f"Bạn là chuyên gia phân tích nội dung web theo phong cách {style}. "
        "Trả về JSON hợp lệ, không markdown, không giải thích ngoài JSON. "
        "Tập trung vào kết luận có giá trị, viết theo văn phong học thuật, có luận điểm và lập luận.\n"
        "Schema bắt buộc:\n"
        "{\n"
        "  \"summary\": \"Đoạn văn 3-5 câu tóm tắt nội dung chính, luận điểm trung tâm và thông điệp học thuật\",\n"
        "  \"findings\": [\"3-5 luận điểm phân tích đầy đủ chuỗi nguyên nhân-hệ quả\"],\n"
        "  \"highlights\": [\"3-5 câu nhấn mạnh điểm trọng yếu theo văn xuôi\"],\n"
        "  \"recommendations\": [\"3-5 đề xuất hành động có cơ sở lập luận\"],\n"
        "  \"evidence\": [{\"label\": \"bằng chứng\", \"detail\": \"mô tả ngắn gọn\"}],\n"
        "  \"sections\": [\n"
        "    {\"heading\": \"...\", \"snippet\": \"...\"}\n"
        "  ]\n"
        "}\n"
        "Nguyên tắc:\n"
        "- Bắt buộc viết tiếng Việt có dấu, rõ ràng, không chung chung, ưu tiên câu văn học thuật.\n"
        "- Summary chỉ tóm tắt nội dung/chủ đề/luận điểm; không nêu số từ, số câu, số đoạn hoặc thống kê kỹ thuật.\n"
        "- Mỗi ý phát hiện cần có luận điểm và ý nghĩa phân tích, không viết dạng keyword rời rạc.\n"
        "- Nếu có dấu hiệu rủi ro, phải nêu rõ mức độ tin cậy/không tin cậy và lý do chính.\n"
        "- Academic: nhấn mạnh cấu trúc, mục tiêu, bối cảnh, giá trị học thuật.\n"
        "- Marketing/SEO: nhấn mạnh intent người dùng, keyword, CTA, cơ hội chuyển đổi.\n"
        "- Business: nhấn mạnh insight, vấn đề, cơ hội, hành động và tác động.\n"
        "- Không tạo số liệu không có trong input, không lặp lại raw text.\n"
        "- sections tối đa 5, findings tối đa 5, highlights tối đa 5, recommendations tối đa 5, evidence tối đa 5.\n"
        "Dữ liệu đầu vào:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def _build_danger_score_prompt(
    *,
    text: str,
    source_label: str,
) -> str:
    """Prompt to ask LLM to analyze danger/risk level 0-100%."""
    return (
        "Ban la chuyen gia an ninh mang va phat hien gian lan. "
        "Phan tich noi dung website va danh gia muc do nguy hiểm tu 0-100%.\n"
        "0% = Hoang toan an toan, khong co dau hieu gian lan\n"
        "50% = Trung binh, co nhung dieu phai chu y\n"
        "100% = Cuc ky nguy hiêm, ro rang la lua dao hoac khiêu dam\n\n"
        "Tra ve DUNG CHI JSON nay, khong giai thich ngoai:\n"
        "{\n"
        "  \"danger_score\": <so tu 0-100>,\n"
        "  \"reasons\": [\"ly do 1\", \"ly do 2\", ...],\n"
        "  \"risk_level\": \"an toan\"|\"trung binh\"|\"cao\"|\"cuc cao\"\n"
        "}\n\n"
        "Dung ton tam danh gia:\n"
        "- Co tu khoa lien quan cua cua (casino, betting, porn, 18+ v.v) -> 70-100%\n"
        "- Co CTA minh hang (uy tin loi khong ro) -> tang 20-30%\n"
        "- Thieu du lieu/bang chung -> tang 15-20%\n"
        "- Noi dung chuan y, du bang chung -> giam xuong 20-40%\n"
        "- Co mo ta chi tiet, am chi hoc thuat -> 10-30%\n\n"
        f"Website: {source_label}\n"
        f"Noi dung:\n{text[:3000]}"
    )


def _call_openai_json(settings: Settings, prompt: str) -> dict[str, object] | None:
    if not settings.openai_api_key:
        return None

    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": "Tra ve dung JSON hop le theo schema duoc yeu cau."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=httpx.Timeout(settings.llm_timeout_seconds)) as client:
        res = client.post(url, headers=headers, json=body)
        res.raise_for_status()
        data = res.json()

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    content = choices[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        return None
    return json.loads(content)


def _call_openrouter_json(settings: Settings, prompt: str) -> dict[str, object] | None:
    if not settings.openrouter_api_key:
        return None

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_app_title:
        headers["X-Title"] = settings.openrouter_app_title

    body = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": "Tra ve dung JSON hop le theo schema duoc yeu cau."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=httpx.Timeout(settings.llm_timeout_seconds)) as client:
        res = client.post(url, headers=headers, json=body)
        res.raise_for_status()
        data = res.json()

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    content = choices[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        return None
    return json.loads(content)


def _call_openai_text(settings: Settings, messages: list[dict[str, str]]) -> str | None:
    if not settings.openai_api_key:
        return None

    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 700,
    }

    with httpx.Client(timeout=httpx.Timeout(settings.llm_timeout_seconds)) as client:
        res = client.post(url, headers=headers, json=body)
        res.raise_for_status()
        data = res.json()

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    content = choices[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        return None
    return _clean_text(content)


def _call_openrouter_text(settings: Settings, messages: list[dict[str, str]]) -> str | None:
    if not settings.openrouter_api_key:
        return None

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_app_title:
        headers["X-Title"] = settings.openrouter_app_title

    body = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 700,
    }

    with httpx.Client(timeout=httpx.Timeout(settings.llm_timeout_seconds)) as client:
        res = client.post(url, headers=headers, json=body)
        res.raise_for_status()
        data = res.json()

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    content = choices[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        return None
    return _clean_text(content)


def _enhance_with_llm(
    settings: Settings,
    *,
    source_type: str,
    source_label: str,
    text: str,
    metrics: list[dict[str, str | int]],
    labels: list[str],
    values: list[int],
    cta: CTAInfo | None,
    data_facts: list[DataFact],
    analysis_mode: str,
) -> tuple[
    str | None,
    list[str],
    list[dict[str, str]],
    list[str],
    list[str],
    list[dict[str, str]],
]:
    if not settings.llm_enabled:
        return None, [], [], [], [], []

    prompt = _build_web_llm_prompt(
        source_type=source_type,
        source_label=source_label,
        text=text,
        metrics=metrics,
        labels=labels,
        values=values,
        cta=cta,
        data_facts=data_facts,
        analysis_mode=analysis_mode,
    )

    result: dict[str, object] | None = None
    try:
        result = _call_openai_json(settings, prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("web_analysis_openai_fallback: %s", type(exc).__name__)

    if result is None:
        try:
            result = _call_openrouter_json(settings, prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("web_analysis_openrouter_fallback: %s", type(exc).__name__)

    if not isinstance(result, dict):
        return None, [], [], [], [], []

    summary = _clean_text(str(result.get("summary", ""))) or None
    findings = _safe_str_list(result.get("findings"), max_items=5)
    highlights = _safe_str_list(result.get("highlights"), max_items=5)
    recommendations = _safe_str_list(result.get("recommendations"), max_items=5)
    evidence = _safe_evidence(result.get("evidence"), max_items=5)
    findings = _ensure_findings_have_evidence(findings, evidence)
    sections = _safe_sections(result.get("sections"), max_items=5)
    return summary, findings, sections, highlights, recommendations, evidence


def _get_ai_danger_score(
    settings: Settings,
    *,
    text: str,
    source_label: str,
) -> float:
    """Get danger score from LLM AI analysis (0-100%)."""
    if not settings.llm_enabled:
        return 0.0

    prompt = _build_danger_score_prompt(text=text, source_label=source_label)
    
    result: dict[str, object] | None = None
    try:
        result = _call_openai_json(settings, prompt)
    except Exception as exc:
        logger.warning("danger_score_openai_fail: %s", type(exc).__name__)

    if result is None:
        try:
            result = _call_openrouter_json(settings, prompt)
        except Exception as exc:
            logger.warning("danger_score_openrouter_fail: %s", type(exc).__name__)

    if not isinstance(result, dict):
        return 0.0

    try:
        score = float(result.get("danger_score", 0))
        return min(max(score, 0.0), 100.0)
    except (ValueError, TypeError):
        return 0.0


def _calculate_fraud_score(
    text: str,
    cta: CTAInfo | None,
    data_facts: list[DataFact],
) -> float:
    """
    Tính độ nguy hiểm website (0-100%, 0=an toàn, 100=nguy hiểm/lừa đảo).
    """
    score = 0.0
    text_lower = text.lower()
    
    # === CẤP 1: Nội dung nhạy cảm HIGH RISK (cá độ, 18+) ===
    gambling_keywords = [
        "casino", "betting", "bet", "poker", "blackjack", "roulette", "slots",
        "cá cược", "cờ bạc", "nhà cái", "xổ số", "bingo", "trò chơi tiền tệ",
        "win88", "bet888", "m88", "fun88", "188bet",
    ]
    adult_keywords = [
        "18+", "adult", "sex", "porn", "xxx", "webcam", "cam girl",
        "khiêu dâm", "tình dục", "nội dung người lớn",
    ]
    
    gambling_count = sum(1 for kw in gambling_keywords if kw in text_lower)
    adult_count = sum(1 for kw in adult_keywords if kw in text_lower)
    
    # Nếu có từ khóa cá độ hoặc 18+, auto-flag 70%+
    if gambling_count > 0:
        score += min(50 + gambling_count * 5, 80)  # 50-80 điểm từ gambling
    elif adult_count > 0:
        score += min(50 + adult_count * 5, 80)  # 50-80 điểm từ adult content
    else:
        # === CẤP 2: Từ khóa nghi ngờ thông thường ===
        suspicious_keywords = [
            "urgent", "act now", "limited time", "exclusive offer", "click here",
            "claim your", "verify account", "confirm identity", "update payment",
            "congratulations", "you won", "free money", "guaranteed",
            "khẩn cấp", "đừng bỏ lỡ", "thời gian hạn chế", "chỉ hôm nay",
            "xác nhận", "cập nhật", "bạn đã thắng", "tiền miễn phí",
        ]
        suspicious_count = sum(1 for kw in suspicious_keywords if kw in text_lower)
        score += min(suspicious_count * 10, 30)  # Max 30 điểm từ từ khóa
        
        # Kiểm tra quá nhiều signs (!!! hoặc ???)
        exclamation_count = text.count("!") + text.count("?")
        if exclamation_count > 20:
            score += min((exclamation_count - 20) * 2, 15)
        
        # Kiểm tra CTA mạnh (aggressive CTA)
        if cta and cta.action_keyword in ["Buy", "Subscribe", "Order", "Sign Up", "Register"]:
            score += 10
        
        # Kiểm tra số lượng dữ liệu thực tế (thiếu dữ liệu = nghi ngờ hơn)
        if not data_facts or len(data_facts) < 2:
            score += 15
        
        # Kiểm tra độ dài nội dung (quá ngắn = nghi ngờ hơn, quá dài = có thể là spam)
        text_length = len(text.strip())
        if text_length < 200:
            score += 10
        elif text_length > 10000:
            score += 5
    
    # Bảo đảm score nằm trong khoảng 0-100
    return min(max(score, 0.0), 100.0)


def _analyze_text(
    text: str,
    source_type: str,
    source_label: str,
    soup: BeautifulSoup | None = None,
    *,
    analysis_mode: str = "business",
) -> WebAnalyzeResponse:
    cleaned = _clean_text(text)
    paragraphs = [seg.strip() for seg in re.split(r"\n+", text) if seg.strip()]
    sentences = [seg.strip() for seg in re.split(r"[.!?]+", cleaned) if seg.strip()]
    labels, values = _extract_keywords(cleaned)

    data_facts = _extract_data_facts(text)
    outline = _extract_outline_from_soup(soup) if soup else []
    cta = _detect_cta(soup) if soup else None

    findings = []
    if analysis_mode == "academic":
        findings.append("Mục tiêu học thuật: tập trung vào nguồn, cấu trúc, và luận điểm chính.")
    elif analysis_mode == "marketing_seo":
        findings.append("Mục tiêu marketing/SEO: đồng bộ thông điệp, keyword, và CTA để tăng chuyển đổi.")
    else:
        findings.append("Mục tiêu kinh doanh: tìm insight, cơ hội và hành động ưu tiên.")
    if labels:
        findings.append(f"Chủ đề chính: {', '.join(labels[:5])}.")
    findings.append(f"Độ dài nội dung: {len(sentences)} câu, {len(paragraphs)} đoạn.")
    if data_facts:
        findings.append(f"Bằng chứng định lượng: {len(data_facts)} mốc dữ liệu (số, ngày, %, tiền tệ).")
    if cta:
        findings.append(f"CTA phát hiện: '{cta.text}' ({cta.type}, từ khóa: {cta.action_keyword}).")
    findings.append("Gợi ý hành động: đưa một thông điệp chính lên đầu trang, giữ CTA ngắn gọn và cụ thể.")

    highlights: list[str] = []
    recommendations: list[str] = []
    evidence: list[dict[str, str]] = []

    if labels:
        highlights.append(f"Từ khóa nổi bật: {', '.join(labels[:4])}.")
    highlights.append(f"Có {len(sentences)} câu và {len(paragraphs)} đoạn nội dung để đọc nhanh.")
    if data_facts:
        highlights.append(f"Phát hiện {len(data_facts)} mốc dữ liệu/dấu hiệu định lượng trong nội dung.")
    if cta:
        highlights.append(f"CTA chính: {cta.text}.")

    if analysis_mode == "academic":
        recommendations.extend([
            "Làm rõ luận điểm chính ở đầu trang và tách rành mạch các phần nội dung.",
            "Ghép thêm nguồn trích dẫn, phương pháp hoặc dữ liệu tham chiếu nếu mục tiêu là học thuật.",
        ])
    elif analysis_mode == "marketing_seo":
        recommendations.extend([
            "Tách rõ intent người dùng, thêm heading dẫn đường và CTA cụ thể hơn.",
            "Tăng độ phủ keyword theo nhóm chủ đề và đưa thông điệp lợi ích lên trước.",
        ])
    else:
        recommendations.extend([
            "Rút ngắn thông điệp đầu trang và nhấn mạnh lợi ích chính trong một dòng đầu tiên.",
            "Chuyển các chi tiết hỗ trợ vào section riêng để dễ so sánh hành động.",
        ])

    if cta:
        recommendations.append("Nếu CTA là mục chuyển đổi chính, cần kiểm tra lại độ rõ ràng, độ tin cậy và độ nổi bật.")
    if not data_facts:
        recommendations.append("Bổ sung bằng chứng số, mốc thời gian, tỷ lệ hoặc thống kê để tăng độ tin cậy.")

    evidence.append({"label": "Độ dài nội dung", "detail": f"{len(sentences)} câu, {len(paragraphs)} đoạn được trích xuất."})
    if labels:
        evidence.append({"label": "Từ khóa chính", "detail": ", ".join(labels[:5])})
    if data_facts:
        evidence.append({"label": "Mốc dữ liệu", "detail": "; ".join(f"{fact.label}: {fact.value}" for fact in data_facts[:4])})
    if cta:
        evidence.append({"label": "CTA", "detail": f"{cta.text} ({cta.type}, {cta.action_keyword})"})

    sections: list[dict[str, str]] = []

    if outline:
        flat_headings: list[str] = []

        def _walk(nodes: list[HeadingNode]) -> None:
            for node in nodes:
                if node.text:
                    flat_headings.append(node.text)
                if node.children:
                    _walk(node.children)

        _walk(outline)
        for idx, heading in enumerate(flat_headings[:6], start=1):
            snippet = paragraphs[idx - 1] if idx - 1 < len(paragraphs) else ""
            if not snippet and sentences:
                snippet = sentences[idx - 1] if idx - 1 < len(sentences) else ""
            sections.append({"heading": heading[:120], "snippet": _clean_text(snippet)[:280]})

    if not sections:
        source_chunks = sentences[:6] if len(sentences) >= 3 else paragraphs[:6]
        for idx, chunk in enumerate(source_chunks, start=1):
            sections.append({"heading": f"Ý chính {idx}", "snippet": _clean_text(chunk)[:280]})

    if not sections and cleaned:
        words = cleaned.split()
        for idx in range(0, min(len(words), 180), 30):
            snippet = " ".join(words[idx:idx + 30]).strip()
            if snippet:
                sections.append({"heading": f"Ý chính {len(sections) + 1}", "snippet": snippet})
            if len(sections) >= 6:
                break

    metrics: list[dict[str, str | int]] = [
        {"metric": "characters", "value": len(cleaned)},
        {"metric": "words", "value": len(re.findall(r"[a-zA-ZA-Za-z0-9]+", cleaned))},
        {"metric": "sentences", "value": len(sentences)},
        {"metric": "paragraphs", "value": len(paragraphs)},
        {"metric": "analysis_mode", "value": analysis_mode},
    ]

    top_kw = ", ".join(labels[:4]) if labels else "chủ đề chính"
    main_claim = sentences[0][:220] if sentences else ""
    support_claim = sentences[1][:220] if len(sentences) > 1 else ""
    summary_fragments = [
        f"Nội dung tập trung vào {top_kw}.",
        main_claim,
        support_claim,
    ]
    summary = " ".join([_clean_text(item) for item in summary_fragments if _clean_text(item)])
    if not summary:
        summary = f"Nội dung từ nguồn {source_type} '{source_label}' đã được trích xuất và đủ căn cứ để phân tích luận điểm trọng tâm."

    cfg = get_settings()
    llm_summary, llm_findings, llm_sections, llm_highlights, llm_recommendations, llm_evidence = _enhance_with_llm(
        cfg,
        source_type=source_type,
        source_label=source_label,
        text=text,
        metrics=metrics,
        labels=labels,
        values=values,
        cta=cta,
        data_facts=data_facts,
        analysis_mode=analysis_mode,
    )
    if llm_summary:
        summary = llm_summary
    if llm_findings:
        findings = llm_findings
    if llm_sections:
        sections = llm_sections
    if llm_highlights:
        highlights = llm_highlights
    if llm_recommendations:
        recommendations = llm_recommendations
    if llm_evidence:
        evidence = llm_evidence

    summary, findings, highlights, recommendations, sections, evidence = _apply_mode_lens(
        analysis_mode=analysis_mode,
        summary=summary,
        findings=findings,
        highlights=highlights,
        recommendations=recommendations,
        sections=sections,
        evidence=evidence,
    )
    # Tính danger score: kết hợp heuristic + AI
    heuristic_score = _calculate_fraud_score(text, cta, data_facts)
    ai_score = _get_ai_danger_score(cfg, text=text, source_label=source_label) if cfg.llm_enabled else 0.0
    
    # Dùng điểm cao hơn giữa 2 phương pháp (trust both AI và heuristic)
    fraud_score = max(heuristic_score, ai_score) if ai_score > 0 else heuristic_score

    # Only include chart if there's valid data
    chart_obj = None
    if labels and values and len(labels) >= 2 and len(values) >= 2 and any(v > 0 for v in values):
        chart_obj = WebChart(
            kind="bar",
            title="Top tu khoa",
            labels=labels,
            values=values,
            total=sum(values),
        )

    return WebAnalyzeResponse(
        analysis_mode=analysis_mode,
        source_type=source_type,
        source_label=source_label,
        page_title=source_label,
        summary=summary,
        findings=findings,
        highlights=highlights,
        recommendations=recommendations,
        evidence=evidence,
        metrics=metrics,
        sections=sections,
        chart=chart_obj,
        outline=outline,
        cta_detected=cta,
        related_websites=[],
        data_facts=data_facts,
        raw_text_preview=cleaned[:1200],
        fraud_score=fraud_score,
        website_screenshot=None,
    )


def analyze_url_or_text(user_input: str, analysis_mode: str = "business") -> WebAnalyzeResponse:
    value = user_input.strip()
    normalized_mode = _normalize_analysis_mode(analysis_mode)
    if not value:
        raise ValueError("Input khong duoc rong")

    if _is_url(value):
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                response = client.get(value)
                response.raise_for_status()
        except httpx.ConnectError as exc:
            if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
                raise ValueError(f"Khong truy cap duoc URL: {exc}") from exc
            try:
                with httpx.Client(timeout=20.0, follow_redirects=True, verify=False) as insecure_client:
                    response = insecure_client.get(value)
                    response.raise_for_status()
            except Exception as retry_exc:  # noqa: BLE001
                raise ValueError(f"Khong truy cap duoc URL: {retry_exc}") from retry_exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Khong truy cap duoc URL: {exc}") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        page_title = _clean_text(soup.title.get_text(" ") if soup.title else "") or value
        paragraphs = [_sanitize_extracted_text(p.get_text(" ")) for p in soup.select("p")]
        paragraphs = [p for p in paragraphs if len(p) > 35][:40]

        article_text = _sanitize_extracted_text(soup.get_text(" ")) if not paragraphs else "\n".join(paragraphs)

        analysis = _analyze_text(article_text, "url", page_title, soup, analysis_mode=normalized_mode)
        analysis.metrics.append({"metric": "http_status", "value": int(response.status_code)})
        analysis.metrics.append({"metric": "links", "value": len(soup.select("a[href]"))})
        analysis.metrics.append({"metric": "headings", "value": len(soup.select("h1, h2, h3"))})
        analysis.website_screenshot = _build_website_screenshot_url(str(response.url))
        analysis.related_websites = _extract_related_websites(soup, str(response.url))
        return analysis

    analysis = _analyze_text(value, "text", "Noi dung nguoi dung", None, analysis_mode=normalized_mode)
    analysis.related_websites = _discover_related_websites_from_text(value)
    return analysis


def _build_web_chat_prompt(analysis: WebAnalyzeResponse, question: str) -> list[dict[str, str]]:
    focus = {
        "source_type": analysis.source_type,
        "source_label": analysis.source_label,
        "page_title": analysis.page_title,
        "analysis_mode": analysis.analysis_mode,
        "danger_score": analysis.fraud_score,
        "summary": analysis.summary,
        "findings": analysis.findings[:5],
        "cta_detected": analysis.cta_detected.model_dump() if analysis.cta_detected else None,
        "data_facts": [fact.model_dump() for fact in analysis.data_facts[:6]],
        "metrics": analysis.metrics[:6],
    }
    system_prompt = (
        "Ban la AI ho tro phan tich website. Chi tra loi dua tren website vua duoc phan tich ben duoi. "
        "Khong lan sang chu de khac, khong tu bau ra thong tin moi. "
        "Neu nguoi dung hoi ngoai pham vi website nay, hay keo lai pham vi vao chinh website dang phan tich. "
        "Tra loi bang tieng Viet, ro rang, ngan gon, tap trung vao rui ro, nguy co, CTA, noi dung nhay cam va hanh dong tiep theo. "
        "KHONG dung markdown table, KHONG dung code block, KHONG dung chuoi | **. Neu can liet ke, chi dung dau gach dau dong va cau ngan."
    )
    user_prompt = (
        "Du lieu website da phan tich (JSON):\n"
        f"{json.dumps(focus, ensure_ascii=False)}\n\n"
        "Cau hoi cua nguoi dung:\n"
        f"{question.strip()}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _strip_chat_markdown(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""

    cleaned = re.sub(r"```(?:json|text)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "")
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
    cleaned = re.sub(r"^\s*\|", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("|", " · ")
    cleaned = re.sub(r"\s+·\s+", " · ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _fallback_web_chat_answer(analysis: WebAnalyzeResponse, question: str) -> str:
    q = question.lower()
    danger = f"{analysis.fraud_score:.1f}%"
    if any(token in q for token in ["cá độ", "ca do", "casino", "bet", "nhà cái", "nha cai", "18+", "porn", "sex"]):
        return (
            f"Website này đang được đánh giá ở mức {danger} nguy hiểm. "
            f"Lý do chính là: {', '.join(analysis.findings[:3]) or analysis.summary}. "
            "Nếu mục tiêu là kiểm tra độ rủi ro, đây là một nguồn có dấu hiệu đáng chú ý và nên tránh tương tác nếu không có xác minh độc lập."
        )
    if any(token in q for token in ["cta", "kêu gọi", "hành động", "nút", "call to action"]):
        if analysis.cta_detected:
            return (
                f"Tôi phát hiện CTA là '{analysis.cta_detected.text}' ({analysis.cta_detected.type}). "
                "CTA này đang hướng người dùng đến hành động cụ thể, nên cần xem nó có rõ ràng và đáng tin không."
            )
        return "Không thấy CTA rõ ràng trong website này, nên phần dẫn dắt hành động hiện khá yếu hoặc chưa nổi bật."
    if any(token in q for token in ["tóm tắt", "tom tat", "summary", "ngắn gọn"]):
        return f"Tóm tắt nhanh: {analysis.summary} Mức độ nguy hiểm hiện tại là {danger}."
    return (
        f"Tôi đang bám theo website '{analysis.source_label}'. Mức độ nguy hiểm hiện tại là {danger}. "
        f"Các điểm chính: {', '.join(analysis.findings[:3]) or analysis.summary}. "
        "Bạn có thể hỏi tiếp về rủi ro, CTA, nội dung nhạy cảm hoặc cách giảm thiểu nguy cơ."
    )


def answer_web_analysis_question(
    settings: Settings,
    *,
    analysis: WebAnalyzeResponse,
    question: str,
) -> WebAnalysisChatResponse:
    cleaned_question = _clean_text(question)
    if not cleaned_question:
        raise ValueError("Cau hoi khong duoc rong")

    messages = _build_web_chat_prompt(analysis, cleaned_question)
    answer: str | None = None

    if settings.llm_enabled:
        try:
            answer = _call_openai_text(settings, messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("web_chat_openai_fallback: %s", type(exc).__name__)

        if answer is None:
            try:
                answer = _call_openrouter_text(settings, messages)
            except Exception as exc:  # noqa: BLE001
                logger.warning("web_chat_openrouter_fallback: %s", type(exc).__name__)

    if not answer:
        answer = _fallback_web_chat_answer(analysis, cleaned_question)
    else:
        answer = _strip_chat_markdown(answer)

    focus = analysis.source_label or analysis.page_title or analysis.source_type
    return WebAnalysisChatResponse(
        question=cleaned_question,
        answer=answer,
        source_label=focus,
        focus=focus,
    )
