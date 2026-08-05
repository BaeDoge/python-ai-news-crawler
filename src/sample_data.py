from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
from urllib.parse import urlparse

from .models import RawItem


def is_sample_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return hostname in {"example.com", "www.example.com"}


def build_sample_items() -> List[RawItem]:
    now = datetime.now()
    collected_at = now.isoformat(timespec="seconds")
    samples = [
        (
            "demo_ai_01",
            "Demo AI Official Blog",
            "AI Agent",
            "Agent 기반 개발 도구의 업무 흐름 자동화",
            "https://example.com/ai/agent-workflow",
            "개발 보조 도구가 단순 질의응답에서 계획 수립, 코드 작성, 테스트 실행을 연결하는 Agent 방식으로 확장되고 있다. 운영 단계에서는 실행 기록과 사용자 승인 지점을 함께 설계해야 한다.",
        ),
        (
            "demo_finance_01",
            "Demo Finance Policy",
            "금융 AI",
            "금융권 생성형 AI 활용을 위한 거버넌스 점검 항목",
            "https://example.com/finance/ai-governance",
            "금융권의 생성형 AI 활용에서는 개인정보, 설명 가능성, 책임 있는 사용, 결과 검증 절차가 중요하다. 입력 데이터와 응답, 사용자 확인 이력을 추적할 수 있는 구조가 필요하다.",
        ),
        (
            "demo_github_01",
            "Demo GitHub Trending",
            "GitHub Trend",
            "LLM 애플리케이션 평가 자동화 도구 관심 증가",
            "https://example.com/github/llm-evaluation",
            "LLM 응답을 데이터셋과 평가 기준으로 반복 검증하는 오픈소스 도구가 주목받고 있다. Prompt 변경 전후의 정확성과 비용, 지연 시간을 함께 비교하는 기능이 핵심이다.",
        ),
        (
            "demo_cloud_01",
            "Demo Cloud Engineering",
            "Cloud",
            "이벤트 기반 배치 파이프라인의 재처리 설계",
            "https://example.com/cloud/retryable-pipeline",
            "외부 데이터 수집 배치에서는 단계별 상태 저장, 지수 백오프 재시도, 실패 큐 분리가 운영 안정성을 높인다. 원천 데이터와 정제 데이터를 분리하면 장애 이후 재처리도 쉬워진다.",
        ),
        (
            "demo_security_01",
            "Demo Security News",
            "보안",
            "AI 서비스 공급망에서 모델과 데이터 출처 관리",
            "https://example.com/security/ai-supply-chain",
            "외부 모델과 데이터 소스를 사용하는 AI 서비스는 공급자 정책, 데이터 보관 여부, 모델 변경 이력을 점검해야 한다. 민감정보가 외부 추론 요청에 포함되지 않도록 입력 통제가 필요하다.",
        ),
        (
            "demo_dev_01",
            "Demo Engineering Blog",
            "개발 생산성",
            "코드 리뷰 요약 자동화의 효과와 한계",
            "https://example.com/engineering/code-review-summary",
            "변경 파일과 테스트 결과를 요약해 리뷰어의 탐색 시간을 줄이는 사례가 늘고 있다. 자동 요약은 검토 우선순위를 돕지만 승인 판단은 담당자가 수행해야 한다.",
        ),
        (
            "demo_data_01",
            "Demo Data Platform",
            "데이터",
            "뉴스 수집에서 URL 정규화와 중복 제거가 중요한 이유",
            "https://example.com/data/url-deduplication?utm_source=newsletter",
            "동일한 기사가 추적 파라미터나 재배포 경로 때문에 여러 건으로 수집될 수 있다. 정규 URL과 제목 유사도를 함께 사용하면 정보 과다와 반복 요약을 줄일 수 있다.",
        ),
        (
            "demo_data_02",
            "Demo Data Platform Mirror",
            "데이터",
            "뉴스 수집에서 URL 정규화와 중복 제거가 중요한 이유",
            "https://example.com/data/url-deduplication?utm_medium=email",
            "동일한 기사가 추적 파라미터나 재배포 경로 때문에 여러 건으로 수집될 수 있다. 정규 URL과 제목 유사도를 함께 사용하면 반복 결과를 줄일 수 있다.",
        ),
        (
            "demo_rpa_01",
            "Demo Automation Lab",
            "RPA",
            "망분리 환경에서 파일 기반 자동화 적용",
            "https://example.com/automation/file-transfer",
            "직접 API 연계가 어려운 환경에서는 검수된 PDF와 XLSX를 전달 단위로 사용할 수 있다. RPA 화면 변경에 대비해 수동 업로드와 재실행 절차를 함께 준비해야 한다.",
        ),
        (
            "demo_ops_01",
            "Demo LLMOps",
            "LLMOps",
            "LLM 응답 품질을 운영 지표로 관리하는 방법",
            "https://example.com/llmops/quality-metrics",
            "요약 품질은 정답률 하나로 설명하기 어렵기 때문에 왜곡 여부, 간결성, 업무 유용성을 나눠 평가하는 방식이 적합하다. 사용자 피드백을 Prompt 개선 이력과 연결하는 것이 중요하다.",
        ),
    ]

    items: List[RawItem] = []
    for index, sample in enumerate(samples):
        source_id, source_name, category, title, url, text = sample
        published = (now - timedelta(days=index % 5)).date().isoformat()
        items.append(
            RawItem(
                id=f"raw_sample_{index + 1:03d}",
                source_id=source_id,
                source_name=source_name,
                source_type="manual_seed",
                category_hint=category,
                collected_at=collected_at,
                published_at=published,
                title=title,
                url=url,
                author="TechLab Demo",
                raw_text=text,
                summary_seed=text,
                language="ko",
            )
        )
    return items
