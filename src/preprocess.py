from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import CleanItem, RawItem


TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    filtered_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_QUERY_KEYS:
            continue
        filtered_query.append((key, value))
    path = re.sub(r"/+$", "", parts.path) or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            urlencode(filtered_query),
            "",
        )
    )


def preprocess_items(
    raw_items: List[RawItem],
    min_text_length: int = 40,
    title_similarity_threshold: float = 0.92,
) -> Tuple[List[CleanItem], int, int]:
    clean_items: List[CleanItem] = []
    normalized_urls = set()
    normalized_titles: List[str] = []
    duplicate_count = 0
    excluded_count = 0

    for raw in raw_items:
        title = " ".join(raw.title.split())
        text = " ".join((raw.raw_text or raw.summary_seed).split())
        if not title or not raw.url:
            excluded_count += 1
            continue
        if len(f"{title} {text}") < min_text_length:
            excluded_count += 1
            continue

        normalized_url = normalize_url(raw.url)
        normalized_title = _normalize_title(title)
        duplicate_by_url = normalized_url in normalized_urls
        duplicate_by_title = any(
            SequenceMatcher(None, normalized_title, seen_title).ratio()
            >= title_similarity_threshold
            for seen_title in normalized_titles
        )
        if duplicate_by_url or duplicate_by_title:
            duplicate_count += 1
            continue

        notes = ["URL 정규화", "필수 필드 확인"]
        if text:
            notes.append("본문 길이 통과")
        clean_payload = raw.to_dict()
        clean_payload.update(
            {
                "title": title,
                "raw_text": text,
                "summary_seed": " ".join(raw.summary_seed.split()),
                "normalized_url": normalized_url,
                "preprocess_notes": notes,
            }
        )
        clean_items.append(CleanItem(**clean_payload))
        normalized_urls.add(normalized_url)
        normalized_titles.append(normalized_title)

    return clean_items, duplicate_count, excluded_count


def _normalize_title(title: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", title).lower()
