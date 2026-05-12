"""Tìm kiếm bài báo khoa học từ OpenAlex và Semantic Scholar.

Không cần API key cho cả 2 nguồn.
Quartile được ước tính từ citation_percentile của OpenAlex:
    ≥75th → Q1 | ≥50th → Q2 | ≥25th → Q3 | <25th → Q4
"""
from __future__ import annotations

import hashlib
import logging
import time

import httpx

from app.config import Settings
from app.schemas.academic import AcademicPaper

logger = logging.getLogger(__name__)

# ── In-memory cache (key → (timestamp, result)) ─────────────────────────────
_CACHE: dict[str, tuple[float, list[AcademicPaper]]] = {}
_CACHE_TTL = 3600  # 1 giờ

_OPENALEX_URL = "https://api.openalex.org/works"
_S2_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _cache_key(*args: str) -> str:
    return hashlib.md5("|".join(args).encode()).hexdigest()


def _cache_get(key: str) -> list[AcademicPaper] | None:
    entry = _CACHE.get(key)
    if entry and time.monotonic() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, papers: list[AcademicPaper]) -> None:
    _CACHE[key] = (time.monotonic(), papers)


def _estimate_quartile(
    cited_by_count: int,
    citation_percentile: float | None,
) -> str:
    """Ước tính quartile từ citation_percentile của OpenAlex.

    Khi không có percentile, fall back sang cited_by_count heuristic.
    """
    if citation_percentile is not None:
        if citation_percentile >= 75:
            return "Q1"
        if citation_percentile >= 50:
            return "Q2"
        if citation_percentile >= 25:
            return "Q3"
        return "Q4"

    # Fallback heuristic dựa trên số trích dẫn tuyệt đối
    if cited_by_count >= 100:
        return "Q1"
    if cited_by_count >= 30:
        return "Q2"
    if cited_by_count >= 5:
        return "Q3"
    return "Q4"


def _extract_authors(authorships: list[dict]) -> list[str]:
    names: list[str] = []
    for a in authorships[:5]:  # tối đa 5 tác giả
        author = a.get("author", {})
        display = author.get("display_name", "")
        if display:
            names.append(display)
    return names


def _openalex_work_to_paper(work: dict) -> AcademicPaper | None:
    """Chuyển đổi OpenAlex work object → AcademicPaper."""
    title = work.get("title") or ""
    if not title:
        return None

    abstract_inverted = work.get("abstract_inverted_index") or {}
    abstract = _rebuild_abstract(abstract_inverted)

    cited_by_count = int(work.get("cited_by_count") or 0)
    percentile = None
    cite_score = work.get("citation_normalized_percentile") or {}
    if isinstance(cite_score, dict):
        percentile = cite_score.get("value")
        if percentile is not None:
            percentile = float(percentile) * 100  # OpenAlex trả 0-1, ta cần 0-100

    quartile = _estimate_quartile(cited_by_count, percentile)

    # Journal / venue
    primary_loc = work.get("primary_location") or {}
    source = primary_loc.get("source") or {}
    source_name = source.get("display_name") or ""

    # DOI
    doi = work.get("doi") or ""
    doi = doi.replace("https://doi.org/", "") if doi else None

    # URL
    url = work.get("doi") or work.get("id") or ""

    # Open access
    oa = work.get("open_access") or {}
    is_oa = bool(oa.get("is_oa"))

    pub_year = work.get("publication_year")

    return AcademicPaper(
        title=title[:300],
        authors=_extract_authors(work.get("authorships") or []),
        year=int(pub_year) if pub_year else None,
        doi=doi,
        abstract=abstract[:1200],
        cited_by_count=cited_by_count,
        quartile=quartile,
        source_name=source_name[:120],
        open_access=is_oa,
        url=url,
    )


def _rebuild_abstract(inverted: dict) -> str:
    """Khôi phục abstract từ inverted index của OpenAlex."""
    if not inverted:
        return ""
    max_pos = max((pos for positions in inverted.values() for pos in positions), default=0)
    words: list[str] = [""] * (max_pos + 1)
    for word, positions in inverted.items():
        for pos in positions:
            if 0 <= pos <= max_pos:
                words[pos] = word
    return " ".join(w for w in words if w)


# ── OpenAlex search ───────────────────────────────────────────────────────────

def search_openalex(query: str, max_results: int = 5) -> list[AcademicPaper]:
    """Tìm kiếm bài báo trên OpenAlex theo query string."""
    cache_key = _cache_key("openalex", query, str(max_results))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = {
        "search": query,
        "per_page": min(max_results, 25),
        "sort": "cited_by_count:desc",
        "select": (
            "id,title,doi,publication_year,cited_by_count,"
            "citation_normalized_percentile,abstract_inverted_index,"
            "authorships,primary_location,open_access"
        ),
        "mailto": "bitlysis@academic.search",  # Polite pool OpenAlex
    }

    papers: list[AcademicPaper] = []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(_OPENALEX_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        for work in data.get("results") or []:
            paper = _openalex_work_to_paper(work)
            if paper and paper.abstract:
                papers.append(paper)

        logger.info("openalex_search: query=%r found=%d", query, len(papers))
    except Exception as exc:  # noqa: BLE001
        logger.warning("openalex_search_failed: %s", exc)

    _cache_set(cache_key, papers)
    return papers


# ── Semantic Scholar fallback ─────────────────────────────────────────────────

def search_semantic_scholar(query: str, max_results: int = 5) -> list[AcademicPaper]:
    """Fallback: tìm kiếm qua Semantic Scholar Graph API."""
    cache_key = _cache_key("s2", query, str(max_results))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = {
        "query": query,
        "limit": min(max_results, 10),
        "fields": (
            "title,authors,year,externalIds,abstract,"
            "citationCount,isOpenAccess,venue"
        ),
    }

    papers: list[AcademicPaper] = []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(_S2_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        for item in (data.get("data") or []):
            title = item.get("title") or ""
            if not title:
                continue
            abstract = item.get("abstract") or ""
            if not abstract:
                continue

            cited = int(item.get("citationCount") or 0)
            doi = (item.get("externalIds") or {}).get("DOI")
            url = f"https://doi.org/{doi}" if doi else ""
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
        logger.warning("s2_search_failed: %s", exc)

    _cache_set(cache_key, papers)
    return papers


# ── Orchestrator ──────────────────────────────────────────────────────────────

def build_paper_list(
    keywords: list[str],
    max_papers: int = 15,
    settings: Settings | None = None,  # noqa: ARG001 — reserved for future API-key support
) -> tuple[list[AcademicPaper], str]:
    """Tìm kiếm bài báo từ nhiều keywords, dedup, sort by quartile.

    Returns:
        (papers, search_query_string)
    """
    search_query = " ".join(keywords)
    seen_titles: set[str] = set()
    papers: list[AcademicPaper] = []

    per_kw = max(3, max_papers // max(len(keywords), 1))

    for kw in keywords:
        batch = search_openalex(kw, max_results=per_kw)
        if len(batch) < 2:
            # Fallback sang Semantic Scholar nếu OpenAlex thiếu kết quả
            batch += search_semantic_scholar(kw, max_results=per_kw)

        for p in batch:
            key = p.title.lower().strip()
            if key not in seen_titles:
                seen_titles.add(key)
                papers.append(p)

    # Sắp xếp: Q1 trước, rồi Q2, Q3, Q4, Unknown; trong mỗi group sắp theo cited_by_count desc
    _quartile_order = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3, "Unknown": 4}
    papers.sort(key=lambda p: (_quartile_order.get(p.quartile, 4), -p.cited_by_count))

    return papers[:max_papers], search_query
