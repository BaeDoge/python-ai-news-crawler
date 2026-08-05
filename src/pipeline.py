from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from .collector import collect_all
from .config import OUTPUT_DIR, load_sources
from .models import (
    CollectionLog,
    PipelineResult,
    ReportArtifacts,
)
from .openrouter_client import (
    analyze_with_openrouter,
    build_fallback_insights,
)
from .preprocess import preprocess_items
from .report_builder import build_report_files, save_run_json
from .sample_data import build_sample_items


ProgressCallback = Optional[Callable[[str, str, int], None]]


def run_pipeline(
    api_key: str,
    model: str = "openrouter/free",
    use_sample_data: bool = False,
    per_source_limit: int = 3,
    top_n: int = 5,
    max_analysis_items: int = 8,
    allow_ai_fallback: bool = True,
    output_dir: Path = OUTPUT_DIR,
    progress_callback: ProgressCallback = None,
) -> PipelineResult:
    warnings: List[str] = []
    _notify(progress_callback, "collector", "외부 소스에서 원천 데이터를 수집합니다.", 10)

    if use_sample_data:
        raw_items = build_sample_items()
        collection_logs = [
            CollectionLog(
                source_id="sample_bundle",
                source_name="TechLab Demo Sample",
                status="success",
                item_count=len(raw_items),
                elapsed_ms=0,
            )
        ]
    else:
        raw_items, collection_logs = collect_all(
            load_sources(),
            per_source_limit=per_source_limit,
        )
        if not raw_items:
            raw_items = build_sample_items()
            warnings.append(
                "실시간 수집 결과가 없어 샘플 원천 데이터로 전환했습니다."
            )
            collection_logs.append(
                CollectionLog(
                    source_id="sample_fallback",
                    source_name="TechLab Demo Sample",
                    status="fallback",
                    item_count=len(raw_items),
                    elapsed_ms=0,
                    error_message="실시간 수집 결과 없음",
                )
            )

    _notify(
        progress_callback,
        "preprocess",
        "URL 정규화, 필수 필드 확인, 중복 제거를 수행합니다.",
        32,
    )
    clean_items, duplicate_count, excluded_count = preprocess_items(raw_items)
    analysis_items = clean_items[:max_analysis_items]
    if not analysis_items:
        raise RuntimeError("정제 기준을 통과한 데이터가 없습니다.")

    _notify(
        progress_callback,
        "insight",
        f"{model} 모델로 {len(analysis_items)}건을 분석합니다.",
        52,
    )
    model_used = "backup-rule/no-llm"
    if api_key:
        try:
            insights, model_used, model_warnings = analyze_with_openrouter(
                analysis_items,
                api_key=api_key,
                model=model,
                status_callback=lambda message: _notify(
                    progress_callback,
                    "insight",
                    message,
                    60,
                ),
            )
            warnings.extend(model_warnings)
        except Exception as exc:
            if not allow_ai_fallback:
                raise
            _notify(
                progress_callback,
                "insight",
                "AI 응답을 받지 못해 백업 규칙으로 전환합니다.",
                68,
            )
            insights = build_fallback_insights(analysis_items)
            warnings.append(
                f"OpenRouter 호출 실패로 백업 규칙을 사용했습니다: {str(exc)[:400]}"
            )
    else:
        if not allow_ai_fallback:
            raise ValueError("OpenRouter API Key를 입력해 주세요.")
        insights = build_fallback_insights(analysis_items)
        warnings.append(
            "OpenRouter API Key가 없어 백업 규칙으로 Insight를 생성했습니다."
        )

    insights = sorted(
        insights,
        key=lambda insight: insight.importance_score,
        reverse=True,
    )
    _notify(
        progress_callback,
        "report",
        "Daily Insight PDF와 XLSX를 생성합니다.",
        75,
    )
    metrics = _metrics(
        raw_count=len(raw_items),
        clean_count=len(clean_items),
        insight_count=len(insights),
        duplicate_count=duplicate_count,
        excluded_count=excluded_count,
        collection_logs=collection_logs,
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / timestamp
    report = build_report_files(
        insights,
        run_dir,
        metrics=metrics,
        model_used=model_used,
        top_n=top_n,
    )
    json_path = run_dir / f"run_log_{timestamp}.json"
    save_run_json(
        json_path,
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "sample" if use_sample_data else "live",
            "model_requested": model,
            "model_used": model_used,
            "metrics": metrics,
            "warnings": warnings,
            "collection_logs": [log.to_dict() for log in collection_logs],
            "raw_items": [item.to_dict() for item in raw_items],
            "clean_items": [item.to_dict() for item in clean_items],
            "insights": [item.to_dict() for item in insights],
        },
    )
    _notify(
        progress_callback,
        "complete",
        "리포트 생성이 완료되었습니다.",
        100,
    )
    return PipelineResult(
        raw_items=raw_items,
        clean_items=clean_items,
        insights=insights,
        collection_logs=collection_logs,
        duplicate_count=duplicate_count,
        excluded_count=excluded_count,
        model_requested=model,
        model_used=model_used,
        warnings=warnings,
        artifacts=ReportArtifacts(
            pdf_path=report["pdf_path"],
            preview_path=report["preview_path"],
            xlsx_path=report["xlsx_path"],
            json_path=json_path,
            html_body=report["html_body"],
            email_subject=report["email_subject"],
        ),
    )


def _metrics(
    raw_count: int,
    clean_count: int,
    insight_count: int,
    duplicate_count: int,
    excluded_count: int,
    collection_logs: List[CollectionLog],
) -> dict:
    successes = sum(log.status == "success" for log in collection_logs)
    return {
        "raw_count": raw_count,
        "clean_count": clean_count,
        "insight_count": insight_count,
        "duplicate_count": duplicate_count,
        "excluded_count": excluded_count,
        "source_success_rate": round(
            successes / len(collection_logs) * 100 if collection_logs else 0,
            1,
        ),
    }


def _notify(
    callback: ProgressCallback,
    step: str,
    message: str,
    percent: int,
) -> None:
    if callback:
        callback(step, message, percent)
