from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class RawItem:
    id: str
    source_id: str
    source_name: str
    source_type: str
    category_hint: str
    collected_at: str
    published_at: str
    title: str
    url: str
    author: str
    raw_text: str
    summary_seed: str
    language: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CleanItem(RawItem):
    normalized_url: str = ""
    preprocess_notes: List[str] = field(default_factory=list)


@dataclass
class InsightItem:
    id: str
    title: str
    source: str
    url: str
    published_at: str
    category: str
    keywords: List[str]
    importance: str
    importance_score: int
    score_breakdown: Dict[str, int]
    summary: str
    work_relevance: str
    risk_note: str
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CollectionLog:
    source_id: str
    source_name: str
    status: str
    item_count: int
    elapsed_ms: int
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReportArtifacts:
    pdf_path: Path
    preview_path: Path
    xlsx_path: Path
    json_path: Path
    html_body: str
    email_subject: str


@dataclass
class PipelineResult:
    raw_items: List[RawItem]
    clean_items: List[CleanItem]
    insights: List[InsightItem]
    collection_logs: List[CollectionLog]
    duplicate_count: int
    excluded_count: int
    model_requested: str
    model_used: str
    warnings: List[str]
    artifacts: ReportArtifacts

    def metrics(self) -> Dict[str, Any]:
        source_successes = sum(log.status == "success" for log in self.collection_logs)
        source_total = len(self.collection_logs)
        return {
            "raw_count": len(self.raw_items),
            "clean_count": len(self.clean_items),
            "insight_count": len(self.insights),
            "duplicate_count": self.duplicate_count,
            "excluded_count": self.excluded_count,
            "source_success_rate": round(
                (source_successes / source_total * 100) if source_total else 0,
                1,
            ),
        }
