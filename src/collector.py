from __future__ import annotations

import calendar
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import feedparser
import requests
from bs4 import BeautifulSoup

from .models import CollectionLog, RawItem


DEFAULT_HEADERS = {
    "User-Agent": "TechLab-Daily-Insight-Demo/1.0 (+local research demo)",
    "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*",
}


def collect_all(
    sources: List[Dict[str, Any]],
    per_source_limit: int = 3,
    timeout_seconds: int = 15,
) -> Tuple[List[RawItem], List[CollectionLog]]:
    if not sources:
        return [], []

    results: Dict[int, Tuple[List[RawItem], CollectionLog]] = {}
    max_workers = min(6, len(sources))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                _collect_source,
                source,
                per_source_limit,
                timeout_seconds,
            ): index
            for index, source in enumerate(sources)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            results[index] = future.result()

    items: List[RawItem] = []
    logs: List[CollectionLog] = []
    for index in range(len(sources)):
        source_items, log = results[index]
        items.extend(source_items)
        logs.append(log)
    return items, logs


def _collect_source(
    source: Dict[str, Any],
    per_source_limit: int,
    timeout_seconds: int,
) -> Tuple[List[RawItem], CollectionLog]:
    started = time.perf_counter()
    source_items: List[RawItem] = []
    error_message = ""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    try:
        if source["type"] == "rss":
            source_items = _collect_rss(
                session,
                source,
                per_source_limit,
                timeout_seconds,
            )
        elif source["type"] == "github_search":
            source_items = _collect_github(
                session,
                source,
                per_source_limit,
                timeout_seconds,
            )
        else:
            raise ValueError(f"지원하지 않는 수집 유형: {source['type']}")
        status = "success"
    except Exception as exc:
        status = "failed"
        error_message = str(exc)[:400]
    finally:
        session.close()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return source_items, CollectionLog(
        source_id=source["id"],
        source_name=source["name"],
        status=status,
        item_count=len(source_items),
        elapsed_ms=elapsed_ms,
        error_message=error_message,
    )


def _collect_rss(
    session: requests.Session,
    source: Dict[str, Any],
    limit: int,
    timeout_seconds: int,
) -> List[RawItem]:
    response = session.get(source["url"], timeout=timeout_seconds)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise RuntimeError(f"RSS 파싱 실패: {getattr(parsed, 'bozo_exception', '')}")

    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    items: List[RawItem] = []
    for entry in parsed.entries[:limit]:
        title = _clean_text(entry.get("title", ""))
        url = entry.get("link", "").strip()
        seed = _entry_text(entry)[:5000]
        if not title or not url:
            continue
        items.append(
            RawItem(
                id=_item_id(source["id"], url),
                source_id=source["id"],
                source_name=source["name"],
                source_type="rss",
                category_hint=source.get("category", "IT News"),
                collected_at=collected_at,
                published_at=_entry_date(entry),
                title=title,
                url=url,
                author=_clean_text(entry.get("author", source["name"])),
                raw_text=seed,
                summary_seed=seed,
                language="unknown",
            )
        )
    return items


def _collect_github(
    session: requests.Session,
    source: Dict[str, Any],
    limit: int,
    timeout_seconds: int,
) -> List[RawItem]:
    created_after = (
        datetime.now(timezone.utc) - timedelta(days=int(source.get("days", 14)))
    ).date()
    query = f"{source.get('query', 'AI agent')} created:>={created_after.isoformat()}"
    response = session.get(
        source["url"],
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": limit,
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    items: List[RawItem] = []
    for repository in payload.get("items", [])[:limit]:
        url = repository.get("html_url", "")
        title = repository.get("full_name", "")
        description = repository.get("description") or "설명이 제공되지 않은 저장소입니다."
        text = (
            f"{description} "
            f"주요 언어: {repository.get('language') or '미상'}. "
            f"스타 수: {repository.get('stargazers_count', 0)}. "
            f"최근 업데이트: {repository.get('updated_at', '')}."
        )
        if not title or not url:
            continue
        items.append(
            RawItem(
                id=_item_id(source["id"], url),
                source_id=source["id"],
                source_name=source["name"],
                source_type="api",
                category_hint=source.get("category", "GitHub Trend"),
                collected_at=collected_at,
                published_at=(repository.get("created_at") or "")[:10],
                title=title,
                url=url,
                author=(repository.get("owner") or {}).get("login", ""),
                raw_text=text,
                summary_seed=text,
                language="unknown",
            )
        )
    return items


def _entry_text(entry: Dict[str, Any]) -> str:
    candidates = [
        entry.get("summary", ""),
        entry.get("description", ""),
    ]
    if entry.get("content"):
        candidates.extend(content.get("value", "") for content in entry["content"])
    cleaned = [_clean_text(candidate) for candidate in candidates if candidate]
    return max(cleaned, key=len, default="")


def _entry_date(entry: Dict[str, Any]) -> str:
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_time:
        timestamp = calendar.timegm(parsed_time)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
    raw_date = entry.get("published") or entry.get("updated") or ""
    return str(raw_date)[:40]


def _clean_text(value: str) -> str:
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return " ".join(text.split())


def _item_id(source_id: str, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"raw_{source_id}_{digest}"
