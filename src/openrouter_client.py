from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from .models import CleanItem, InsightItem


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
RETRYABLE_STATUS_CODES = {408, 429, 502, 503}
MAX_FREE_FALLBACK_MODELS = 3
DEFAULT_REQUEST_TIMEOUT_SECONDS = 45
DEFAULT_MAX_ATTEMPTS = 2
JSON_REPAIR_TIMEOUT_SECONDS = 30
DEFAULT_MAX_OUTPUT_TOKENS = 5000
StatusCallback = Optional[Callable[[str], None]]
CATEGORIES = [
    "AI Agent",
    "GitHub Trend",
    "금융 AI",
    "IT News",
    "Cloud",
    "보안",
    "데이터",
    "개발 생산성",
    "RPA",
    "LLMOps",
]
SCORE_KEYS = {
    "freshness": 25,
    "work_relevance": 30,
    "spread_potential": 20,
    "finance_relevance": 15,
    "source_trust": 10,
}


def analyze_with_openrouter(
    items: List[CleanItem],
    api_key: str,
    model: str = "openrouter/free",
    timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    status_callback: StatusCallback = None,
) -> Tuple[List[InsightItem], str, List[str]]:
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY가 비어 있습니다.")
    if not items:
        return [], model, []

    prompt_items = [
        {
            "id": item.id,
            "title": item.title,
            "source": item.source_name,
            "published_at": item.published_at,
            "category_hint": item.category_hint,
            "text": (item.raw_text or item.summary_seed)[:1600],
        }
        for item in items
    ]
    prompt = _build_prompt(prompt_items)
    base_payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "당신은 금융회사 IT 개발자를 위한 기술 동향 편집 Agent입니다. "
                    "제공된 공개 원문 범위 안에서만 판단하고 한국어로 작성합니다."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        **_structured_output_options(),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-OpenRouter-Title": "TechLab Daily Insight Demo",
    }

    free_fallback_models = _fetch_free_fallback_models(
        headers,
        requested_model=model,
        timeout_seconds=min(timeout_seconds, 15),
    )
    routed_payload = dict(base_payload)
    if free_fallback_models:
        routed_payload["models"] = free_fallback_models
        if status_callback:
            status_callback(
                f"무료 대체 모델 {len(free_fallback_models)}개를 준비했습니다."
            )

    response, request_warnings = _request_with_recovery(
        headers,
        routed_payload,
        timeout_seconds,
        fallback_models=free_fallback_models,
        status_callback=status_callback,
    )
    if response.status_code == 400 and "response_format" in routed_payload:
        retry_payload = dict(routed_payload)
        retry_payload.pop("response_format", None)
        retry_payload.pop("plugins", None)
        retry_payload.pop("provider", None)
        compatibility_warning = (
            "선택된 무료 모델이 JSON 강제 출력을 지원하지 않아 "
            "일반 출력 모드로 한 번 더 요청했습니다."
        )
        request_warnings.append(compatibility_warning)
        if status_callback:
            status_callback(compatibility_warning)
        response, retry_warnings = _request_with_recovery(
            headers,
            retry_payload,
            timeout_seconds,
            fallback_models=free_fallback_models,
            max_attempts=1,
            status_callback=status_callback,
        )
        request_warnings.extend(retry_warnings)
    if not response.ok:
        raise RuntimeError(_friendly_error_message(response))

    response_json = response.json()
    if response_json.get("error"):
        raise RuntimeError(_friendly_payload_error(response_json["error"]))
    model_used = response_json.get("model", model)
    content = response_json["choices"][0]["message"].get("content", "")
    parsed, parse_warnings = _parse_or_repair_content(
        content=content,
        headers=headers,
        model=model_used,
        original_prompt=prompt,
        timeout_seconds=min(timeout_seconds, JSON_REPAIR_TIMEOUT_SECONDS),
        repair_models=free_fallback_models,
        status_callback=status_callback,
    )
    if isinstance(parsed, dict):
        raw_insights = parsed.get("items", [])
    elif isinstance(parsed, list):
        raw_insights = parsed
    else:
        raw_insights = []
    if not isinstance(raw_insights, list):
        raise RuntimeError("OpenRouter 응답의 items가 배열이 아닙니다.")

    item_by_id = {item.id: item for item in items}
    warnings: List[str] = [*request_warnings, *parse_warnings]
    insights: List[InsightItem] = []
    returned_ids = set()
    for index, raw_insight in enumerate(raw_insights, start=1):
        if not isinstance(raw_insight, dict):
            warnings.append(
                f"모델 응답의 {index}번째 항목이 JSON 객체가 아니어서 제외했습니다."
            )
            continue
        item_id = str(raw_insight.get("id", ""))
        source_item = item_by_id.get(item_id)
        if not source_item:
            warnings.append(f"알 수 없는 id 응답 제외: {item_id or '(empty)'}")
            continue
        insights.append(_coerce_insight(raw_insight, source_item))
        returned_ids.add(item_id)

    missing_items = [item for item in items if item.id not in returned_ids]
    if missing_items:
        warnings.append(
            f"모델 응답에서 누락된 {len(missing_items)}건은 백업 규칙으로 보완했습니다."
        )
        insights.extend(build_fallback_insights(missing_items))
    return insights, model_used, warnings


def build_fallback_insights(items: List[CleanItem]) -> List[InsightItem]:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    insights: List[InsightItem] = []
    for index, item in enumerate(items):
        source_score = 9 if item.source_type in {"rss", "api"} else 7
        freshness = max(12, 22 - index)
        work_score = 23 if item.category_hint in {"AI Agent", "금융 AI", "보안"} else 19
        spread_score = 14
        finance_score = 12 if "금융" in item.category_hint else 7
        breakdown = {
            "freshness": freshness,
            "work_relevance": work_score,
            "spread_potential": spread_score,
            "finance_relevance": finance_score,
            "source_trust": source_score,
        }
        total = sum(breakdown.values())
        summary = item.summary_seed or item.raw_text
        insights.append(
            InsightItem(
                id=item.id.replace("raw_", "insight_", 1),
                title=item.title,
                source=item.source_name,
                url=item.url,
                published_at=item.published_at,
                category=item.category_hint or "IT News",
                keywords=_fallback_keywords(item.title),
                importance=_importance_label(total),
                importance_score=total,
                score_breakdown=breakdown,
                summary=summary[:500],
                work_relevance=(
                    "사내 적용 전 원문과 보안 정책을 확인하고, 작은 업무 단위의 "
                    "PoC와 운영 로그 기준을 함께 검토할 수 있습니다."
                ),
                risk_note=(
                    "백업 규칙으로 생성된 결과입니다. 외부 배포 전 원문 검수가 필요합니다."
                ),
                generated_at=generated_at,
            )
        )
    return insights


def _request_completion(
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: int,
) -> requests.Response:
    return requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=timeout_seconds,
    )


def _request_with_recovery(
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: int,
    fallback_models: Optional[List[str]] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    status_callback: StatusCallback = None,
) -> Tuple[requests.Response, List[str]]:
    current_payload = dict(payload)
    remaining_models = list(fallback_models or [])
    warnings: List[str] = []
    response: Optional[requests.Response] = None

    for attempt in range(max_attempts):
        current_model = str(current_payload.get("model", "openrouter/free"))
        if status_callback:
            status_callback(
                f"OpenRouter 응답 대기 중 ({attempt + 1}/{max_attempts}) · "
                f"{current_model} · 최대 {timeout_seconds}초"
            )
        try:
            response = _request_completion(
                headers,
                current_payload,
                timeout_seconds,
            )
        except requests.Timeout:
            if attempt >= max_attempts - 1:
                raise RuntimeError(
                    f"OpenRouter 응답이 {timeout_seconds}초 안에 도착하지 않았습니다."
                )
            warning = _switch_to_next_model(
                current_payload,
                remaining_models,
                reason="응답 시간이 초과되어",
            )
            warnings.append(warning)
            if status_callback:
                status_callback(warning)
            continue
        except requests.RequestException as exc:
            if attempt >= max_attempts - 1:
                raise RuntimeError(
                    f"OpenRouter 연결 오류가 발생했습니다: {str(exc)[:180]}"
                )
            warning = _switch_to_next_model(
                current_payload,
                remaining_models,
                reason="연결 오류가 발생해",
            )
            warnings.append(warning)
            if status_callback:
                status_callback(warning)
            continue

        if response.ok or response.status_code not in RETRYABLE_STATUS_CODES:
            return response, warnings
        if attempt >= max_attempts - 1:
            break

        warning = _switch_to_next_model(
            current_payload,
            remaining_models,
            reason=f"{response.status_code} 응답으로 제한되어",
        )
        warnings.append(warning)
        if status_callback:
            status_callback(warning)

        delay_seconds = _retry_delay_seconds(response, attempt)
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    if response is None:
        raise RuntimeError("OpenRouter 요청을 시작하지 못했습니다.")
    return response, warnings


def _switch_to_next_model(
    payload: Dict[str, Any],
    remaining_models: List[str],
    reason: str,
) -> str:
    previous_model = str(payload.get("model", "openrouter/free"))
    if remaining_models:
        next_model = remaining_models.pop(0)
        payload["model"] = next_model
        if remaining_models:
            payload["models"] = list(remaining_models)
        else:
            payload.pop("models", None)
        return (
            f"{previous_model} 모델에서 {reason} "
            f"{next_model} 모델로 자동 전환했습니다."
        )
    return f"{previous_model} 모델에서 {reason} 같은 모델로 다시 시도합니다."


def _fetch_free_fallback_models(
    headers: Dict[str, str],
    requested_model: str,
    timeout_seconds: int,
) -> List[str]:
    try:
        response = requests.get(
            OPENROUTER_MODELS_URL,
            headers=headers,
            params={"output_modalities": "text"},
            timeout=timeout_seconds,
        )
        if not response.ok:
            return []
        model_rows = response.json().get("data", [])
    except (requests.RequestException, ValueError, AttributeError):
        return []

    preferred: List[str] = []
    remaining: List[str] = []
    seen_authors = set()
    for row in model_rows:
        model_id = str(row.get("id", ""))
        if (
            not model_id
            or model_id == requested_model
            or model_id == "openrouter/free"
            or not _is_free_model(row)
        ):
            continue
        supported = set(row.get("supported_parameters") or [])
        target = (
            preferred
            if {"response_format", "structured_outputs"} & supported
            else remaining
        )
        author = model_id.split("/", 1)[0]
        if author in seen_authors:
            continue
        target.append(model_id)
        seen_authors.add(author)

    return (preferred + remaining)[:MAX_FREE_FALLBACK_MODELS]


def _is_free_model(model_row: Dict[str, Any]) -> bool:
    pricing = model_row.get("pricing") or {}
    try:
        prompt_price = float(pricing.get("prompt", "1"))
        completion_price = float(pricing.get("completion", "1"))
    except (TypeError, ValueError):
        return False
    return prompt_price == 0 and completion_price == 0


def _retry_delay_seconds(response: requests.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After", "")
    try:
        requested_delay = float(retry_after)
    except (TypeError, ValueError):
        requested_delay = 0
    if requested_delay > 0:
        return min(requested_delay, 5.0)
    return min(1.0 + attempt, 3.0)


def _friendly_error_message(response: requests.Response) -> str:
    status = response.status_code
    if status == 401:
        return "OpenRouter API Key가 유효하지 않습니다. Key 값을 다시 확인해 주세요."
    if status == 402:
        return "OpenRouter 계정의 사용 가능 크레딧 또는 무료 호출 권한을 확인해 주세요."
    if status == 429:
        return (
            "무료 모델 공급자의 공용 호출 한도가 일시적으로 소진되었습니다. "
            "잠시 후 다시 실행하거나 'AI 실패 시 백업 결과 사용'을 선택해 주세요."
        )
    if status in {502, 503}:
        return (
            "현재 사용 가능한 무료 모델 공급자가 없습니다. "
            "잠시 후 다시 실행하거나 백업 결과를 사용해 주세요."
        )
    detail = ""
    try:
        detail = str((response.json().get("error") or {}).get("message", ""))
    except (ValueError, AttributeError):
        detail = ""
    return f"OpenRouter 요청 실패 ({status}){f': {detail[:240]}' if detail else ''}"


def _friendly_payload_error(error: Dict[str, Any]) -> str:
    try:
        code = int(error.get("code", 500))
    except (TypeError, ValueError):
        code = 500
    if code == 429:
        return (
            "무료 모델 공급자의 공용 호출 한도가 일시적으로 소진되었습니다. "
            "잠시 후 다시 실행하거나 백업 결과를 사용해 주세요."
        )
    if code in {502, 503}:
        return (
            "선택된 무료 모델이 일시적으로 응답하지 않습니다. "
            "잠시 후 다시 실행하거나 백업 결과를 사용해 주세요."
        )
    message = str(error.get("message", "모델 응답 생성 중 오류가 발생했습니다."))
    return f"OpenRouter 모델 응답 오류 ({code}): {message[:240]}"


def _build_prompt(items: List[Dict[str, Any]]) -> str:
    return f"""
다음 기사 목록을 분석해 JSON 객체 하나만 반환하세요.

필수 규칙:
1. 입력의 id를 그대로 유지합니다.
2. 원문에 없는 사실, 수치, 기관 입장을 만들지 않습니다.
3. summary는 한국어 2~4문장으로 작성합니다.
4. category는 다음 중 하나입니다: {", ".join(CATEGORIES)}
5. keywords는 2~5개입니다.
6. work_relevance는 사내 IT 개발자가 참고할 구체적 적용 포인트 1~2문장입니다.
7. risk_note는 보안·개인정보·운영·출처 검증 주의점이며, 없으면 "특이사항 없음"입니다.
8. importance_score는 아래 5개 점수의 합계이며 0~100입니다.
   - freshness: 0~25
   - work_relevance: 0~30
   - spread_potential: 0~20
   - finance_relevance: 0~15
   - source_trust: 0~10
9. importance는 합계 80 이상 "높음", 60 이상 "중간", 그 외 "낮음"입니다.

반환 형식:
{{
  "items": [
    {{
      "id": "입력 id",
      "category": "분류",
      "keywords": ["키워드"],
      "importance": "높음|중간|낮음",
      "importance_score": 0,
      "score_breakdown": {{
        "freshness": 0,
        "work_relevance": 0,
        "spread_potential": 0,
        "finance_relevance": 0,
        "source_trust": 0
      }},
      "summary": "요약",
      "work_relevance": "실무 적용 포인트",
      "risk_note": "주의 사항"
    }}
  ]
}}

입력:
{json.dumps(items, ensure_ascii=False)}
""".strip()


def _structured_output_options() -> Dict[str, Any]:
    score_properties = {
        key: {
            "type": "integer",
            "minimum": 0,
            "maximum": maximum,
        }
        for key, maximum in SCORE_KEYS.items()
    }
    insight_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "category": {"type": "string", "enum": CATEGORIES},
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 5,
            },
            "importance": {
                "type": "string",
                "enum": ["높음", "중간", "낮음"],
            },
            "importance_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
            "score_breakdown": {
                "type": "object",
                "properties": score_properties,
                "required": list(SCORE_KEYS),
                "additionalProperties": False,
            },
            "summary": {"type": "string"},
            "work_relevance": {"type": "string"},
            "risk_note": {"type": "string"},
        },
        "required": [
            "id",
            "category",
            "keywords",
            "importance",
            "importance_score",
            "score_breakdown",
            "summary",
            "work_relevance",
            "risk_note",
        ],
        "additionalProperties": False,
    }
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "techlab_insights",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": insight_schema,
                        }
                    },
                    "required": ["items"],
                    "additionalProperties": False,
                },
            },
        },
        "plugins": [{"id": "response-healing"}],
        "provider": {"require_parameters": True},
    }


def _parse_or_repair_content(
    content: Any,
    headers: Dict[str, str],
    model: str,
    original_prompt: str,
    timeout_seconds: int,
    repair_models: Optional[List[str]] = None,
    status_callback: StatusCallback = None,
) -> Tuple[Any, List[str]]:
    try:
        return _parse_json_content(content), []
    except RuntimeError as exc:
        if "JSON" not in str(exc):
            raise

    if status_callback:
        status_callback(
            "모델이 설명문을 반환해 JSON 형식으로 자동 복구합니다 "
            f"(최대 {timeout_seconds}초)."
        )
    repair_candidates = [
        candidate
        for candidate in (repair_models or [])
        if candidate != model
    ]
    repair_model = repair_candidates.pop(0) if repair_candidates else model
    repair_payload = {
        "model": repair_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "당신은 JSON 형식 복구기입니다. Markdown과 설명을 쓰지 말고 "
                    '{"items": [...]} 형태의 유효한 JSON 객체 하나만 반환하세요.'
                ),
            },
            {
                "role": "user",
                "content": (
                    "아래 분석 지시를 다시 수행하되 JSON 객체 하나만 반환하세요.\n\n"
                    f"[분석 지시]\n{original_prompt}\n\n"
                    "[이전의 잘못된 응답]\n"
                    f"{_content_to_text(content)[:6000]}"
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        **_structured_output_options(),
    }
    try:
        response, _ = _request_with_recovery(
            headers,
            repair_payload,
            timeout_seconds,
            fallback_models=repair_candidates,
            max_attempts=min(2, 1 + len(repair_candidates)),
            status_callback=status_callback,
        )
        if not response.ok:
            raise RuntimeError(_friendly_error_message(response))
        response_json = response.json()
        if response_json.get("error"):
            raise RuntimeError(_friendly_payload_error(response_json["error"]))
        repaired_content = response_json["choices"][0]["message"].get("content", "")
        parsed = _parse_json_content(repaired_content)
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise RuntimeError(
            "OpenRouter 응답을 JSON 형식으로 자동 복구하지 못했습니다. "
            "'AI 실패 시 백업 결과 사용'을 선택하면 리포트 생성을 계속할 수 있습니다."
        ) from exc

    return parsed, ["모델의 비정형 응답을 JSON 형식으로 자동 복구했습니다."]


def _content_to_text(content: Any) -> str:
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _parse_json_content(content: Any) -> Any:
    text = _content_to_text(content).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoded_values = _decode_json_sequence(text)
        if not decoded_values:
            raise RuntimeError("OpenRouter 응답에서 JSON을 찾지 못했습니다.")
        if len(decoded_values) == 1:
            return decoded_values[0]

        merged_items: List[Any] = []
        for value in decoded_values:
            if isinstance(value, dict) and isinstance(value.get("items"), list):
                merged_items.extend(value["items"])
            elif isinstance(value, list):
                merged_items.extend(value)
            elif isinstance(value, dict):
                merged_items.append(value)
        return merged_items


def _decode_json_sequence(text: str) -> List[Any]:
    decoder = json.JSONDecoder()
    start_candidates = [
        position
        for position in (text.find("{"), text.find("["))
        if position >= 0
    ]
    if not start_candidates:
        return []

    position = min(start_candidates)
    values: List[Any] = []
    while position < len(text):
        while position < len(text) and text[position] in " \r\n\t,;`":
            position += 1
        if position >= len(text):
            break
        try:
            value, end_position = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            next_object = text.find("{", position + 1)
            next_array = text.find("[", position + 1)
            next_candidates = [
                candidate
                for candidate in (next_object, next_array)
                if candidate >= 0
            ]
            if not next_candidates:
                break
            position = min(next_candidates)
            continue
        values.append(value)
        position = end_position
    return values


def _coerce_insight(raw: Dict[str, Any], item: CleanItem) -> InsightItem:
    breakdown: Dict[str, int] = {}
    raw_breakdown = raw.get("score_breakdown") or {}
    for key, maximum in SCORE_KEYS.items():
        breakdown[key] = _clamp_int(raw_breakdown.get(key, 0), 0, maximum)
    calculated_total = sum(breakdown.values())
    reported_total = _clamp_int(raw.get("importance_score", calculated_total), 0, 100)
    total = calculated_total if calculated_total else reported_total
    category = str(raw.get("category", item.category_hint or "IT News"))
    if category not in CATEGORIES:
        category = item.category_hint if item.category_hint in CATEGORIES else "IT News"
    keywords = raw.get("keywords") or _fallback_keywords(item.title)
    if not isinstance(keywords, list):
        keywords = [str(keywords)]
    return InsightItem(
        id=item.id.replace("raw_", "insight_", 1),
        title=item.title,
        source=item.source_name,
        url=item.url,
        published_at=item.published_at,
        category=category,
        keywords=[str(keyword)[:40] for keyword in keywords[:5]],
        importance=_importance_label(total),
        importance_score=total,
        score_breakdown=breakdown,
        summary=str(raw.get("summary") or item.summary_seed)[:1200],
        work_relevance=str(
            raw.get("work_relevance")
            or "원문을 검토한 뒤 관련 개발 업무에 적용 가능성을 확인합니다."
        )[:600],
        risk_note=str(raw.get("risk_note") or "특이사항 없음")[:400],
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def _importance_label(score: int) -> str:
    if score >= 80:
        return "높음"
    if score >= 60:
        return "중간"
    return "낮음"


def _fallback_keywords(title: str) -> List[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣]{2,}", title)
    return tokens[:4] or ["기술 동향"]
