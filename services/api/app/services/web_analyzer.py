from __future__ import annotations

import base64
import html
import json
import logging
import re
from collections import Counter
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import Settings, get_settings
from app.schemas.web_analysis import (
    CTAInfo,
    DataFact,
    DangerBreakdown,
    DangerBreakdownItem,
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

MODE_LENS_EN = {
    "academic": {
        "summary_lead": "Academic perspective",
        "findings": [
            "The central argument should be clearly presented in a problem–analysis–conclusion structure.",
            "Academic credibility depends on conceptual consistency and the quality of supporting evidence.",
        ],
        "highlights": [
            "Prioritize evaluation of research context, argumentative logic, and knowledge value.",
            "Focus on the relationship between claims, evidence, and academic implications.",
        ],
        "recommendations": [
            "Add citations, define scope, and describe methodology to strengthen conclusions.",
            "Standardize academic terminology and restructure paragraphs along a clear argument flow.",
        ],
        "sections": [
            {"heading": "Context & objectives", "snippet": "This section clarifies the context, audience, and knowledge goals that frame the research problem."},
            {"heading": "Evidence & reasoning", "snippet": "This section evaluates evidence quality and checks the coherence of the argument chain."},
        ],
    },
    "marketing_seo": {
        "summary_lead": "Marketing / SEO perspective",
        "findings": [
            "Marketing focus: messaging, search intent, keywords, and CTA flow.",
            "Conversion potential and clarity of value proposition need to be prioritised.",
        ],
        "highlights": [
            "Evaluate through the search-intent funnel and keyword coverage depth.",
            "Check alignment between headlines, body content, and the desired user action.",
        ],
        "recommendations": [
            "Optimise the value proposition above the fold and consolidate CTAs around a single goal.",
            "Cluster keywords by topic and map each cluster to a specific landing intent.",
        ],
        "sections": [
            {"heading": "Messaging & positioning", "snippet": "Assesses message clarity and differentiated value proposition."},
            {"heading": "Keywords, intent & CTA", "snippet": "Summarises keyword optimisation opportunities, search intent alignment, and conversion journey."},
        ],
    },
    "business": {
        "summary_lead": "Business perspective",
        "findings": [
            "Business focus: opportunities, risks, impact, and action priorities.",
            "Decisions should be prioritised by value created and opportunity cost.",
        ],
        "highlights": [
            "Evaluate by impact on business outcomes and operational efficiency.",
            "Quickly identify bottlenecks affecting execution effectiveness.",
        ],
        "recommendations": [
            "Prioritise 1–2 high-impact, low-effort actions.",
            "Set clear KPIs to measure progress for each improvement step.",
        ],
        "sections": [
            {"heading": "Opportunities & risks", "snippet": "Summarises opportunity and risk points, prioritised by impact level."},
            {"heading": "Action plan", "snippet": "Proposes short-term implementation steps and KPIs to track outcomes."},
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


def _augment_when_thin(primary: list[str], fallback: list[str], *, max_items: int = 6) -> list[str]:
    """Use the page-specific items first; only top up from the mode boilerplate
    if the LLM/heuristic output is too thin. This keeps the per-URL analysis
    front-and-center instead of being drowned by canned mode-lens text.
    """
    cleaned_primary = [item for item in (_clean_text(p) for p in primary) if item]
    if len(cleaned_primary) >= 2:
        return _dedupe_keep_order(cleaned_primary, max_items=max_items)
    return _dedupe_keep_order([*cleaned_primary, *fallback], max_items=max_items)


def _apply_mode_lens(
    *,
    analysis_mode: str,
    summary: str,
    findings: list[str],
    highlights: list[str],
    recommendations: list[str],
    sections: list[dict[str, str]],
    evidence: list[dict[str, str]],
    language: str = "vi",
) -> tuple[str, list[str], list[str], list[str], list[dict[str, str]], list[dict[str, str]]]:
    lens = MODE_LENS_EN if language == "en" else MODE_LENS
    profile = lens.get(analysis_mode, lens["business"])
    lead = str(profile["summary_lead"])
    base_summary = _strip_redundant_summary_prefix(summary)
    summary = f"{lead}: {base_summary}" if base_summary else lead

    findings_out = _augment_when_thin(findings, list(profile["findings"]), max_items=6)
    highlights_out = _augment_when_thin(highlights, list(profile["highlights"]), max_items=6)
    recommendations_out = _augment_when_thin(recommendations, list(profile["recommendations"]), max_items=6)
    sections_out = _merge_sections(sections, profile["sections"], max_items=6)

    evidence_out: list[dict[str, str]] = []
    seen_ev: set[str] = set()
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

    if not evidence_out:
        mode_evidence = {
            "label": "Mode lens",
            "detail": (
                f"Output adjusted for {analysis_mode} mode." if language == "en"
                else f"Đầu ra được điều chỉnh theo chế độ {analysis_mode}."
            ),
        }
        evidence_out.append(mode_evidence)

    return summary, findings_out, highlights_out, recommendations_out, sections_out, evidence_out


def _capture_real_website_screenshot(source_url: str) -> bytes | None:
    """Chụp ảnh trang web bằng Playwright Chromium (headless).

    Thứ tự thử:
    1. Playwright-managed Chromium headless shell (ưu tiên, dùng trong Docker/Render)
    2. Hệ thống Chrome đã cài sẵn qua channel="chrome" (fallback cho Windows local dev)
    3. Trả None → SVG placeholder nếu cả hai đều thất bại
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        logger.warning("playwright_not_installed: pip install playwright && playwright install chromium")
        return None

    args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-gpu-sandbox",
        "--disable-software-rasterizer",
        "--no-zygote",
        "--hide-scrollbars",
        "--disable-extensions",
        "--disable-popup-blocking",
        "--ignore-certificate-errors",
        "--lang=vi-VN",
        "--disable-features=VizDisplayCompositor",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-sync",
        "--disable-translate",
        "--metrics-recording-only",
        "--safebrowsing-disable-auto-update",
        "--disable-component-update",
    ]

    def _do_screenshot(p: object, **launch_kwargs: object) -> bytes | None:
        browser = p.chromium.launch(headless=True, args=args, **launch_kwargs)  # type: ignore[union-attr]
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.goto(source_url, wait_until="domcontentloaded", timeout=25_000)
            page.wait_for_timeout(1500)
            return page.screenshot(full_page=False, type="jpeg", quality=80)
        finally:
            browser.close()

    try:
        with sync_playwright() as p:
            raw: bytes | None = None

            # 1) Playwright-managed Chromium
            try:
                raw = _do_screenshot(p)
            except Exception as exc_pw:  # noqa: BLE001
                exc_msg = str(exc_pw)
                if "Executable doesn't exist" in exc_msg or "executable" in exc_msg.lower():
                    logger.warning(
                        "playwright_chromium_not_found, trying system chrome: %s",
                        exc_msg[:160],
                    )
                    # 2) Fallback: system Chrome / Edge installed on the machine
                    try:
                        raw = _do_screenshot(p, channel="chrome")
                    except Exception:  # noqa: BLE001
                        try:
                            raw = _do_screenshot(p, channel="msedge")
                        except Exception:  # noqa: BLE001
                            pass
                else:
                    raise

            if not raw or len(raw) < 512:
                logger.warning("playwright_screenshot_too_small: size=%d", len(raw or b""))
                return None
            return raw

    except Exception as exc:  # noqa: BLE001
        logger.warning("playwright_screenshot_failed: %s: %s", type(exc).__name__, str(exc)[:240])
        return None


def _build_website_screenshot_url(source_url: str) -> str | None:
    parsed = urlparse(source_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    screenshot_bytes = _capture_real_website_screenshot(source_url)
    if screenshot_bytes:
        return f"data:image/jpeg;base64,{base64.b64encode(screenshot_bytes).decode('ascii')}"

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
    language: str = "vi",
) -> str:
    style = MODE_LABELS.get(analysis_mode, MODE_LABELS["business"])
    payload = {
        "source_type": source_type,
        "source_label": source_label,
        "analysis_style": analysis_mode,
        "analysis_style_label": style,
        "metrics": metrics,
        "top_keywords": [{"label": lbl, "count": v} for lbl, v in zip(labels[:8], values[:8])],
        "cta_detected": cta.model_dump() if cta else None,
        "data_facts": [fact.model_dump() for fact in data_facts[:8]],
        "text_excerpt": text[:7000],
    }
    if language == "en":
        return (
            f"You are a web content analysis expert in {style} style. "
            "Return valid JSON only, no markdown, no explanations outside JSON. "
            "Focus on valuable conclusions with clear arguments and reasoning.\n"
            "Required schema:\n"
            "{\n"
            "  \"summary\": \"3-5 sentence paragraph summarizing the main content, central argument and key message\",\n"
            "  \"findings\": [\"3-5 analytical points with full cause-effect chains\"],\n"
            "  \"highlights\": [\"3-5 sentences emphasizing key points in prose\"],\n"
            "  \"recommendations\": [\"3-5 action recommendations with reasoned basis\"],\n"
            "  \"evidence\": [{\"label\": \"evidence\", \"detail\": \"brief description\"}],\n"
            "  \"sections\": [\n"
            "    {\"heading\": \"...\", \"snippet\": \"...\"}\n"
            "  ]\n"
            "}\n"
            "Rules:\n"
            "- MUST write in clear English, no vague generalities, prefer analytical prose.\n"
            "- Lock the analysis subject to source_label, URL/host and text_excerpt. Do not substitute with similarly named entities.\n"
            "- If no clear subject name is found in text_excerpt, say 'this website source' instead of guessing organization names.\n"
            "- Summary only summarizes content/topic/argument; do not mention word counts, sentence counts, paragraphs or technical statistics.\n"
            "- Each finding must have a clear argument and analytical significance, not isolated keywords.\n"
            "- If there are risk signals, clearly state the trust/distrust level and main reason.\n"
            "- Academic: emphasize structure, goals, context, academic value.\n"
            "- Marketing/SEO: emphasize user intent, keywords, CTAs, conversion opportunities.\n"
            "- Business: emphasize insights, problems, opportunities, actions and impact.\n"
            "- Do not fabricate data not present in input, do not repeat raw text.\n"
            "- Max 5 sections, 5 findings, 5 highlights, 5 recommendations, 5 evidence items.\n"
            "Input data:\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
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
        "- Khóa chủ thể phân tích theo source_label, URL/host và text_excerpt. Không thay thế bằng trường/đơn vị có tên gần giống.\n"
        "- Nếu không thấy tên chủ thể rõ ràng trong text_excerpt, hãy nói 'nguồn website này' thay vì suy đoán tên trường/tổ chức.\n"
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
    language: str = "vi",
) -> str:
    """Prompt to ask LLM to analyze danger/risk level 0-100%."""
    if language == "en":
        return (
            "You are a cybersecurity and fraud detection expert. "
            "Analyze the website content and assess the danger level from 0-100%.\n"
            "0% = Completely safe, no signs of fraud\n"
            "50% = Moderate, some things to watch\n"
            "100% = Extremely dangerous, clearly fraud or adult content\n\n"
            "Return ONLY this JSON, no explanations outside:\n"
            "{\n"
            "  \"danger_score\": <number 0-100>,\n"
            "  \"reasons\": [\"reason 1\", \"reason 2\", ...],\n"
            "  \"risk_level\": \"safe\"|\"medium\"|\"high\"|\"critical\"\n"
            "}\n\n"
            "Key assessment factors:\n"
            "- Keywords related to gambling (casino, betting, porn, 18+, etc.) -> 70-100%\n"
            "- Explicit CTAs (unclear credibility promises) -> add 20-30%\n"
            "- Missing data/evidence -> add 15-20%\n"
            "- Credible content with sufficient evidence -> reduce 20-40%\n"
            "- Detailed description, academic references -> 10-30%\n\n"
            f"Website: {source_label}\n"
            f"Content:\n{text[:3000]}"
        )
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
    language: str = "vi",
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
        language=language,
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
    language: str = "vi",
) -> float:
    """Get danger score from LLM AI analysis (0-100%)."""
    if not settings.llm_enabled:
        return 0.0

    prompt = _build_danger_score_prompt(text=text, source_label=source_label, language=language)
    
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


_GAMBLING_KEYWORDS = [
    "casino", "betting", "bet", "poker", "blackjack", "roulette", "slots",
    "cá cược", "cờ bạc", "nhà cái", "xổ số", "bingo", "trò chơi tiền tệ",
    "win88", "bet888", "m88", "fun88", "188bet",
]
_ADULT_KEYWORDS = [
    "18+", "adult", "sex", "porn", "xxx", "webcam", "cam girl",
    "khiêu dâm", "tình dục", "nội dung người lớn",
]
_SUSPICIOUS_KEYWORDS = [
    "urgent", "act now", "limited time", "exclusive offer", "click here",
    "claim your", "verify account", "confirm identity", "update payment",
    "congratulations", "you won", "free money", "guaranteed",
    "khẩn cấp", "đừng bỏ lỡ", "thời gian hạn chế", "chỉ hôm nay",
    "xác nhận", "cập nhật", "bạn đã thắng", "tiền miễn phí",
]


def _compute_danger_analysis(
    text: str,
    cta: CTAInfo | None,
    data_facts: list[DataFact],
    ai_score: float,
    language: str = "vi",
) -> tuple[float, DangerBreakdown]:
    """Compute danger score and return DangerBreakdown with 4 categories."""
    text_lower = text.lower()
    en = language == "en"

    # --- 1. Sensitive content ---
    gambling_count = sum(1 for kw in _GAMBLING_KEYWORDS if kw in text_lower)
    adult_count = sum(1 for kw in _ADULT_KEYWORDS if kw in text_lower)

    if gambling_count > 0:
        sensitive_score = min(50.0 + gambling_count * 5, 80.0)
        sensitive_note = (
            f"Detected {gambling_count} gambling/betting related keywords."
            if en else
            f"Phát hiện {gambling_count} từ liên quan đến cờ bạc/cá cược trong nội dung."
        )
    elif adult_count > 0:
        sensitive_score = min(50.0 + adult_count * 5, 80.0)
        sensitive_note = (
            f"Detected {adult_count} adult content (18+) related keywords."
            if en else
            f"Phát hiện {adult_count} từ liên quan đến nội dung 18+."
        )
    else:
        sensitive_score = 0.0
        sensitive_note = (
            "No sensitive keywords detected (gambling, betting, adult content)."
            if en else
            "Không phát hiện từ khóa nhạy cảm (cờ bạc, cá cược, nội dung 18+)."
        )

    sensitive_level = "high" if sensitive_score >= 50 else ("medium" if sensitive_score > 0 else "safe")

    # --- 2. CTA and manipulative behavior ---
    suspicious_count = sum(1 for kw in _SUSPICIOUS_KEYWORDS if kw in text_lower)
    exclamation_count = text.count("!") + text.count("?")
    aggressive_cta = bool(cta and cta.action_keyword in ["Buy", "Subscribe", "Order", "Sign Up", "Register"])

    if sensitive_score == 0:
        cta_score = min(suspicious_count * 10, 30)
        if exclamation_count > 20:
            cta_score += min((exclamation_count - 20) * 2, 15)
        if aggressive_cta:
            cta_score += 10
    else:
        cta_score = 10.0 if aggressive_cta else 0.0

    cta_score = min(cta_score, 40.0)

    if cta_score >= 20:
        cta_level = "high"
        cta_note = (
            f"Detected {suspicious_count} trigger words and strong manipulative CTAs."
            if en else
            f"Phát hiện {suspicious_count} từ kích động và CTA dẫn dụ mạnh."
        )
    elif cta_score > 0:
        cta_level = "medium"
        cta_note = (
            f"Signs of manipulative CTA ({suspicious_count} keywords"
            + (f", CTA: {cta.text[:40]}" if cta else "")
            + ")."
            if en else
            f"Có dấu hiệu CTA dẫn dụ ({suspicious_count} từ khóa"
            + (f", CTA: {cta.text[:40]}" if cta else "")
            + ")."
        )
    else:
        cta_level = "safe"
        cta_note = (
            "No manipulative CTA behavior or trigger keywords detected."
            if en else
            "Không phát hiện hành vi CTA dẫn dụ hoặc từ khóa kích động."
        )

    # --- 3. Lack of evidence ---
    evidence_score = 0.0
    if sensitive_score == 0:
        if not data_facts or len(data_facts) < 2:
            evidence_score += 15.0
        text_length = len(text.strip())
        if text_length < 200:
            evidence_score += 10.0
        elif text_length > 10000:
            evidence_score += 5.0
    evidence_score = min(evidence_score, 30.0)

    if evidence_score >= 20:
        ev_level = "high"
        ev_note = (
            f"Content severely lacks numerical evidence ({len(data_facts)} data points, short content)."
            if en else
            f"Nội dung rất thiếu bằng chứng số ({len(data_facts)} mốc dữ liệu, nội dung ngắn)."
        )
    elif evidence_score > 0:
        ev_level = "medium"
        ev_note = (
            f"Insufficient numerical evidence ({len(data_facts)} data points extracted)."
            if en else
            f"Thiếu bằng chứng số ({len(data_facts)} mốc dữ liệu được trích xuất)."
        )
    else:
        ev_level = "safe"
        ev_note = (
            f"Sufficient numerical evidence ({len(data_facts)} data points in content)."
            if en else
            f"Có đủ bằng chứng số ({len(data_facts)} mốc dữ liệu trong nội dung)."
        )

    # --- 4. AI composite assessment ---
    if ai_score >= 50:
        ai_level = "high"
        ai_note = (
            f"AI assessed high danger level ({ai_score:.1f}%). Review content carefully before trusting."
            if en else
            f"AI đánh giá mức nguy hiểm cao ({ai_score:.1f}%). Cần xem xét kỹ nội dung trước khi tin tưởng."
        )
    elif ai_score >= 20:
        ai_level = "medium"
        ai_note = (
            f"AI assessed medium danger level ({ai_score:.1f}%). Some points to note."
            if en else
            f"AI đánh giá mức nguy hiểm trung bình ({ai_score:.1f}%). Có một số điểm cần lưu ý."
        )
    else:
        ai_level = "safe"
        ai_note = (
            f"AI assessed content as relatively safe ({ai_score:.1f}%)."
            if en else
            f"AI đánh giá nội dung tương đối an toàn ({ai_score:.1f}%)."
        )

    # --- Total score ---
    heuristic = sensitive_score + (cta_score if sensitive_score == 0 else 0.0) + (evidence_score if sensitive_score == 0 else 0.0)
    total = min(max(heuristic, ai_score) if ai_score > 0 else heuristic, 100.0)

    breakdown = DangerBreakdown(
        sensitive_content=DangerBreakdownItem(
            label="Sensitive Content" if en else "Nội dung nhạy cảm",
            score=round(sensitive_score, 1),
            level=sensitive_level,
            note=sensitive_note,
        ),
        cta_manipulation=DangerBreakdownItem(
            label="CTA & Manipulation" if en else "CTA và hành vi dẫn dụ",
            score=round(cta_score, 1),
            level=cta_level,
            note=cta_note,
        ),
        evidence_lack=DangerBreakdownItem(
            label="Evidence Lack" if en else "Thiếu bằng chứng",
            score=round(evidence_score, 1),
            level=ev_level,
            note=ev_note,
        ),
        ai_assessment=DangerBreakdownItem(
            label="AI Assessment" if en else "Đánh giá tổng hợp AI",
            score=round(ai_score, 1),
            level=ai_level,
            note=ai_note,
        ),
    )
    return round(min(max(total, 0.0), 100.0), 1), breakdown


def _analyze_text(
    text: str,
    source_type: str,
    source_label: str,
    soup: BeautifulSoup | None = None,
    *,
    analysis_mode: str = "business",
    language: str = "vi",
) -> WebAnalyzeResponse:
    cleaned = _clean_text(text)
    paragraphs = [seg.strip() for seg in re.split(r"\n+", text) if seg.strip()]
    sentences = [seg.strip() for seg in re.split(r"[.!?]+", cleaned) if seg.strip()]
    labels, values = _extract_keywords(cleaned)

    data_facts = _extract_data_facts(text)
    outline = _extract_outline_from_soup(soup) if soup else []
    cta = _detect_cta(soup) if soup else None
    en = language == "en"

    findings = []
    if analysis_mode == "academic":
        findings.append(
            "Academic goal: focus on source, structure, and main claims."
            if en else
            "Mục tiêu học thuật: tập trung vào nguồn, cấu trúc, và luận điểm chính."
        )
    elif analysis_mode == "marketing_seo":
        findings.append(
            "Marketing/SEO goal: align messaging, keywords, and CTAs to increase conversions."
            if en else
            "Mục tiêu marketing/SEO: đồng bộ thông điệp, keyword, và CTA để tăng chuyển đổi."
        )
    else:
        findings.append(
            "Business goal: find insights, opportunities and priority actions."
            if en else
            "Mục tiêu kinh doanh: tìm insight, cơ hội và hành động ưu tiên."
        )
    if labels:
        findings.append(
            f"Main topics: {', '.join(labels[:5])}."
            if en else
            f"Chủ đề chính: {', '.join(labels[:5])}."
        )
    findings.append(
        f"Content length: {len(sentences)} sentences, {len(paragraphs)} paragraphs."
        if en else
        f"Độ dài nội dung: {len(sentences)} câu, {len(paragraphs)} đoạn."
    )
    if data_facts:
        findings.append(
            f"Quantitative evidence: {len(data_facts)} data points (numbers, dates, %, currency)."
            if en else
            f"Bằng chứng định lượng: {len(data_facts)} mốc dữ liệu (số, ngày, %, tiền tệ)."
        )
    if cta:
        findings.append(
            f"CTA detected: '{cta.text}' ({cta.type}, keyword: {cta.action_keyword})."
            if en else
            f"CTA phát hiện: '{cta.text}' ({cta.type}, từ khóa: {cta.action_keyword})."
        )
    findings.append(
        "Action suggestion: put one main message at the top of the page, keep CTA concise and specific."
        if en else
        "Gợi ý hành động: đưa một thông điệp chính lên đầu trang, giữ CTA ngắn gọn và cụ thể."
    )

    highlights: list[str] = []
    recommendations: list[str] = []
    evidence: list[dict[str, str]] = []

    if labels:
        highlights.append(
            f"Top keywords: {', '.join(labels[:4])}."
            if en else
            f"Từ khóa nổi bật: {', '.join(labels[:4])}."
        )
    highlights.append(
        f"Contains {len(sentences)} sentences and {len(paragraphs)} paragraphs for quick reading."
        if en else
        f"Có {len(sentences)} câu và {len(paragraphs)} đoạn nội dung để đọc nhanh."
    )
    if data_facts:
        highlights.append(
            f"Found {len(data_facts)} data points/quantitative indicators in content."
            if en else
            f"Phát hiện {len(data_facts)} mốc dữ liệu/dấu hiệu định lượng trong nội dung."
        )
    if cta:
        highlights.append(
            f"Primary CTA: {cta.text}."
            if en else
            f"CTA chính: {cta.text}."
        )

    if analysis_mode == "academic":
        if en:
            recommendations.extend([
                "Clarify the main argument at the top and clearly separate content sections.",
                "Add citations, methodology, or reference data if the goal is academic.",
            ])
        else:
            recommendations.extend([
                "Làm rõ luận điểm chính ở đầu trang và tách rành mạch các phần nội dung.",
                "Ghép thêm nguồn trích dẫn, phương pháp hoặc dữ liệu tham chiếu nếu mục tiêu là học thuật.",
            ])
    elif analysis_mode == "marketing_seo":
        if en:
            recommendations.extend([
                "Clarify user intent, add guiding headings and more specific CTAs.",
                "Expand keyword coverage by topic cluster and lead with benefit messaging.",
            ])
        else:
            recommendations.extend([
                "Tách rõ intent người dùng, thêm heading dẫn đường và CTA cụ thể hơn.",
                "Tăng độ phủ keyword theo nhóm chủ đề và đưa thông điệp lợi ích lên trước.",
            ])
    else:
        if en:
            recommendations.extend([
                "Shorten the above-the-fold message and emphasize the main benefit in the first line.",
                "Move supporting details into dedicated sections for easier action comparison.",
            ])
        else:
            recommendations.extend([
                "Rút ngắn thông điệp đầu trang và nhấn mạnh lợi ích chính trong một dòng đầu tiên.",
                "Chuyển các chi tiết hỗ trợ vào section riêng để dễ so sánh hành động.",
            ])

    if cta:
        recommendations.append(
            "If the CTA is the main conversion goal, check its clarity, credibility and visibility."
            if en else
            "Nếu CTA là mục chuyển đổi chính, cần kiểm tra lại độ rõ ràng, độ tin cậy và độ nổi bật."
        )
    if not data_facts:
        recommendations.append(
            "Add numerical evidence, dates, percentages or statistics to increase credibility."
            if en else
            "Bổ sung bằng chứng số, mốc thời gian, tỷ lệ hoặc thống kê để tăng độ tin cậy."
        )

    evidence.append({
        "label": "Content length" if en else "Độ dài nội dung",
        "detail": f"{len(sentences)} {'sentences' if en else 'câu'}, {len(paragraphs)} {'paragraphs' if en else 'đoạn'} {'extracted' if en else 'được trích xuất'}.",
    })
    if labels:
        evidence.append({
            "label": "Main keywords" if en else "Từ khóa chính",
            "detail": ", ".join(labels[:5]),
        })
    if data_facts:
        evidence.append({
            "label": "Data points" if en else "Mốc dữ liệu",
            "detail": "; ".join(f"{fact.label}: {fact.value}" for fact in data_facts[:4]),
        })
    if cta:
        evidence.append({
            "label": "CTA",
            "detail": f"{cta.text} ({cta.type}, {cta.action_keyword})",
        })

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

    heading_prefix = "Key point" if en else "Ý chính"
    if not sections:
        source_chunks = sentences[:6] if len(sentences) >= 3 else paragraphs[:6]
        for idx, chunk in enumerate(source_chunks, start=1):
            sections.append({"heading": f"{heading_prefix} {idx}", "snippet": _clean_text(chunk)[:280]})

    if not sections and cleaned:
        words = cleaned.split()
        for idx in range(0, min(len(words), 180), 30):
            snippet = " ".join(words[idx:idx + 30]).strip()
            if snippet:
                sections.append({"heading": f"{heading_prefix} {len(sections) + 1}", "snippet": snippet})
            if len(sections) >= 6:
                break

    metrics: list[dict[str, str | int]] = [
        {"metric": "characters", "value": len(cleaned)},
        {"metric": "words", "value": len(re.findall(r"[a-zA-ZA-Za-z0-9]+", cleaned))},
        {"metric": "sentences", "value": len(sentences)},
        {"metric": "paragraphs", "value": len(paragraphs)},
        {"metric": "analysis_mode", "value": analysis_mode},
    ]

    top_kw = ", ".join(labels[:4]) if labels else ("main topics" if en else "chủ đề chính")
    main_claim = sentences[0][:220] if sentences else ""
    support_claim = sentences[1][:220] if len(sentences) > 1 else ""
    summary_fragments = [
        f"Content focuses on {top_kw}." if en else f"Nội dung tập trung vào {top_kw}.",
        main_claim,
        support_claim,
    ]
    summary = " ".join([_clean_text(item) for item in summary_fragments if _clean_text(item)])
    if not summary:
        if en:
            summary = f"Content from {source_type} source '{source_label}' has been extracted and provides sufficient basis for analysis."
        else:
            summary = f"Nội dung từ nguồn {source_type} '{source_label}' đã được trích xuất và đủ căn cứ để phân tích luận điểm trọng tâm."

    cfg = get_settings()
    llm_summary, llm_findings, llm_sections, llm_highlights, llm_recommendations, llm_evidence = _enhance_with_llm(
        cfg,
        source_type=source_type,
        source_label=source_label,
        text=text,
        language=language,
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
        language=language,
    )
    ai_score = _get_ai_danger_score(cfg, text=text, source_label=source_label, language=language) if cfg.llm_enabled else 0.0
    fraud_score, danger_breakdown = _compute_danger_analysis(text, cta, data_facts, ai_score, language)

    # Only include chart if there's valid data
    chart_obj = None
    if labels and values and len(labels) >= 2 and len(values) >= 2 and any(v > 0 for v in values):
        chart_obj = WebChart(
            kind="bar",
            title="Top keywords" if en else "Top tu khoa",
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
        danger_breakdown=danger_breakdown,
    )


DEFAULT_FETCH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_FETCH_HEADERS = {
    "User-Agent": DEFAULT_FETCH_USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


def _fetch_url_html(url: str, *, timeout: float = 30.0) -> httpx.Response:
    """Fetch a page with browser-like headers, one retry, and TLS fallback.

    Many Vietnamese .edu.vn sites sit behind WAFs that reject clients without
    realistic User-Agent / Accept-Language headers, or briefly time out under
    load. We mimic a modern browser and retry once on transient failures.
    """
    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            with httpx.Client(
                timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
                follow_redirects=True,
                headers=DEFAULT_FETCH_HEADERS,
                http2=False,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                return response
        except httpx.ConnectError as exc:
            last_error = exc
            if "CERTIFICATE_VERIFY_FAILED" in str(exc):
                try:
                    with httpx.Client(
                        timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
                        follow_redirects=True,
                        headers=DEFAULT_FETCH_HEADERS,
                        verify=False,
                    ) as insecure_client:
                        response = insecure_client.get(url)
                        response.raise_for_status()
                        return response
                except Exception as retry_exc:  # noqa: BLE001
                    last_error = retry_exc
            if attempt == 1:
                continue
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            last_error = exc
            if attempt == 1:
                continue
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            break

    raise ValueError(f"Khong truy cap duoc URL: {last_error}") from last_error


_ARTICLE_ROOT_SELECTORS = (
    "main",
    "article",
    "[role='main']",
    ".content",
    ".main-content",
    ".post-content",
    ".entry-content",
    "#content",
    "#main",
    "#main-content",
)
_ARTICLE_BLOCK_SELECTOR = "p, h1, h2, h3, h4, li, blockquote, dd, td, figcaption"
_ARTICLE_BLOCKED_PARENTS = ("nav", "footer", "aside", "header", "form", "script", "style", "noscript")
_ARTICLE_MIN_LENGTHS = {
    "p": 25,
    "h1": 8,
    "h2": 8,
    "h3": 8,
    "h4": 8,
    "li": 20,
    "blockquote": 25,
    "dd": 20,
    "td": 20,
    "figcaption": 20,
}


def _extract_article_text(soup: BeautifulSoup, *, max_chunks: int = 80) -> str:
    """Collect meaningful text from the page across `<p>`, headings, `<li>`, etc.

    Earlier versions relied solely on `<p>` tags longer than 35 characters,
    which produced very little text on portal-style university homepages
    (e.g., utc.edu.vn) where the body is structured around heading + list
    blocks instead of long paragraphs. That starved downstream summarization
    and led to generic, site-agnostic answers.
    """
    roots = soup.select(", ".join(_ARTICLE_ROOT_SELECTORS))
    if not roots:
        roots = [soup.body or soup]

    chunks: list[str] = []
    seen: set[str] = set()
    for root in roots:
        for tag in root.select(_ARTICLE_BLOCK_SELECTOR):
            if tag.find_parent(_ARTICLE_BLOCKED_PARENTS):
                continue
            text = _sanitize_extracted_text(tag.get_text(" "))
            if not text:
                continue
            min_len = _ARTICLE_MIN_LENGTHS.get(tag.name, 25)
            if len(text) < min_len:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            chunks.append(text)
            if len(chunks) >= max_chunks:
                break
        if len(chunks) >= max_chunks:
            break

    if chunks:
        return "\n".join(chunks)

    # Last-resort: full body text minus noise containers so we never feed an
    # empty string to the analyzer.
    body = soup.body or soup
    return _sanitize_extracted_text(body.get_text(" "))


def analyze_url_or_text(user_input: str, analysis_mode: str = "business", language: str = "vi") -> WebAnalyzeResponse:
    value = user_input.strip()
    normalized_mode = _normalize_analysis_mode(analysis_mode)
    if not value:
        raise ValueError("Input khong duoc rong")

    if _is_url(value):
        response = _fetch_url_html(value)
        resolved_url = str(response.url)
        resolved_host = urlparse(resolved_url).netloc

        soup = BeautifulSoup(response.text, "html.parser")
        for noise in soup(["script", "style", "noscript", "template"]):
            noise.decompose()

        page_title = _clean_text(soup.title.get_text(" ") if soup.title else "") or value
        source_identity = f"{page_title} ({resolved_host})" if resolved_host else page_title
        article_text = _extract_article_text(soup)

        analysis = _analyze_text(article_text, "url", source_identity, soup, analysis_mode=normalized_mode, language=language)
        analysis.page_title = page_title
        analysis.metrics.append({"metric": "http_status", "value": int(response.status_code)})
        analysis.metrics.append({"metric": "source_host", "value": resolved_host})
        analysis.metrics.append({"metric": "links", "value": len(soup.select("a[href]"))})
        analysis.metrics.append({"metric": "headings", "value": len(soup.select("h1, h2, h3"))})
        analysis.metrics.append({"metric": "content_chars", "value": len(article_text)})
        analysis.website_screenshot = _build_website_screenshot_url(resolved_url)
        analysis.related_websites = _extract_related_websites(soup, resolved_url)
        return analysis

    source_label = "User content" if language == "en" else "Noi dung nguoi dung"
    analysis = _analyze_text(value, "text", source_label, None, analysis_mode=normalized_mode, language=language)
    analysis.related_websites = _discover_related_websites_from_text(value)
    return analysis


def _build_web_chat_prompt(analysis: WebAnalyzeResponse, question: str, language: str = "vi") -> list[dict[str, str]]:
    danger_bd = None
    if analysis.danger_breakdown:
        bd = analysis.danger_breakdown
        danger_bd = {
            bd.sensitive_content.label: {"score": bd.sensitive_content.score, "level": bd.sensitive_content.level, "note": bd.sensitive_content.note},
            bd.cta_manipulation.label: {"score": bd.cta_manipulation.score, "level": bd.cta_manipulation.level, "note": bd.cta_manipulation.note},
            bd.evidence_lack.label: {"score": bd.evidence_lack.score, "level": bd.evidence_lack.level, "note": bd.evidence_lack.note},
            bd.ai_assessment.label: {"score": bd.ai_assessment.score, "level": bd.ai_assessment.level, "note": bd.ai_assessment.note},
        }

    focus = {
        "source_type": analysis.source_type,
        "source_label": analysis.source_label,
        "page_title": analysis.page_title,
        "analysis_mode": analysis.analysis_mode,
        "danger_score": analysis.fraud_score,
        "danger_breakdown": danger_bd,
        "summary": analysis.summary,
        "findings": analysis.findings[:5],
        "highlights": analysis.highlights[:5],
        "recommendations": analysis.recommendations[:5],
        "evidence": analysis.evidence[:6],
        "sections": [
            {"heading": s.get("heading", ""), "snippet": s.get("snippet", "")[:150]}
            for s in analysis.sections[:5]
        ],
        "related_websites": [
            {
                "title": w.get("title", ""),
                "url": w.get("url", ""),
                "relation": w.get("relation", ""),
                "summary": w.get("summary", "")[:120],
            }
            for w in analysis.related_websites[:4]
        ],
        "cta_detected": analysis.cta_detected.model_dump() if analysis.cta_detected else None,
        "data_facts": [fact.model_dump() for fact in analysis.data_facts[:6]],
        "metrics": analysis.metrics[:8],
    }
    if language == "en":
        system_prompt = (
            "You are the Bitlysis website analysis AI chatbot. The grounding data is the full website "
            "analysis result provided below — including danger score, 4-category analysis, "
            "content structure, evidence, related websites, recommendations, and CTA. "
            "Only answer based on this grounding context; do NOT add numbers, warnings or conclusions outside context. "
            "If the user asks beyond the scope of the website being analyzed, redirect the conversation. "
            "Reply in English clearly and concisely. "
            "Do NOT use markdown tables, code blocks, or | ** strings. If listing items, use bullet dashes."
        )
        user_prompt = (
            "Website analysis data (JSON grounding context):\n"
            f"{json.dumps(focus, ensure_ascii=False)}\n\n"
            "Question:\n"
            f"{question.strip()}"
        )
    else:
        system_prompt = (
            "Ban la AI chatbot chuyen phan tich website Bitlysis. Du lieu nen tang (grounding) la ket qua phan tich website "
            "da thuc hien duoc cung cap day du ben duoi — bao gom diem nguy hiem, phan tich 4 hang muc, "
            "cau truc noi dung, bang chung, website lien quan, khuyen nghi va CTA. "
            "Chi tra loi dua tren grounding context nay; KHONG tu them so lieu, canh bao hoac ket luan ngoai context. "
            "Neu nguoi dung hoi ngoai pham vi website dang phan tich, keo lai chu de. "
            "Tra loi bang tieng Viet ro rang, ngan gon. "
            "KHONG dung markdown table, code block hoac chuoi | **. Neu can liet ke, dung dau gach dau dong."
        )
        user_prompt = (
            "Du lieu phan tich website (JSON grounding context):\n"
            f"{json.dumps(focus, ensure_ascii=False)}\n\n"
            "Cau hoi:\n"
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


def _fallback_web_chat_answer(analysis: WebAnalyzeResponse, question: str, language: str = "vi") -> str:
    q = question.lower()
    danger = f"{analysis.fraud_score:.1f}%"
    en = language == "en"
    if any(token in q for token in ["cá độ", "ca do", "casino", "bet", "nhà cái", "nha cai", "18+", "porn", "sex"]):
        if en:
            return (
                f"This website is assessed at a {danger} danger level. "
                f"Main reasons: {', '.join(analysis.findings[:3]) or analysis.summary}. "
                "If your goal is to check risk, this is a source with notable signals and should be avoided without independent verification."
            )
        return (
            f"Website này đang được đánh giá ở mức {danger} nguy hiểm. "
            f"Lý do chính là: {', '.join(analysis.findings[:3]) or analysis.summary}. "
            "Nếu mục tiêu là kiểm tra độ rủi ro, đây là một nguồn có dấu hiệu đáng chú ý và nên tránh tương tác nếu không có xác minh độc lập."
        )
    if any(token in q for token in ["cta", "kêu gọi", "hành động", "nút", "call to action"]):
        if analysis.cta_detected:
            if en:
                return (
                    f"I detected a CTA: '{analysis.cta_detected.text}' ({analysis.cta_detected.type}). "
                    "This CTA is directing users to a specific action — check if it's clear and trustworthy."
                )
            return (
                f"Tôi phát hiện CTA là '{analysis.cta_detected.text}' ({analysis.cta_detected.type}). "
                "CTA này đang hướng người dùng đến hành động cụ thể, nên cần xem nó có rõ ràng và đáng tin không."
            )
        if en:
            return "No clear CTA found on this website, so the action-guiding section is currently weak or not prominent."
        return "Không thấy CTA rõ ràng trong website này, nên phần dẫn dắt hành động hiện khá yếu hoặc chưa nổi bật."
    if any(token in q for token in ["tóm tắt", "tom tat", "summary", "ngắn gọn"]):
        if en:
            return f"Quick summary: {analysis.summary} Current danger level is {danger}."
        return f"Tóm tắt nhanh: {analysis.summary} Mức độ nguy hiểm hiện tại là {danger}."
    if en:
        return (
            f"I am analyzing website '{analysis.source_label}'. Current danger level is {danger}. "
            f"Key points: {', '.join(analysis.findings[:3]) or analysis.summary}. "
            "You can ask about risks, CTAs, sensitive content, or how to reduce risks."
        )
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
    language: str = "vi",
) -> WebAnalysisChatResponse:
    cleaned_question = _clean_text(question)
    if not cleaned_question:
        raise ValueError("Cau hoi khong duoc rong")

    messages = _build_web_chat_prompt(analysis, cleaned_question, language)
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
        answer = _fallback_web_chat_answer(analysis, cleaned_question, language)
    else:
        answer = _strip_chat_markdown(answer)

    focus = analysis.source_label or analysis.page_title or analysis.source_type
    return WebAnalysisChatResponse(
        question=cleaned_question,
        answer=answer,
        source_label=focus,
        focus=focus,
    )
