from __future__ import annotations

from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from src.config import env_int, env_value, load_environment, load_sources
from src.email_delivery import (
    DEFAULT_EMAIL,
    SMTPSettings,
    email_as_bytes,
    send_email,
)
from src.pipeline import run_pipeline
from src.sample_data import is_sample_url


load_environment()

st.set_page_config(
    page_title="TechLab Daily Insight",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root {
        --kb-yellow: #ffcc00;
        --kb-dark: #242424;
        --kb-gray: #666660;
        --kb-line: #d8d8d2;
        --kb-surface: #f5f5f2;
      }
      .stApp { background: #ffffff; color: var(--kb-dark); }
      [data-testid="stSidebar"] {
        background: #f3f3ef;
        border-right: 1px solid var(--kb-line);
      }
      .block-container {
        max-width: 1440px;
        padding-top: 1.4rem;
        padding-bottom: 3rem;
      }
      .page-head {
        border-top: 8px solid var(--kb-yellow);
        border-bottom: 1px solid var(--kb-line);
        padding: 20px 4px 18px;
        margin-bottom: 18px;
      }
      .page-head .eyebrow {
        color: #705500;
        font-size: 12px;
        line-height: 1.2;
        margin-bottom: 7px;
      }
      .page-head h1 {
        color: var(--kb-dark);
        font-size: 32px;
        line-height: 1.2;
        margin: 0 0 6px;
        letter-spacing: 0;
      }
      .page-head p {
        color: var(--kb-gray);
        font-size: 14px;
        margin: 0;
      }
      .agent-strip {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        border: 1px solid var(--kb-line);
        background: #fff;
        margin: 6px 0 18px;
      }
      .agent-step {
        min-height: 70px;
        padding: 13px 14px;
        border-right: 1px solid var(--kb-line);
      }
      .agent-step:last-child { border-right: 0; }
      .agent-step .num {
        color: #705500;
        font-size: 10px;
        margin-bottom: 6px;
      }
      .agent-step .name {
        color: var(--kb-dark);
        font-size: 14px;
        margin-bottom: 3px;
      }
      .agent-step .desc {
        color: var(--kb-gray);
        font-size: 11px;
        line-height: 1.35;
      }
      .insight-meta {
        color: #705500;
        font-size: 12px;
        margin-bottom: 5px;
      }
      .insight-title {
        color: var(--kb-dark);
        font-size: 18px;
        line-height: 1.4;
        margin-bottom: 7px;
      }
      .insight-copy {
        color: #343434;
        font-size: 14px;
        line-height: 1.7;
      }
      .work-note {
        border-left: 4px solid var(--kb-yellow);
        background: var(--kb-surface);
        padding: 10px 12px;
        margin: 10px 0;
        color: #343434;
        font-size: 13px;
        line-height: 1.55;
      }
      div[data-testid="stMetric"] {
        border-top: 3px solid var(--kb-yellow);
        border-bottom: 1px solid var(--kb-line);
        padding: 11px 4px 9px;
      }
      .stButton > button[kind="primary"] {
        background: var(--kb-yellow);
        color: #1f1f1f;
        border: 1px solid #cda400;
        border-radius: 4px;
        font-weight: 700;
      }
      .stButton > button, .stDownloadButton > button {
        border-radius: 4px;
      }
      @media (max-width: 900px) {
        .agent-strip { grid-template-columns: 1fr; }
        .agent-step { border-right: 0; border-bottom: 1px solid var(--kb-line); }
        .agent-step:last-child { border-bottom: 0; }
        .page-head h1 { font-size: 26px; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="page-head">
      <div class="eyebrow">TECHLAB / RESEARCH DEMO</div>
      <h1>Daily Insight Agent Console</h1>
      <p>외부 기술 정보 수집부터 PDF 생성과 사내 전달까지 이어지는 End-to-End 데모</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="agent-strip">
      <div class="agent-step"><div class="num">01</div><div class="name">Collector</div><div class="desc">RSS·API 원천 데이터</div></div>
      <div class="agent-step"><div class="num">02</div><div class="name">Preprocess</div><div class="desc">URL 정규화·중복 제거</div></div>
      <div class="agent-step"><div class="num">03</div><div class="name">Insight</div><div class="desc">요약·분류·중요도</div></div>
      <div class="agent-step"><div class="num">04</div><div class="name">Report</div><div class="desc">Top-N·PDF·XLSX</div></div>
      <div class="agent-step"><div class="num">05</div><div class="name">Delivery</div><div class="desc">웹메일·첨부·로그</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.subheader("실행 설정")
    api_key = st.text_input(
        "OpenRouter API Key",
        value=env_value("OPENROUTER_API_KEY"),
        type="password",
        placeholder="sk-or-v1-...",
    )
    model = st.text_input(
        "Model",
        value=env_value("OPENROUTER_MODEL", "openrouter/free"),
    )
    source_mode = st.segmented_control(
        "데이터",
        options=["실시간 수집", "샘플 데이터"],
        default="실시간 수집",
    )
    top_n = st.slider("Top-N", min_value=3, max_value=8, value=5)
    per_source_limit = st.slider(
        "소스별 수집 건수",
        min_value=1,
        max_value=5,
        value=3,
    )
    allow_ai_fallback = st.checkbox(
        "AI 실패 시 백업 결과 사용",
        value=True,
    )
    run_clicked = st.button(
        "전체 파이프라인 실행",
        type="primary",
        use_container_width=True,
    )
    with st.expander("활성 데이터 소스"):
        for source in load_sources():
            st.caption(f"{source['name']} · {source['type']}")


if run_clicked:
    if not api_key and not allow_ai_fallback:
        st.error("OpenRouter API Key를 입력해 주세요.")
    else:
        status = st.status("Agent 파이프라인 실행 중", expanded=True)
        progress = st.progress(0)

        def update_progress(step: str, message: str, percent: int) -> None:
            status.write(f"{percent}% · {message}")
            progress.progress(percent)

        try:
            result = run_pipeline(
                api_key=api_key,
                model=model,
                use_sample_data=source_mode == "샘플 데이터",
                per_source_limit=per_source_limit,
                top_n=top_n,
                max_analysis_items=max(top_n, 8),
                allow_ai_fallback=allow_ai_fallback,
                progress_callback=update_progress,
            )
            st.session_state["pipeline_result"] = result
            status.update(
                label="Agent 파이프라인 완료",
                state="complete",
                expanded=False,
            )
        except Exception as exc:
            status.update(
                label="Agent 파이프라인 실패",
                state="error",
                expanded=True,
            )
            st.error(str(exc))


result = st.session_state.get("pipeline_result")
if not result:
    st.info("왼쪽에서 OpenRouter Key와 데이터 모드를 선택한 뒤 파이프라인을 실행하세요.")
    st.stop()


metrics = result.metrics()
uses_sample_data = any(
    log.source_id in {"sample_bundle", "sample_fallback"}
    for log in result.collection_logs
)
if uses_sample_data:
    st.info(
        "현재 결과에는 데모용 샘플 데이터가 사용되었습니다. "
        "샘플 항목은 실제 원문이 없으며 example.com 주소는 예시 식별자입니다."
    )

metric_columns = st.columns(5)
metric_columns[0].metric("원천 데이터", f"{metrics['raw_count']}건")
metric_columns[1].metric("정제 데이터", f"{metrics['clean_count']}건")
metric_columns[2].metric("중복 제거", f"{metrics['duplicate_count']}건")
metric_columns[3].metric("Insight", f"{metrics['insight_count']}건")
metric_columns[4].metric("수집 성공률", f"{metrics['source_success_rate']}%")

if result.warnings:
    with st.expander(f"실행 경고 {len(result.warnings)}건", expanded=False):
        for warning in result.warnings:
            st.warning(warning)

tabs = st.tabs(
    [
        "실행 결과",
        "Raw / Clean",
        "AI Insight",
        "PDF / XLSX",
        "메일 발송",
    ]
)

with tabs[0]:
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Agent 실행 로그")
        log_rows = [log.to_dict() for log in result.collection_logs]
        st.dataframe(
            log_rows,
            use_container_width=True,
            hide_index=True,
            column_order=[
                "source_name",
                "status",
                "item_count",
                "elapsed_ms",
                "error_message",
            ],
        )
    with right:
        st.subheader("중요도 분포")
        score_frame = pd.DataFrame(
            {
                "제목": [item.title for item in result.insights],
                "점수": [item.importance_score for item in result.insights],
            }
        )
        score_chart = (
            alt.Chart(score_frame)
            .mark_bar(color="#ffcc00", cornerRadiusEnd=2)
            .encode(
                x=alt.X("점수:Q", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("제목:N", sort="-x", axis=alt.Axis(labelLimit=190)),
                tooltip=["제목:N", "점수:Q"],
            )
            .properties(height=310)
        )
        st.altair_chart(score_chart, use_container_width=True)
    st.caption(
        f"요청 모델: {result.model_requested} · 실제 사용 모델: {result.model_used}"
    )

with tabs[1]:
    raw_tab, clean_tab = st.tabs(["Raw Items", "Clean Items"])
    with raw_tab:
        st.dataframe(
            [
                {
                    "source": item.source_name,
                    "title": item.title,
                    "published_at": item.published_at,
                    "url": item.url,
                    "source_type": item.source_type,
                }
                for item in result.raw_items
            ],
            use_container_width=True,
            hide_index=True,
        )
    with clean_tab:
        st.dataframe(
            [
                {
                    "source": item.source_name,
                    "title": item.title,
                    "category_hint": item.category_hint,
                    "normalized_url": item.normalized_url,
                    "notes": ", ".join(item.preprocess_notes),
                }
                for item in result.clean_items
            ],
            use_container_width=True,
            hide_index=True,
        )

with tabs[2]:
    ranked = sorted(
        result.insights,
        key=lambda item: item.importance_score,
        reverse=True,
    )[:top_n]
    for rank, item in enumerate(ranked, start=1):
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="insight-meta">TOP {rank} · {escape(item.category)} · {item.importance_score}점</div>
                <div class="insight-title">{escape(item.title)}</div>
                <div class="insight-copy">{escape(item.summary)}</div>
                <div class="work-note"><strong>실무 적용</strong><br>{escape(item.work_relevance)}</div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(
                f"{item.source} · {item.published_at} · {' / '.join(item.keywords)}"
            )
            if is_sample_url(item.url):
                st.caption("샘플 데이터 · 실제 원문 링크 없음")
            else:
                st.link_button("원문 열기", item.url)

with tabs[3]:
    pdf_bytes = result.artifacts.pdf_path.read_bytes()
    preview_bytes = result.artifacts.preview_path.read_bytes()
    xlsx_bytes = result.artifacts.xlsx_path.read_bytes()
    json_bytes = result.artifacts.json_path.read_bytes()
    download_columns = st.columns(3)
    download_columns[0].download_button(
        "PDF 다운로드",
        data=pdf_bytes,
        file_name=result.artifacts.pdf_path.name,
        mime="application/pdf",
        use_container_width=True,
    )
    download_columns[1].download_button(
        "XLSX 다운로드",
        data=xlsx_bytes,
        file_name=result.artifacts.xlsx_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    download_columns[2].download_button(
        "실행 로그 다운로드",
        data=json_bytes,
        file_name=result.artifacts.json_path.name,
        mime="application/json",
        use_container_width=True,
    )
    st.image(
        preview_bytes,
        caption="Daily Insight PDF 미리보기",
        use_container_width=True,
    )

with tabs[4]:
    st.subheader("SMTP 메일 발송")
    st.caption(
        "Gmail 권장값: smtp.gmail.com · 587 · STARTTLS · "
        "전체 Gmail 주소 · 16자리 앱 비밀번호"
    )
    sender_default = env_value("EMAIL_FROM", DEFAULT_EMAIL)
    recipient_default = env_value("EMAIL_TO", DEFAULT_EMAIL)
    sender = st.text_input("발신자", value=sender_default)
    recipient = st.text_input("수신자", value=recipient_default)
    smtp_columns = st.columns([2, 1, 1])
    smtp_host = smtp_columns[0].text_input(
        "SMTP Host",
        value=env_value("SMTP_HOST", "smtp.gmail.com"),
        placeholder="smtp.gmail.com",
    )
    smtp_port = smtp_columns[1].number_input(
        "Port",
        min_value=1,
        max_value=65535,
        value=env_int("SMTP_PORT", 587),
    )
    security_options = ["starttls", "ssl", "none"]
    configured_security = env_value("SMTP_SECURITY", "starttls").lower()
    security_index = (
        security_options.index(configured_security)
        if configured_security in security_options
        else 0
    )
    smtp_security = smtp_columns[2].selectbox(
        "보안",
        security_options,
        index=security_index,
    )
    credential_columns = st.columns(2)
    smtp_username = credential_columns[0].text_input(
        "SMTP Username",
        value=env_value("SMTP_USERNAME"),
    )
    smtp_password = credential_columns[1].text_input(
        "SMTP App Password",
        value=env_value("SMTP_PASSWORD"),
        type="password",
        help="Gmail 계정의 일반 비밀번호가 아니라 Google에서 발급한 16자리 앱 비밀번호",
    )

    eml_bytes = email_as_bytes(
        sender=sender,
        recipient=recipient,
        subject=result.artifacts.email_subject,
        html_body=result.artifacts.html_body,
        attachments=[
            result.artifacts.pdf_path,
            result.artifacts.xlsx_path,
        ],
    )
    action_columns = st.columns(2)
    action_columns[0].download_button(
        "EML 파일 다운로드",
        data=eml_bytes,
        file_name="Daily_Insight_Email.eml",
        mime="message/rfc822",
        use_container_width=True,
    )
    if action_columns[1].button(
        "PDF 첨부 메일 발송",
        type="primary",
        use_container_width=True,
    ):
        try:
            send_email(
                settings=SMTPSettings(
                    host=smtp_host,
                    port=int(smtp_port),
                    username=smtp_username,
                    password=smtp_password,
                    security=smtp_security,
                ),
                sender=sender,
                recipient=recipient,
                subject=result.artifacts.email_subject,
                html_body=result.artifacts.html_body,
                attachments=[
                    result.artifacts.pdf_path,
                    result.artifacts.xlsx_path,
                ],
            )
            st.success(f"{recipient} 주소로 메일을 발송했습니다.")
        except Exception as exc:
            st.error(f"메일 발송 실패: {exc}")
