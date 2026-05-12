"""Tìm kiếm bài báo khoa học từ 3 tier theo thứ tự ưu tiên.

Tier 1: arXiv       — preprint STEM hàng đầu, relevance sort
Tier 2: OpenAlex    — index toàn diện, citation_percentile → Q1-Q4
Tier 3: Semantic Scholar — fallback khi pool thiếu

Scoring formula (relevance:quality = 65:35):
    combined = 0.65 * relevance_score + 0.35 * quality_score

    relevance_score: vị trí trong search results (normalized linear decay)
    quality_score:   Q1=1.0 | Q2=0.75 | Q3=0.50 | Q4=0.25 | Unknown=0.40
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET

import httpx

from app.config import Settings
from app.schemas.academic import AcademicPaper

logger = logging.getLogger(__name__)

# ── Cache ─────────────────────────────────────────────────────────────────────
_CACHE: dict[str, tuple[float, list[AcademicPaper]]] = {}
_CACHE_TTL = 3600  # 1 giờ


def _cache_key(*args: str) -> str:
    return hashlib.md5("|".join(args).encode()).hexdigest()


def _cache_get(key: str) -> list[AcademicPaper] | None:
    entry = _CACHE.get(key)
    if entry and time.monotonic() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, papers: list[AcademicPaper]) -> None:
    _CACHE[key] = (time.monotonic(), papers)


# ── Scoring (65:35) ───────────────────────────────────────────────────────────

_QUARTILE_QUALITY: dict[str, float] = {
    "Q1": 1.00,
    "Q2": 0.75,
    "Q3": 0.50,
    "Q4": 0.25,
    "Unknown": 0.40,  # arXiv không có citation data nhưng chất lượng cao
}
_RELEVANCE_W = 0.65
_QUALITY_W = 0.35


def _relevance_score(pos: int, total: int) -> float:
    if total <= 1:
        return 1.0
    return max(0.0, 1.0 - pos / (total - 1))


def _combined_score(pos: int, total: int, quartile: str) -> float:
    return _RELEVANCE_W * _relevance_score(pos, total) + _QUALITY_W * _QUARTILE_QUALITY.get(quartile, 0.40)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _estimate_quartile(cited: int, percentile: float | None) -> str:
    if percentile is not None:
        if percentile >= 75:
            return "Q1"
        if percentile >= 50:
            return "Q2"
        if percentile >= 25:
            return "Q3"
        return "Q4"
    if cited >= 100:
        return "Q1"
    if cited >= 30:
        return "Q2"
    if cited >= 5:
        return "Q3"
    return "Q4"


def _normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower().strip())[:180]


# ── Tier 1: arXiv ─────────────────────────────────────────────────────────────

_ARXIV_URL = "https://export.arxiv.org/api/query"
_ATOM_NS = "http://www.w3.org/2005/Atom"


def search_arxiv(query: str, max_results: int = 8) -> list[AcademicPaper]:
    """arXiv search (tier 1) — sorted by relevance, open access, no API key."""
    ck = _cache_key("arxiv", query, str(max_results))
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    # Đặt quotes quanh multi-word query để tăng precision
    search_q = f'all:"{query}"' if " " in query else f"all:{query}"
    resp = None
    last_exc: Exception | None = None

    for attempt in range(2):
        try:
            with httpx.Client(timeout=25.0, follow_redirects=True) as c:
                resp = c.get(
                    _ARXIV_URL,
                    params={
                        "search_query": search_q,
                        "max_results": min(max_results, 20),
                        "sortBy": "relevance",
                        "sortOrder": "descending",
                    },
                )
            if resp.status_code == 429:
                wait = 4 * (attempt + 1)
                logger.warning("arxiv_rate_limited: waiting %ds", wait)
                time.sleep(wait)
                resp = None
                continue
            resp.raise_for_status()
            break
        except httpx.TimeoutException as exc:
            last_exc = exc
            logger.warning("arxiv_timeout: query=%r attempt=%d", query, attempt)
            time.sleep(2)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            break

    if resp is None:
        logger.warning("arxiv_search_failed: query=%r %s", query, last_exc)
        _cache_set(ck, [])
        return []

    papers: list[AcademicPaper] = []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        logger.warning("arxiv_parse_error: %s", exc)
        _cache_set(ck, [])
        return []

    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        title_el   = entry.find(f"{{{_ATOM_NS}}}title")
        summary_el = entry.find(f"{{{_ATOM_NS}}}summary")
        pub_el     = entry.find(f"{{{_ATOM_NS}}}published")
        id_el      = entry.find(f"{{{_ATOM_NS}}}id")

        title    = (title_el.text    or "").strip().replace("\n", " ") if title_el    else ""
        abstract = (summary_el.text  or "").strip().replace("\n", " ") if summary_el  else ""
        if not title or not abstract:
            continue

        arxiv_url = (id_el.text or "").strip() if id_el else ""
        arxiv_url = re.sub(r"v\d+$", "", arxiv_url).replace("http://", "https://")
        arxiv_id  = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else ""
        doi       = f"10.48550/arXiv.{arxiv_id}" if arxiv_id else None

        year: int | None = None
        if pub_el is not None and pub_el.text:
            try:
                year = int(pub_el.text[:4])
            except ValueError:
                pass

        authors: list[str] = []
        for ae in entry.findall(f"{{{_ATOM_NS}}}author")[:5]:
            ne = ae.find(f"{{{_ATOM_NS}}}name")
            if ne is not None and ne.text:
                authors.append(ne.text.strip())

        cats = [c.get("term", "") for c in entry.findall(f"{{{_ATOM_NS}}}category") if c.get("term")]
        source_name = "arXiv: " + ", ".join(cats[:3]) if cats else "arXiv"

        papers.append(AcademicPaper(
            title=title[:300],
            authors=authors,
            year=year,
            doi=doi,
            abstract=abstract[:1200],
            cited_by_count=0,
            quartile="Unknown",
            source_name=source_name[:120],
            open_access=True,
            url=arxiv_url,
        ))

    logger.info("arxiv_search: query=%r found=%d", query, len(papers))
    _cache_set(ck, papers)
    return papers


# ── Tier 2: OpenAlex ─────────────────────────────────────────────────────────

_OPENALEX_URL = "https://api.openalex.org/works"


def _rebuild_abstract(inverted: dict) -> str:
    if not inverted:
        return ""
    try:
        max_pos = max((p for positions in inverted.values() for p in positions), default=0)
        words = [""] * (max_pos + 1)
        for word, positions in inverted.items():
            for p in positions:
                if 0 <= p <= max_pos:
                    words[p] = word
        return " ".join(w for w in words if w)
    except Exception:  # noqa: BLE001
        return ""


def search_openalex(query: str, max_results: int = 8) -> list[AcademicPaper]:
    """OpenAlex search (tier 2) — sorted by relevance score (không phải citation count)."""
    ck = _cache_key("openalex", query, str(max_results))
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    papers: list[AcademicPaper] = []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as c:
            resp = c.get(
                _OPENALEX_URL,
                params={
                    "search": query,
                    "per_page": min(max_results, 25),
                    # Không set sort= → OpenAlex mặc định sort by relevance
                    "select": (
                        "id,title,doi,publication_year,cited_by_count,"
                        "citation_normalized_percentile,abstract_inverted_index,"
                        "authorships,primary_location,open_access"
                    ),
                    "mailto": "bitlysis@academic.search",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        for work in data.get("results") or []:
            title = (work.get("title") or "").strip()
            if not title:
                continue
            abstract = _rebuild_abstract(work.get("abstract_inverted_index") or {})
            if not abstract:
                continue

            cited = int(work.get("cited_by_count") or 0)
            percentile: float | None = None
            cs = work.get("citation_normalized_percentile") or {}
            if isinstance(cs, dict) and cs.get("value") is not None:
                percentile = float(cs["value"]) * 100

            quartile = _estimate_quartile(cited, percentile)
            primary_loc = work.get("primary_location") or {}
            source_name = (primary_loc.get("source") or {}).get("display_name") or ""
            doi_raw = work.get("doi") or ""
            doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None
            url = doi_raw or work.get("id") or ""
            oa = bool((work.get("open_access") or {}).get("is_oa"))
            pub_year = work.get("publication_year")
            authors = [
                (a.get("author") or {}).get("display_name", "")
                for a in (work.get("authorships") or [])[:5]
                if (a.get("author") or {}).get("display_name")
            ]

            papers.append(AcademicPaper(
                title=title[:300],
                authors=authors,
                year=int(pub_year) if pub_year else None,
                doi=doi,
                abstract=abstract[:1200],
                cited_by_count=cited,
                quartile=quartile,
                source_name=source_name[:120],
                open_access=oa,
                url=url,
            ))

        logger.info("openalex_search: query=%r found=%d", query, len(papers))
    except Exception as exc:  # noqa: BLE001
        logger.warning("openalex_search_failed: query=%r %s", query, exc)

    _cache_set(ck, papers)
    return papers


# ── Tier 3: Semantic Scholar ──────────────────────────────────────────────────

_S2_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def search_semantic_scholar(query: str, max_results: int = 5) -> list[AcademicPaper]:
    """Semantic Scholar (tier 3 — fallback)."""
    ck = _cache_key("s2", query, str(max_results))
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    papers: list[AcademicPaper] = []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as c:
            resp = c.get(
                _S2_URL,
                params={
                    "query": query,
                    "limit": min(max_results, 10),
                    "fields": "title,authors,year,externalIds,abstract,citationCount,isOpenAccess,venue",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        for item in data.get("data") or []:
            title    = (item.get("title")    or "").strip()
            abstract = (item.get("abstract") or "").strip()
            if not title or not abstract:
                continue
            cited = int(item.get("citationCount") or 0)
            doi   = (item.get("externalIds") or {}).get("DOI")
            url   = f"https://doi.org/{doi}" if doi else ""
            authors = [a.get("name", "") for a in (item.get("authors") or [])[:5]]
            papers.append(AcademicPaper(
                title=title[:300],
                authors=authors,
                year=item.get("year"),
                doi=doi,
                abstract=abstract[:1200],
                cited_by_count=cited,
                quartile=_estimate_quartile(cited, None),
                source_name=item.get("venue") or "",
                open_access=bool(item.get("isOpenAccess")),
                url=url,
            ))

        logger.info("s2_search: query=%r found=%d", query, len(papers))
    except Exception as exc:  # noqa: BLE001
        logger.warning("s2_search_failed: query=%r %s", query, exc)

    _cache_set(ck, papers)
    return papers


# ── Ranked pool ───────────────────────────────────────────────────────────────

def _add_to_pool(
    papers: list[AcademicPaper],
    seen: set[str],
    pool: list[tuple[float, AcademicPaper]],
) -> None:
    """Score papers bằng vị trí (relevance) + quartile (quality) rồi thêm vào pool."""
    total = len(papers)
    for pos, paper in enumerate(papers):
        key = _normalize_title(paper.title)
        if key in seen:
            continue
        seen.add(key)
        score = _combined_score(pos, total, paper.quartile)
        pool.append((score, paper))


def build_paper_list(
    keywords: list[str],
    max_papers: int = 15,
    settings: Settings | None = None,  # noqa: ARG001
) -> tuple[list[AcademicPaper], str]:
    """Tìm kiếm từ 3 tier, score 65:35, dedup, trả về top N.

    Tier 1 (arXiv) + Tier 2 (OpenAlex) được gọi cho mỗi keyword.
    Tier 3 (Semantic Scholar) chỉ kích hoạt khi pool quá ít.

    Returns:
        (papers_sorted_by_combined_score, search_query_string)
    """
    search_query = " | ".join(keywords[:6]) + (" ..." if len(keywords) > 6 else "")
    fetch_n = max(5, min(10, max_papers))

    seen: set[str] = set()
    pool: list[tuple[float, AcademicPaper]] = []

    for kw in keywords:
        _add_to_pool(search_arxiv(kw, max_results=fetch_n), seen, pool)
        _add_to_pool(search_openalex(kw, max_results=fetch_n), seen, pool)

    # Tier 3: chỉ dùng khi pool thiếu
    if len(pool) < max(5, max_papers // 2):
        logger.info("build_paper_list: pool=%d → triggering S2 fallback", len(pool))
        for kw in keywords[:3]:
            _add_to_pool(search_semantic_scholar(kw, max_results=fetch_n), seen, pool)

    pool.sort(key=lambda x: x[0], reverse=True)
    final = [p for _, p in pool[:max_papers]]

    logger.info("build_paper_list: kws=%d pool=%d returning=%d", len(keywords), len(pool), len(final))
    return final, search_query
