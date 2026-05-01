"""
EU CBAM (Carbon Border Adjustment Mechanism) 한국 기업 영향 계산기
=====================================================================

목적:
  EU CBAM 본격 시행 (2026.1.1) 후 한국 주요 수출기업의 부담을 시뮬레이션하고,
  탄소감축 수단(CCS, DRI-H₂, EAF, RE100 등) 적용 시 회피 가능액을 계산.

핵심 수식:
  CBAM cost = (SEE − Free EU benchmark) × Phase-in factor × EUA × import volume

지표 정의:
  SEE     [tCO₂/t]     Specific Embedded Emissions
  Phase-in factor       2026: 2.5% → 2034: 100% (선형 ramp)
  Free benchmark         EU 무상할당 벤치마크 (sector·공정별 상이)
  EUA                    EU Emissions Allowance 가격 (€/tCO₂)

데이터 소스:
  - EU Regulation (EU) 2023/956  (CBAM 본법)
  - EU IR 2023/1773              (전이기간 시행령)
  - EU IR 2025/2621              (Annex I default values, Annex II 전력 EF)
  - 대한상의 SGI Brief 22 (2024) 철강 영향
  - KOTRA 공급망 인사이트 (CBAM)
  - POSCO Climate Risk 2025
  - InfluenceMap (2024) 한·일 철강 CBAM
  - ICAP, Sandbag, EEX, ICE EUA Futures
  - IEA, IEAGHG, NETL, World Steel Association

자매 도구: https://github.com/cafeon90-oss/CCUS_benchmark
실행:    streamlit run app.py
"""

import json
import math
import os
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ======================================================================
# 페이지 설정 + 다크모드 CSS
# ======================================================================
st.set_page_config(
    page_title="EU CBAM 영향 계산기",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    /* ─────────────────────────────────────────────────
       전역 — 차분한 다크모드 (Linear/Vercel 톤)
       ───────────────────────────────────────────────── */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    .main, .block-container,
    body, html { background-color: #0a0d14 !important; }
    body, [class*="st"] { color: #F0F2F5; }

    /* Streamlit 상단 헤더 / 툴바 / 데코레이션 — 흰 띠 제거 */
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    .stApp > header {
        background-color: #0a0d14 !important;
        background: #0a0d14 !important;
    }
    /* 헤더 안의 모든 흰색 배경 요소 차단 */
    header[data-testid="stHeader"] * {
        background-color: transparent !important;
    }
    /* Streamlit 상단의 가는 흰색 띠 (deploy bar / running bar) */
    [data-testid="stDecoration"] {
        background-image: none !important;
        height: 0 !important;
    }
    /* 햄버거 메뉴, share 버튼 등 아이콘 색상 */
    header[data-testid="stHeader"] svg,
    header[data-testid="stHeader"] button {
        color: #A8AEB6 !important;
        fill: #A8AEB6 !important;
    }
    /* 본문 영역 패딩 정돈 (헤더 가렸을 때 본문이 위로 밀리지 않게) */
    .main .block-container {
        padding-top: 2rem !important;
    }

    /* 본문 헤더 */
    h1 {
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
        color: #F0F2F5 !important;
    }
    h2, h3, h4 {
        font-weight: 500 !important;
        color: #F0F2F5 !important;
    }

    /* 사이드바 완전 불투명 + 차분 */
    section[data-testid="stSidebar"] {
        background-color: #0a0d14 !important;
        opacity: 1 !important;
        border-right: 1px solid #1f2733;
    }
    section[data-testid="stSidebar"] > div:first-child { background-color: #0a0d14 !important; }
    section[data-testid="stSidebar"] * { background-color: transparent; }
    section[data-testid="stSidebar"] h3 {
        font-size: 0.78rem !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #A8AEB6 !important;
        font-weight: 500 !important;
        margin-top: 4px !important;
    }

    /* 탭 — 모던 underline 스타일 */
    div[data-baseweb="tab-list"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        scrollbar-width: thin;
        gap: 0 !important;
        border-bottom: 1px solid #1f2733;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar { height: 4px; }
    div[data-baseweb="tab-list"]::-webkit-scrollbar-thumb { background: #2a3346; border-radius: 2px; }
    div[data-baseweb="tab-list"] button {
        flex-shrink: 0 !important;
        white-space: nowrap;
        font-size: 0.86rem !important;
        font-weight: 500 !important;
        color: #A8AEB6 !important;
        padding: 10px 14px !important;
        border-bottom: 2px solid transparent !important;
        transition: color 0.15s ease;
    }
    div[data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #4FC3F7 !important;
        border-bottom-color: #4FC3F7 !important;
    }
    div[data-baseweb="tab-list"] button:hover { color: #B0BEC5 !important; }

    /* 메트릭 카드 — 좌측 strip + flat */
    div[data-testid="stMetric"] {
        background-color: #11161e;
        padding: 13px 16px 13px 18px;
        border-radius: 10px;
        border: 1px solid #1f2733;
        position: relative;
        overflow: hidden;
        transition: border-color 0.15s ease;
    }
    div[data-testid="stMetric"]:hover { border-color: #2a3346; }
    /* KPI 카드 좌측 strip은 nth-child로 색상 부여 */
    div[data-testid="stMetric"]::before {
        content: "";
        position: absolute;
        top: 0; left: 0; bottom: 0;
        width: 2px;
        background: #4FC3F7;
    }
    /* 4개 컬럼 KPI 카드의 색상 strip 다양화 */
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) div[data-testid="stMetric"]::before { background: #4FC3F7; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) div[data-testid="stMetric"]::before { background: #9575CD; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) div[data-testid="stMetric"]::before { background: #FFB74D; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(4) div[data-testid="stMetric"]::before { background: #81C784; }

    div[data-testid="stMetricLabel"] {
        font-size: 0.66rem !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #A8AEB6 !important;
        font-weight: 500 !important;
    }
    div[data-testid="stMetricLabel"] > div { font-weight: 500 !important; }
    div[data-testid="stMetricValue"] {
        font-size: 1.35rem !important;
        font-weight: 600 !important;
        line-height: 1.2;
        color: #F0F2F5 !important;
        letter-spacing: -0.02em;
        margin-top: 4px !important;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 0.7rem !important;
        color: #D4D8DD !important;
    }
    div[data-testid="stMetricDelta"] svg { display: none; }

    /* 인사이트 박스 — flat + 좌측 strip */
    .insight-box {
        background: #11161e;
        border: 1px solid #1f2733;
        border-left: 2px solid #4FC3F7;
        padding: 13px 16px;
        margin: 10px 0;
        border-radius: 0 8px 8px 0;
        color: #D4D8DD;
        font-size: 0.88rem;
        line-height: 1.65;
    }
    .insight-box strong { color: #F0F2F5; font-weight: 500; }
    .insight-box.good { border-left-color: #81C784; }
    .insight-box.warn { border-left-color: #FFB74D; }
    .insight-box.bad  { border-left-color: #E57373; }
    .insight-box .good { color: #A5D6A7; font-weight: 500; }
    .insight-box .warn { color: #FFCC80; font-weight: 500; }
    .insight-box .bad  { color: #EF9A9A; font-weight: 500; }

    /* Omnibus 알림 — 컴팩트 */
    .omnibus-banner {
        display: flex;
        gap: 10px;
        align-items: center;
        background: #11161e;
        border: 1px solid #1f2733;
        border-radius: 8px;
        padding: 9px 14px;
        margin: 10px 0 16px 0;
        font-size: 0.8rem;
        color: #D4D8DD;
    }
    .omnibus-banner .new-badge {
        background: #1d2b22;
        color: #81C784;
        font-size: 0.66rem;
        font-weight: 500;
        padding: 2px 7px;
        border-radius: 4px;
        letter-spacing: 0.04em;
        flex-shrink: 0;
    }
    .omnibus-banner a {
        color: #81C784;
        text-decoration: none;
        font-size: 0.78rem;
        margin-left: auto;
        flex-shrink: 0;
    }

    /* 자매도구 안내 카드 — 차분 톤 */
    .sister-card {
        background: #11161e;
        border: 1px solid #1f2733;
        border-left: 2px solid #9b8de8;
        border-radius: 0 8px 8px 0;
        padding: 13px 16px;
        margin: 10px 0;
        font-size: 0.88rem;
        color: #D4D8DD;
        line-height: 1.6;
    }
    .sister-card a { color: #9b8de8; text-decoration: none; font-weight: 500; }
    .sister-card a:hover { text-decoration: underline; }
    .sister-card h4 { color: #F0F2F5 !important; font-weight: 500 !important; }

    /* ─────────────────────────────────────────────────
       DataFrame — 다크모드 강제 (Streamlit이 기본 흰 배경 적용 방지)
       ───────────────────────────────────────────────── */
    div[data-testid="stDataFrame"],
    div[data-testid="stTable"],
    .stDataFrame {
        background-color: #11161e !important;
        border-radius: 8px;
        overflow: hidden;
    }
    div[data-testid="stDataFrame"] table,
    div[data-testid="stDataFrame"] [data-testid="StyledDataFrameBody"],
    div[data-testid="stDataFrame"] [data-testid="StyledDataFrameDataCell"],
    .stDataFrame table {
        background-color: #11161e !important;
        color: #F0F2F5 !important;
    }
    div[data-testid="stDataFrame"] thead th,
    div[data-testid="stDataFrame"] [data-testid="StyledDataFrameHeaderCell"],
    .stDataFrame thead th {
        background-color: #161c26 !important;
        color: #D4D8DD !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-size: 0.72rem !important;
        border-bottom: 1px solid #1f2733 !important;
    }
    div[data-testid="stDataFrame"] tbody tr td,
    div[data-testid="stDataFrame"] tbody tr,
    .stDataFrame tbody tr td {
        background-color: #11161e !important;
        color: #F0F2F5 !important;
        border-bottom: 1px solid #1a2028 !important;
    }
    /* glide-data-grid (Streamlit 신형 dataframe) 다크 강제 */
    .glide-data-grid, .gdg-wmyidgi, [class*="dvn-scroller"] {
        background-color: #11161e !important;
        color: #F0F2F5 !important;
    }

    /* ─────────────────────────────────────────────────
       Select / Dropdown — 텍스트 안 보이는 문제 수정
       ───────────────────────────────────────────────── */
    /* 닫힌 select 박스 */
    div[data-baseweb="select"] > div {
        background-color: #11161e !important;
        border-color: #1f2733 !important;
        color: #F0F2F5 !important;
    }
    div[data-baseweb="select"] > div:hover { border-color: #2a3346 !important; }
    div[data-baseweb="select"] > div > div,
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input {
        color: #F0F2F5 !important;
        background-color: transparent !important;
    }
    /* 열린 dropdown 메뉴 (포털로 body 직속 렌더링됨) */
    div[data-baseweb="popover"],
    div[data-baseweb="menu"],
    ul[role="listbox"] {
        background-color: #11161e !important;
        border: 1px solid #1f2733 !important;
    }
    div[data-baseweb="popover"] li,
    div[data-baseweb="menu"] li,
    ul[role="listbox"] li {
        background-color: #11161e !important;
        color: #F0F2F5 !important;
    }
    div[data-baseweb="popover"] li:hover,
    div[data-baseweb="menu"] li:hover,
    ul[role="listbox"] li:hover,
    li[aria-selected="true"] {
        background-color: #1a2330 !important;
        color: #F0F2F5 !important;
    }

    /* Text input + number input */
    div[data-baseweb="input"] > div,
    div[data-baseweb="base-input"] {
        background-color: #11161e !important;
        border-color: #1f2733 !important;
    }
    div[data-baseweb="input"] input,
    div[data-baseweb="base-input"] input,
    .stNumberInput input, .stTextInput input {
        background-color: #11161e !important;
        color: #F0F2F5 !important;
    }

    /* ─────────────────────────────────────────────────
       Radio 버튼 — Streamlit 기본 스타일 유지하면서 색상만 정돈
       (이전 시도가 width/height 강제로 텍스트까지 무너뜨림 → 최소 개입)
       ───────────────────────────────────────────────── */
    /* 라벨 텍스트 — 가로 배열 + 흰색 */
    .stRadio label,
    div[data-testid="stRadio"] label,
    .stRadio p {
        color: #F0F2F5 !important;
        font-size: 0.86rem !important;
    }
    /* radiogroup 컨테이너만 가로 정렬 보장 */
    div[role="radiogroup"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 14px !important;
        align-items: center !important;
    }
    /* 각 옵션도 가로 정렬 (라벨이 세로로 안 무너지게) */
    div[role="radiogroup"] > label {
        display: inline-flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 6px !important;
        white-space: nowrap !important;
        margin: 0 !important;
    }

    /* Checkbox */
    .stCheckbox label { color: #F0F2F5 !important; }

    /* MultiSelect 칩 */
    span[data-baseweb="tag"] {
        background-color: #1a2330 !important;
        color: #F0F2F5 !important;
        border-color: #2a3346 !important;
    }

    /* 슬라이더 — cyan accent */
    div[data-baseweb="slider"] [role="slider"] {
        background-color: #4FC3F7 !important;
        border-color: #4FC3F7 !important;
    }
    div[data-baseweb="slider"] [data-testid="stTickBar"] {
        color: #A8AEB6 !important;
    }

    /* Expander — 차분 */
    div[data-testid="stExpander"] {
        background-color: #11161e;
        border: 1px solid #1f2733 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stExpander"] summary { color: #D4D8DD !important; }
    div[data-testid="stExpander"] details > summary:hover { color: #F0F2F5 !important; }

    /* 캡션 — 명도 보장 */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: #A8AEB6 !important;
    }

    /* Help (?) 아이콘 툴팁 */
    [data-testid="stTooltipIcon"] svg { fill: #6b7689 !important; }

    /* 모바일 폰트 축소 */
    @media (max-width: 640px) {
        h1 { font-size: 1.35rem !important; }
        h2 { font-size: 1.1rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.05rem !important; }
        div[data-testid="stMetricLabel"] { font-size: 0.62rem !important; }
        .insight-box, .sister-card { font-size: 0.82rem; }
        .omnibus-banner { font-size: 0.75rem; padding: 8px 12px; }
        div[data-baseweb="tab-list"] button { font-size: 0.78rem !important; padding: 9px 11px !important; }
    }

    /* 그래프 완전 정적화 — 모바일 핀치/터치 줌 차단 강화 */
    .js-plotly-plot, .plotly, .plot-container, .main-svg,
    div[data-testid="stPlotlyChart"], div[data-testid="stPlotlyChart"] * {
        touch-action: pan-y !important;       /* 페이지 세로 스크롤만 허용 */
        -ms-touch-action: pan-y !important;
        -webkit-user-select: none !important;
        user-select: none !important;
        -webkit-tap-highlight-color: transparent !important;
    }
    /* 차트 내부의 모든 SVG 요소에서 포인터 이벤트 차단 (drilldown 차단 핵심) */
    .js-plotly-plot .plotly svg,
    .js-plotly-plot .main-svg .draglayer,
    .js-plotly-plot .main-svg .nsewdrag,
    .js-plotly-plot .main-svg .cursor-pointer {
        pointer-events: none !important;
    }
    /* hover, modebar, cursor 모두 무력화 */
    .js-plotly-plot .plotly .modebar,
    .js-plotly-plot .plotly .modebar-container,
    .js-plotly-plot .plotly .hoverlayer,
    .js-plotly-plot .plotly .hovertext { display: none !important; }
    .js-plotly-plot * { cursor: default !important; }
    /* 핀치줌·더블탭줌 방지 (메타뷰포트와 별개로 차트 영역만 격리) */
    .js-plotly-plot { -webkit-touch-callout: none !important; }

    /* 사이드바 multiselect 칩 글자 잘림 방지 */
    section[data-testid="stSidebar"] [data-baseweb="tag"] {
        max-width: 100% !important;
        height: auto !important;
        margin: 2px 2px !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="tag"] > div {
        white-space: normal !important;
        word-break: break-word !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.3 !important;
    }

    /* 데스크톱 사이드바 폭 */
    @media (min-width: 768px) {
        section[data-testid="stSidebar"] {
            min-width: 360px !important;
            width: 360px !important;
        }
        section[data-testid="stSidebar"] > div { min-width: 360px !important; }
    }

    /* 푸터 카드 — 차분 */
    .footer-card {
        background: #11161e;
        border-radius: 12px;
        padding: 18px 22px;
        margin: 24px 0 8px 0;
        border: 1px solid #1f2733;
        position: relative;
    }
    .footer-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, #4FC3F7 0%, #9b8de8 100%);
        border-radius: 12px 12px 0 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================
# Plotly 정적화 config (모든 차트 공통)
# ======================================================================
PLOTLY_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showTips": False,
    "displaylogo": False,
    "staticPlot": True,                  # 핵심 정적 모드
    "showAxisDragHandles": False,
    "showAxisRangeEntryBoxes": False,
    "responsive": True,
    "editable": False,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
        "hoverClosestCartesian", "hoverCompareCartesian",
        "toggleSpikelines", "toImage",
    ],
}


def lock_static(fig):
    """차트 정적 잠금 + 톤다운된 흰색 텍스트 강제 (다크모드 가독성).
    모든 fig 직전에 호출."""
    fig.update_layout(
        dragmode=False,
        hovermode=False,
        clickmode="none",
        # 텍스트 색상 — 톤다운된 흰색 통일
        font=dict(color=C_TEXT2, family="-apple-system, sans-serif", size=12),
        title=dict(font=dict(color=C_TEXT, size=14)),
        legend=dict(font=dict(color=C_TEXT2, size=11)),
        # 배경 — 카드와 자연스럽게 녹게
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
    )
    # 축 라벨/눈금/그리드 — 회색 격자 대신 어두운 톤다운된 흰색
    axis_style = dict(
        color=C_TEXT2,
        tickfont=dict(color=C_TEXT3, size=11),
        title_font=dict(color=C_TEXT2, size=12),
        gridcolor="#1f2733",
        linecolor="#252b36",
        zerolinecolor="#252b36",
        fixedrange=True,
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    return fig

# 색상 팔레트 (차분 다크모드 v3 — 톤다운된 흰색 통일)
# 모든 텍스트는 흰색 계열, 명도만 단계 — 회색 일절 사용 X
C_BG       = "#0a0d14"   # 본문 배경
C_CARD     = "#11161e"   # 카드 배경
C_PRIMARY  = "#4FC3F7"   # 정보 (cyan)
C_ACCENT   = "#9575CD"   # 보조 강조 (soft purple)
C_GOOD     = "#81C784"   # 좋음 (녹색)
C_WARN     = "#FFB74D"   # 주의 (주황)
C_BAD      = "#E57373"   # 나쁨 (빨강)
C_HIGH     = "#FFEB3B"   # 강조 (노랑)
C_TEXT     = "#F0F2F5"   # primary text (90% white)
C_TEXT2    = "#D4D8DD"   # secondary text (75% white) — 부제, 설명
C_TEXT3    = "#A8AEB6"   # tertiary text (60% white) — caption, label
C_TEXT4    = "#7A8089"   # quaternary text (45% white) — placeholder, footer
C_BORDER   = "#252b36"   # 테두리

# 지역 색상 코딩
REGION_COLORS = {
    "US":  "🟦",
    "EU":  "🟨",
    "UK":  "🟪",
    "KR":  "🟧",
    "ANY": "⚪",
    "GLOBAL": "🌍",
}

def region_icon(key: str) -> str:
    return REGION_COLORS.get(key.upper(), "⚪")


# ======================================================================
# 자매 CCUS 도구 연계 (Phase 2 — 현재는 stub + placeholder)
# ======================================================================
CCUS_REPO_URL = "https://github.com/cafeon90-oss/CCUS_benchmark"
CCUS_JSON_URL = "https://raw.githubusercontent.com/cafeon90-oss/CCUS_benchmark/main/data/ccus_metrics.json"

# Phase 2에서 위 URL로 fetch — 현재는 placeholder mirror
DEFAULT_CCUS_METRICS = {
    "schema_version": "1.0-stub",
    "last_updated": "2026-05-01",
    "currency": "USD",
    "year_basis": 2025,
    "source_tool": CCUS_REPO_URL,
    "technologies": {
        "MEA_30wt": {
            "display_name": "MEA 30wt% (baseline)", "short_name": "MEA",
            "COCA_USD_per_tCO2": 60, "CAPEX_USD_per_tpy": 950, "OPEX_USD_per_tCO2": 35,
            "TRL": 9, "capture_rate": 0.90,
        },
        "K2CO3_KIERSOL": {
            "display_name": "KIERSOL (KIER)", "short_name": "KIERSOL",
            "COCA_USD_per_tCO2": 50, "CAPEX_USD_per_tpy": 1050, "OPEX_USD_per_tCO2": 28,
            "TRL": 7, "capture_rate": 0.90,
        },
        "Chilled_NH3_CAP": {
            "display_name": "Chilled Ammonia (CAP)", "short_name": "CAP",
            "COCA_USD_per_tCO2": 55, "CAPEX_USD_per_tpy": 1200, "OPEX_USD_per_tCO2": 30,
            "TRL": 8, "capture_rate": 0.90,
        },
        "Biphasic_DMX": {
            "display_name": "Biphasic DMX™", "short_name": "DMX",
            "COCA_USD_per_tCO2": 42, "CAPEX_USD_per_tpy": 1100, "OPEX_USD_per_tCO2": 22,
            "TRL": 7, "capture_rate": 0.90,
        },
        "Solid_TSA": {
            "display_name": "Solid Sorbent TSA", "short_name": "TSA",
            "COCA_USD_per_tCO2": 70, "CAPEX_USD_per_tpy": 1400, "OPEX_USD_per_tCO2": 40,
            "TRL": 6, "capture_rate": 0.90,
        },
        "Calcium_Looping": {
            "display_name": "Calcium Looping (CaL)", "short_name": "CaL",
            "COCA_USD_per_tCO2": 38, "CAPEX_USD_per_tpy": 1300, "OPEX_USD_per_tCO2": 20,
            "TRL": 7, "capture_rate": 0.95,
        },
    },
    "sector_fit": {
        "steel_BF_BOF":   ["MEA_30wt", "Chilled_NH3_CAP", "Calcium_Looping"],
        "steel_EAF":      ["Solid_TSA", "Biphasic_DMX"],
        "cement":         ["Calcium_Looping", "Chilled_NH3_CAP", "MEA_30wt"],
        "aluminum":       ["MEA_30wt", "Biphasic_DMX"],
        "fertilizer_NH3": ["MEA_30wt", "K2CO3_KIERSOL"],
        "hydrogen_SMR":   ["MEA_30wt", "Biphasic_DMX", "K2CO3_KIERSOL"],
        "power":          ["MEA_30wt", "Chilled_NH3_CAP", "Calcium_Looping"],
    },
}


@st.cache_data(ttl=86400)
def load_ccus_metrics():
    """CCUS 도구 metrics fetch. Phase 2에서 활성화. 현재는 stub."""
    # Phase 2:
    # try:
    #     r = requests.get(CCUS_JSON_URL, timeout=5); r.raise_for_status()
    #     return r.json(), "live"
    # except Exception:
    #     return DEFAULT_CCUS_METRICS, "fallback"
    return DEFAULT_CCUS_METRICS, "stub"


# ======================================================================
# EUA 가격 자동 fetch (GitHub Actions로 주 1회 갱신되는 JSON 사용)
# ======================================================================
EUA_JSON_LOCAL = Path(__file__).parent / "data" / "eua_price.json"

@st.cache_data(ttl=86400)
def load_eua_price():
    """data/eua_price.json에서 최신 EUA 가격 로드. 실패 시 fallback."""
    try:
        if EUA_JSON_LOCAL.exists():
            data = json.loads(EUA_JSON_LOCAL.read_text(encoding="utf-8"))
            return float(data.get("price_eur_per_tco2", 80.0)), data.get("date", "n/a"), "auto"
    except Exception:
        pass
    return 80.0, "fallback", "fallback"


# ======================================================================
# 헬퍼 함수
# ======================================================================
def fmt_krw_amt(krw: float, sign: bool = False) -> str:
    """억원/조원 자동 단위. sign=True면 부호 포함."""
    if abs(krw) >= 1e12:
        val, prec, unit = krw / 1e12, 2, "조원"
    else:
        val = krw / 1e8
        prec = 0 if abs(val) >= 100 else 1
        unit = "억원"
    s = f"{val:+,.{prec}f}" if sign else f"{val:,.{prec}f}"
    return f"{s}{unit}"


def fmt_money(usd: float, fx: float, mode: str = "Both", per_t: bool = False) -> str:
    """통화 표시. mode: USD | KRW | Both. per_t=True면 단위 톤당."""
    krw = usd * fx
    if per_t:
        usd_str = f"${usd:+,.1f}/t" if usd < 0 else f"${usd:,.1f}/t"
        krw_str = f"{krw:+,.0f} 원/t" if usd < 0 else f"{krw:,.0f} 원/t"
    else:
        usd_str = f"${usd/1e6:+,.2f}M" if usd < 0 else f"${usd/1e6:,.2f}M"
        krw_str = fmt_krw_amt(krw, sign=usd < 0)
    if mode == "USD":
        return usd_str
    if mode == "KRW":
        return krw_str
    return f"{usd_str} ({krw_str})"


def fmt_eur(eur: float, per_t: bool = False) -> str:
    if per_t:
        return f"€{eur:,.1f}/t"
    if abs(eur) >= 1e9:
        return f"€{eur/1e9:,.2f}B"
    if abs(eur) >= 1e6:
        return f"€{eur/1e6:,.2f}M"
    return f"€{eur:,.0f}"


def tip(term: str, label: str = None) -> str:
    """약어에 hover 툴팁 적용 (HTML abbr)."""
    desc = TOOLTIPS.get(term, "")
    text = label or term
    return (f'<abbr title="{desc}" '
            f'style="text-decoration:underline dotted;cursor:help;">{text}</abbr>')


# ======================================================================
# CBAM 핵심 상수 (EU Regulation 2023/956 + IR 2025/2621)
# ======================================================================
# Phase-in factor (CBAM이 부과하는 비율) — 2026~2034 ramp
PHASE_IN_FACTORS = {
    2023: 0.0,    2024: 0.0,    2025: 0.0,
    2026: 0.025,  2027: 0.05,   2028: 0.10,
    2029: 0.225,  2030: 0.485,  2031: 0.61,
    2032: 0.735,  2033: 0.86,   2034: 1.00,
}

def phase_in(year: int) -> float:
    """연도별 CBAM phase-in factor (0~1). 2034 이후는 100%."""
    if year >= 2034:
        return 1.0
    return PHASE_IN_FACTORS.get(year, 0.0)


# 한국 grid 배출계수 (간접 emissions 산정용, kgCO₂/kWh)
KR_GRID_FACTOR = 0.443    # 2024 한국 평균
EU_GRID_FACTOR = 0.230    # 2024 EU 평균


# ======================================================================
# Sector 라이브러리 (LIT) — 6개 CBAM sector + 한국 평균 SEE
# ======================================================================
LIT = {
    # ─────────────── 철강 ───────────────
    "steel_BF_BOF": {
        "name": "철강 (BF-BOF, HRC)",
        "name_en": "Steel (Blast Furnace + Basic Oxygen Furnace)",
        "sector_key": "steel",
        "process": "BF-BOF",
        "product": "Hot-rolled coil",
        "default_SEE": 2.0,           # CBAM default value (Annex I 평균 추정)
        "kr_avg_SEE": 2.127,          # POSCO 2025 Climate Risk 자료
        "eu_benchmark": 1.370,        # EU finalized free allocation benchmark
        "unit": "tCO₂/t crude steel",
        "product_unit": "ton",
        "ccus_sector": "steel_BF_BOF",
        "kr_eu_export_usd_2021": 4.3e9,  # ~$4.3B
        "color": "#90A4AE",
        "refs": ["EU_IR_2025_2621", "EU_REG_2023_956", "EUROMETAL_Bench", "POSCO_Climate_2025", "WSA_2024"],
    },
    "steel_DRI_EAF": {
        "name": "철강 (DRI-EAF, 수소 환원)",
        "name_en": "Steel (Direct Reduced Iron + Electric Arc Furnace)",
        "sector_key": "steel",
        "process": "DRI-EAF",
        "product": "Steel (DRI)",
        "default_SEE": 0.85,
        "kr_avg_SEE": 0.95,
        "eu_benchmark": 0.481,
        "unit": "tCO₂/t crude steel",
        "product_unit": "ton",
        "ccus_sector": "steel_BF_BOF",
        "kr_eu_export_usd_2021": 0,
        "color": "#A5D6A7",
        "refs": ["EUROMETAL_Bench", "EU_REG_2023_956", "WSA_2024"],
    },
    "steel_scrap_EAF": {
        "name": "철강 (Scrap-EAF, 전기로)",
        "name_en": "Steel (Scrap-based Electric Arc Furnace)",
        "sector_key": "steel",
        "process": "Scrap-EAF",
        "product": "Steel (EAF)",
        "default_SEE": 0.40,
        "kr_avg_SEE": 0.40,            # 현대제철 EAF
        "eu_benchmark": 0.072,
        "unit": "tCO₂/t crude steel",
        "product_unit": "ton",
        "ccus_sector": "steel_EAF",
        "kr_eu_export_usd_2021": 0,
        "color": "#81C784",
        "refs": ["EUROMETAL_Bench", "EU_REG_2023_956", "Hyundai_Steel_2024"],
    },
    # ─────────────── 시멘트 ───────────────
    "cement_clinker": {
        "name": "시멘트 (Clinker)",
        "name_en": "Cement (Clinker)",
        "sector_key": "cement",
        "process": "Dry kiln",
        "product": "Clinker",
        "default_SEE": 0.85,
        "kr_avg_SEE": 0.85,
        "eu_benchmark": 0.693,
        "unit": "tCO₂/t clinker",
        "product_unit": "ton",
        "ccus_sector": "cement",
        "kr_eu_export_usd_2021": 1e6,
        "color": "#BCAAA4",
        "refs": ["EU_IR_2025_2621", "Norcem_Brevik_2024", "IEAGHG_Cement"],
    },
    # ─────────────── 알루미늄 ───────────────
    "aluminum_primary": {
        "name": "알루미늄 (Primary, Hall-Héroult)",
        "name_en": "Aluminum (Primary smelter)",
        "sector_key": "aluminum",
        "process": "Hall-Héroult",
        "product": "Primary aluminum ingot",
        "default_SEE": 10.0,           # 한국은 수입 ingot 가공 위주, 해외 ingot의 경우 grid factor가 dominant
        "kr_avg_SEE": 10.0,
        "eu_benchmark": 1.514,
        "unit": "tCO₂/t Al",
        "product_unit": "ton",
        "ccus_sector": "aluminum",
        "kr_eu_export_usd_2021": 5e8,
        "color": "#B0BEC5",
        "refs": ["EU_IR_2025_2621", "IAI_Aluminum_2024", "Novelis_Korea"],
    },
    # ─────────────── 비료 ───────────────
    "fertilizer_NH3": {
        "name": "비료 (NH₃, 암모니아)",
        "name_en": "Fertilizer (Ammonia)",
        "sector_key": "fertilizer",
        "process": "Haber-Bosch (SMR)",
        "product": "Ammonia",
        "default_SEE": 2.0,
        "kr_avg_SEE": 2.0,
        "eu_benchmark": 1.619,
        "unit": "tCO₂/t NH₃",
        "product_unit": "ton",
        "ccus_sector": "fertilizer_NH3",
        "kr_eu_export_usd_2021": 5e6,
        "color": "#CE93D8",
        "refs": ["EU_IR_2025_2621", "IFA_Fertilizer", "Hanwha_Solutions"],
    },
    # ─────────────── 수소 ───────────────
    "hydrogen_gray": {
        "name": "수소 (Gray, SMR)",
        "name_en": "Hydrogen (Gray, Steam Methane Reforming)",
        "sector_key": "hydrogen",
        "process": "SMR (no CCS)",
        "product": "H₂",
        "default_SEE": 9.5,
        "kr_avg_SEE": 10.0,
        "eu_benchmark": 8.85,
        "unit": "tCO₂/t H₂",
        "product_unit": "ton",
        "ccus_sector": "hydrogen_SMR",
        "kr_eu_export_usd_2021": 0,
        "color": "#FFAB91",
        "refs": ["EU_IR_2025_2621", "IEA_Hydrogen_2024", "SK_ES_H2"],
    },
    "hydrogen_blue": {
        "name": "수소 (Blue, SMR + CCS)",
        "name_en": "Hydrogen (Blue, SMR + CCS)",
        "sector_key": "hydrogen",
        "process": "SMR + CCS (90%)",
        "product": "H₂",
        "default_SEE": 1.2,
        "kr_avg_SEE": 1.0,
        "eu_benchmark": 8.85,           # 동일 benchmark — Blue는 default 보다 훨씬 낮음
        "unit": "tCO₂/t H₂",
        "product_unit": "ton",
        "ccus_sector": "hydrogen_SMR",
        "kr_eu_export_usd_2021": 0,
        "color": "#80DEEA",
        "refs": ["EU_IR_2025_2621", "IEA_Hydrogen_2024", "Northern_Lights_2024"],
    },
    # ─────────────── 전력 ───────────────
    "electricity": {
        "name": "전력 (Grid)",
        "name_en": "Electricity (Grid average)",
        "sector_key": "electricity",
        "process": "Mixed grid",
        "product": "Electricity",
        "default_SEE": 0.443,           # 한국 grid (kgCO₂/kWh = tCO₂/MWh)
        "kr_avg_SEE": 0.443,
        "eu_benchmark": 0.230,           # EU grid 평균
        "unit": "tCO₂/MWh",
        "product_unit": "MWh",
        "ccus_sector": "power",
        "kr_eu_export_usd_2021": 0,
        "color": "#FFE082",
        "refs": ["EU_IR_2025_2621", "IEA_Elec_Maps_2024", "KEPCO_2024"],
    },
}

SHORT_NAMES = {
    "steel_BF_BOF":     "BF-BOF",
    "steel_DRI_EAF":    "DRI-EAF",
    "steel_scrap_EAF":  "Scrap-EAF",
    "cement_clinker":   "Clinker",
    "aluminum_primary": "Al(prim)",
    "fertilizer_NH3":   "NH₃",
    "hydrogen_gray":    "H₂(gray)",
    "hydrogen_blue":    "H₂(blue)",
    "electricity":      "Grid",
}


# ======================================================================
# 시나리오 프리셋 (한국 기업 기반)
# ======================================================================
PRESETS = {
    "kr_posco_BF": {
        "label": "🇰🇷 POSCO (BF-BOF, ~75 Mt/yr)",
        "description": "포스코 광양·포항 BF-BOF · EU 수출 비중 5%",
        "sector_lit": "steel_BF_BOF",
        "settings": {
            "annual_production_mt": 75.0,
            "eu_export_share_pct": 5.0,
            "user_SEE": 2.127,
            "company_name": "POSCO",
        },
    },
    "kr_hyundai_BF": {
        "label": "🇰🇷 현대제철 (BF + EAF mix, ~24 Mt/yr)",
        "description": "현대제철 당진 BF + 인천·포항 EAF 혼합 (BF 70% 가정)",
        "sector_lit": "steel_BF_BOF",
        "settings": {
            "annual_production_mt": 24.0 * 0.7,
            "eu_export_share_pct": 7.0,
            "user_SEE": 2.05,
            "company_name": "현대제철 (BF)",
        },
    },
    "kr_hyundai_EAF": {
        "label": "🇰🇷 현대제철 (Pure Scrap-EAF, ~5 Mt/yr)",
        "description": "현대제철 EAF 라인 — 친환경 강재 EU 수출",
        "sector_lit": "steel_scrap_EAF",
        "settings": {
            "annual_production_mt": 5.0,
            "eu_export_share_pct": 10.0,
            "user_SEE": 0.40,
            "company_name": "현대제철 (EAF)",
        },
    },
    "kr_cement": {
        "label": "🇰🇷 쌍용·한일시멘트 (~10 Mt/yr clinker)",
        "description": "한국 주요 시멘트 — EU 수출 비중 매우 낮음",
        "sector_lit": "cement_clinker",
        "settings": {
            "annual_production_mt": 10.0,
            "eu_export_share_pct": 0.05,
            "user_SEE": 0.85,
            "company_name": "쌍용·한일시멘트",
        },
    },
    "kr_novelis": {
        "label": "🇰🇷 노벨리스 코리아 (Al, ~1.5 Mt/yr)",
        "description": "재활용 기반 알루미늄 (그러나 ingot은 import) · EU 수출",
        "sector_lit": "aluminum_primary",
        "settings": {
            "annual_production_mt": 1.5,
            "eu_export_share_pct": 15.0,
            "user_SEE": 8.0,    # 재활용 비중 반영 — 아직 primary 평균보다는 낮음
            "company_name": "노벨리스 코리아",
        },
    },
    "kr_hanwha": {
        "label": "🇰🇷 한화솔루션 (NH₃ 200 kt/yr)",
        "description": "비료·암모니아 — EU 수출 미미 (Korea Trade)",
        "sector_lit": "fertilizer_NH3",
        "settings": {
            "annual_production_mt": 0.2,
            "eu_export_share_pct": 5.0,
            "user_SEE": 2.0,
            "company_name": "한화솔루션",
        },
    },
    "kr_sk_h2_gray": {
        "label": "🇰🇷 SK E&S (Gray H₂, 100 kt/yr)",
        "description": "SMR 수소 — CCS 없음. 향후 EU 수출 잠재력",
        "sector_lit": "hydrogen_gray",
        "settings": {
            "annual_production_mt": 0.1,
            "eu_export_share_pct": 5.0,
            "user_SEE": 10.0,
            "company_name": "SK E&S (Gray)",
        },
    },
    "kr_sk_h2_blue": {
        "label": "🇰🇷 SK E&S + CCS (Blue H₂, 100 kt/yr)",
        "description": "SMR + CCS 90% — CBAM 부담 ~88% 회피",
        "sector_lit": "hydrogen_blue",
        "settings": {
            "annual_production_mt": 0.1,
            "eu_export_share_pct": 5.0,
            "user_SEE": 1.0,
            "company_name": "SK E&S + CCS (Blue)",
        },
    },
    "eu_dri_h2": {
        "label": "🌍 EU 베스트 (DRI-H₂ 철강, 참조용)",
        "description": "H2 Green Steel형 (스웨덴) — 한국 vs 최첨단 비교",
        "sector_lit": "steel_DRI_EAF",
        "settings": {
            "annual_production_mt": 5.0,
            "eu_export_share_pct": 0.0,
            "user_SEE": 0.40,
            "company_name": "H2 Green Steel (참조)",
        },
    },
    "custom": {
        "label": "✏️ Custom (직접 입력)",
        "description": "모든 입력값을 사용자가 직접 조정",
        "sector_lit": "steel_BF_BOF",
        "settings": {},
    },
}


def apply_preset():
    """프리셋 변경 시 모든 입력값 자동 세팅."""
    key = st.session_state.get("preset_select")
    if not key or key == "custom":
        return
    p = PRESETS.get(key)
    if not p:
        return
    st.session_state["sector_lit"] = p["sector_lit"]
    for k, v in p["settings"].items():
        st.session_state[k] = v


# ======================================================================
# 참고문헌 (REFS)
# ======================================================================
REFS = {
    # ────────────── EU 본법 + 시행령 (시간순) ──────────────
    "EU_REG_2023_956": {
        "cat": "regulation",
        "date": "2023-05-10 (adopted) · OJ L 130, 2023-05-16",
        "cite": "Regulation (EU) 2023/956 of the European Parliament and of the Council of "
                "10 May 2023 establishing a Carbon Border Adjustment Mechanism (CBAM). "
                "Entry into force: 17 May 2023. Transitional phase: 1 Oct 2023 – 31 Dec 2025. "
                "Definitive phase: 1 Jan 2026.",
        "url": "https://eur-lex.europa.eu/eli/reg/2023/956/oj",
        "used_for": "CBAM 본법 — sector·phase-in·인증서 의무",
    },
    "EU_IR_2023_1773": {
        "cat": "regulation",
        "date": "2023-08-17 (adopted) · OJ L 228, 2023-09-15",
        "cite": "Commission Implementing Regulation (EU) 2023/1773 of 17 August 2023 — "
                "transitional period reporting rules (quarterly CBAM reports). "
                "Applied: 1 Oct 2023 – 31 Dec 2025.",
        "url": "https://eur-lex.europa.eu/eli/reg_impl/2023/1773/oj",
        "used_for": "전이기간 (2023.10~2025.12) 분기별 보고",
    },
    "EU_OMNIBUS_2025": {
        "cat": "regulation",
        "date": "2025-09-29 (adopted) · OJ 2025-10-17 · effective 2025-10-20",
        "cite": "CBAM Omnibus Simplification Regulation (Sep 2025) — proposal: 26 Feb 2025; "
                "political agreement: 18 June 2025; final adoption: 29 Sep 2025; OJ: 17 Oct 2025; "
                "effective: 20 Oct 2025. Key changes: (1) 50-tonne de minimis threshold "
                "(excl. H₂ & electricity), (2) certificate sales postponed from 1 Jan 2026 → 1 Feb 2027, "
                "(3) annual declaration deadline 31 May → 30 Sep, (4) quarterly holdings 80% → 50%, "
                "(5) authorization grace period until 31 Mar 2026.",
        "url": "https://icapcarbonaction.com/en/news/eu-adopts-simplifications-cbam-rules-ahead-compliance-phase-starting-2026",
        "used_for": "2025년 Omnibus 단순화 — 50t threshold, 인증서 판매 일정, 연간 declaration",
    },
    "EU_PACKAGE_2025_12": {
        "cat": "regulation",
        "date": "2025-12-17 (released)",
        "cite": "European Commission CBAM Operational Package (17 Dec 2025) — 8 implementing acts "
                "+ 1 delegated act for definitive phase operation. Includes: CBAM certificate pricing "
                "(2026 quarterly avg, 2027+ weekly avg of EUA), verifier accreditation, "
                "definitive CBAM Registry rules. Plus proposal to extend scope to downstream "
                "steel/aluminium products (target: 2028).",
        "url": "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-legislation-and-guidance_en",
        "used_for": "Operational rules + downstream 확장 로드맵 (2028)",
    },
    "EU_IR_2025_2621": {
        "cat": "regulation",
        "date": "2025 · part of definitive phase package",
        "cite": "Commission Implementing Regulation (EU) 2025/2621 — country-specific default "
                "values (Annex I) and electricity emission factors (Annex II) for CBAM definitive "
                "phase. Mark-up: 10% (2026-2027) → 30% (2028+) for steel/cement/aluminium; "
                "1% for fertilizer.",
        "url": "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-legislation-and-guidance_en",
        "used_for": "Default SEE 값 + 전력 EF (2026~ 본격 시행)",
    },
    "EU_CBAM_TaxCustoms": {
        "cat": "regulation",
        "date": "live (페이지 — 지속 갱신)",
        "cite": "European Commission — Taxation & Customs Union: CBAM Official Page. "
                "Compliance phase in force since 1 Jan 2026.",
        "url": "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en",
        "used_for": "공식 sector list, 일정, FAQ",
    },
    # ────────────── 시장 데이터 / 산업 보고 ──────────────
    "EUROMETAL_Bench": {
        "cat": "report",
        "date": "2025-11 (publication)",
        "cite": "EUROMETAL (Nov 2025). EU Commission finalizes CBAM benchmarks, default values "
                "ahead of January 2026 launch — HRC: BF/BOF 1.370, DRI/EAF 0.481, scrap-EAF 0.072 tCO₂/t.",
        "url": "https://eurometal.net/eu-commission-finalizes-cbam-benchmarks-default-values-ahead-of-january-2026-launch/",
        "used_for": "철강 EU benchmark 확정값",
    },
    "ICAP_CBAM_2026": {
        "cat": "report",
        "date": "2026-01 (post-launch update)",
        "cite": "ICAP — International Carbon Action Partnership (Jan 2026). EU CBAM enters "
                "compliance phase. Phase-in factor 2.5%(2026)→100%(2034).",
        "url": "https://icapcarbonaction.com/en/news/eu-cbam-enters-compliance-phase-and-outlines-path-ahead",
        "used_for": "Phase-in schedule 검증",
    },
    "Coolset_CBAM": {
        "cat": "report",
        "date": "2026 (academy resource)",
        "cite": "Coolset (2026). CBAM timeline, deadlines and phases: What to expect in 2026. "
                "Free allowance phase-out 97.5%→0%, CBAM 2.5%→100%.",
        "url": "https://www.coolset.com/academy/cbam-timeline-deadlines-phases-what-to-expect-2026",
        "used_for": "Phase-in/out 표 정리",
    },
    "Climat_be_PhaseIn": {
        "cat": "report",
        "date": "2025-2026 (Belgium federal climate portal, live)",
        "cite": "Climat.be — Gradual CBAM phase-in (2026: 2.5%, 2027: 5%, 2028: 10%, "
                "2029: 22.5%, 2030: 48.5%, 2031: 61%, 2032: 73.5%, 2033: 86%, 2034: 100%).",
        "url": "https://climat.be/cbam-en/cbam-certificates/gradual-cbam-phase-in",
        "used_for": "연도별 phase-in factor 정확값",
    },
    "TTI_Korea_CBAM": {
        "cat": "report",
        "date": "2026 (Korea intelligence brief)",
        "cite": "Terawatt Times Institute (2026). Korea CBAM Intelligence — "
                "POSCO HRC 2026 €71/t → 2034 €259/t. SEE 2.127 vs benchmark 1.370.",
        "url": "https://terawatttimes.org/cbam-country-intelligence-korea-2026/",
        "used_for": "POSCO CBAM 부담 추정",
    },
    "InfluenceMap_KR_Steel": {
        "cat": "report",
        "date": "2024",
        "cite": "InfluenceMap (2024). Corporate Engagement by Japanese and Korean Steel "
                "Industry with the EU CBAM.",
        "url": "https://influencemap.org/report/Corporate-Engagement-by-Japanese-and-Korean-Steel-Industry-with-the-EU-CBAM-26493",
        "used_for": "한국 철강업체 CBAM 대응 분석",
    },
    "POSCO_Climate_2025": {
        "cat": "report",
        "date": "2025 (annual disclosure)",
        "cite": "POSCO Holdings (2025). Climate Risk Disclosure — Carbon intensity 2.127 tCO₂/t crude steel "
                "(scope 1+2). Hydrogen DRI roadmap 2030+.",
        "url": "https://www.posco.co.kr/",
        "used_for": "POSCO SEE 검증",
    },
    "KOTRA_CBAM": {
        "cat": "report",
        "date": "2024",
        "cite": "KOTRA 공급망 인사이트 (2024). CBAM 한국 수출 영향 — 철강 $43억, 알루미늄 $5억, "
                "비료 $500만, 시멘트 $100만 (2021 기준).",
        "url": "https://dream.kotra.or.kr/",
        "used_for": "한국 sector별 EU 수출액 (2021)",
    },
    "KCCI_SGI_22": {
        "cat": "report",
        "date": "2024 (대한상의 SGI brief)",
        "cite": "대한상공회의소 SGI 브리프 22호 (2024). CBAM 도입이 철강산업에 미치는 영향과 시사점.",
        "url": "https://sgi.korcham.net/File/Sgi/2024%20%EB%8C%80%ED%95%9C%EC%83%81%EC%9D%98%20SGI%20%EB%B8%8C%EB%A6%AC%ED%94%84%20%EC%A0%9C22%ED%98%B8.pdf",
        "used_for": "한국 철강 산업 CBAM 영향 분석",
    },
    "KITA_CBAM_3000": {
        "cat": "report",
        "date": "2024",
        "cite": "한국무역협회 (2024). CBAM 영향 보고서 — 약 3,000개 한국 기업·사업장 직간접 영향.",
        "url": "https://www.kita.net/",
        "used_for": "한국 영향 기업 수",
    },
    "WSA_2024": {
        "cat": "report",
        "date": "2024 (annual)",
        "cite": "World Steel Association (2024). World Steel in Figures 2024. Crude steel production "
                "+ CO₂ intensity by route.",
        "url": "https://worldsteel.org/",
        "used_for": "철강 글로벌 SEE 평균",
    },
    "Norcem_Brevik_2024": {
        "cat": "report",
        "date": "2024 (commissioning)",
        "cite": "Heidelberg Materials / Norcem Brevik CCS Project (2024). World's first cement plant "
                "CCS, 0.4 Mt/yr, ~€500M CAPEX.",
        "url": "https://www.heidelbergmaterials.com/en/sustainability/ccus",
        "used_for": "시멘트 CCS retrofit benchmark",
    },
    "IEAGHG_Cement": {
        "cat": "report",
        "date": "2013 (Report 2013/19)",
        "cite": "IEAGHG (2013). Deployment of CCS in the Cement Industry. Report 2013/19.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "시멘트 CCS 산업 분석",
    },
    "IAI_Aluminum_2024": {
        "cat": "report",
        "date": "2024",
        "cite": "International Aluminium Institute (2024). Greenhouse Gas Emissions — primary "
                "smelter intensity by region.",
        "url": "https://international-aluminium.org/",
        "used_for": "알루미늄 sector SEE",
    },
    "Novelis_Korea": {
        "cat": "report",
        "date": "2024 (annual)",
        "cite": "Novelis Korea — Sustainability Report 2024. Recycled aluminum content + CO₂ disclosure.",
        "url": "https://www.novelis.com/",
        "used_for": "노벨리스 한국 SEE 추정",
    },
    "Hyundai_Steel_2024": {
        "cat": "report",
        "date": "2024 (annual)",
        "cite": "현대제철 지속가능성보고서 (2024). EAF 라인 + 친환경 강재 EU 수출 전략.",
        "url": "https://www.hyundai-steel.com/",
        "used_for": "현대제철 EAF SEE 검증",
    },
    "IFA_Fertilizer": {
        "cat": "report",
        "date": "2023",
        "cite": "International Fertilizer Association (IFA) (2023). Energy Efficiency and CO₂ "
                "Emissions in Ammonia Production.",
        "url": "https://www.ifastat.org/",
        "used_for": "비료/NH₃ sector SEE",
    },
    "Hanwha_Solutions": {
        "cat": "report",
        "date": "2024 (annual ESG)",
        "cite": "한화솔루션 ESG 보고서 (2024). 비료·NH₃ 사업부 탄소집약도 공시.",
        "url": "https://www.hanwhasolutions.com/",
        "used_for": "한화솔루션 NH₃ SEE 검증",
    },
    "IEA_Hydrogen_2024": {
        "cat": "report",
        "date": "2024-09 (Global Hydrogen Review)",
        "cite": "IEA (2024). Global Hydrogen Review 2024. Gray vs Blue H₂ emission intensity, "
                "production cost.",
        "url": "https://www.iea.org/reports/global-hydrogen-review-2024",
        "used_for": "수소 sector SEE",
    },
    "SK_ES_H2": {
        "cat": "report",
        "date": "2024",
        "cite": "SK E&S (2024). Blue Hydrogen Roadmap. Boryeong LNG terminal + CCS · "
                "EU 수출 잠재력.",
        "url": "https://eng.skens.com/",
        "used_for": "한국 수소 EU 수출 전망",
    },
    "Northern_Lights_2024": {
        "cat": "report",
        "date": "2024 (operational)",
        "cite": "Northern Lights JV (Equinor/Shell/TotalEnergies, 2024). 1.5 Mt/yr transport & "
                "storage, ~€800M CAPEX. Greenfield blue H₂ benchmark.",
        "url": "https://norlights.com/",
        "used_for": "Blue H₂ + CCS 검증",
    },
    "IEA_Elec_Maps_2024": {
        "cat": "report",
        "date": "2024 (live database)",
        "cite": "IEA / Electricity Maps (2024). Grid Carbon Intensity Database. "
                "Korea 443, EU 230 gCO₂/kWh.",
        "url": "https://app.electricitymaps.com/",
        "used_for": "Grid 배출계수",
    },
    "KEPCO_2024": {
        "cat": "report",
        "date": "2024 (annual)",
        "cite": "한국전력공사 (2024). 한국 전력 평균 배출계수 공시.",
        "url": "https://home.kepco.co.kr/",
        "used_for": "한국 grid factor 0.443 tCO₂/MWh",
    },
    "EEX_EUA": {
        "cat": "market",
        "date": "live (daily)",
        "cite": "EEX — European Energy Exchange. EU ETS Spot, Futures & Options. "
                "EUA 가격 데이터 (€/tCO₂).",
        "url": "https://www.eex.com/en/markets/environmental-markets/eu-ets-spot-futures-options",
        "used_for": "EUA 가격",
    },
    "Sandbag_Carbon": {
        "cat": "market",
        "date": "live (daily price viewer)",
        "cite": "Sandbag — Carbon Price Viewer. EUA 일별 가격 추적.",
        "url": "https://sandbag.be/carbon-price-viewer/",
        "used_for": "EUA 자동 fetch (GitHub Actions)",
    },
    "GMK_EUA_2030": {
        "cat": "report",
        "date": "2025",
        "cite": "GMK Center (2025). Carbon price in the EU ETS to hit €126/t by 2030 "
                "(consensus forecast range €80~147).",
        "url": "https://gmk.center/en/infographic/carbon-price-in-the-eu-ets-to-hit-e126-t-by-2030/",
        "used_for": "EUA 장기 전망",
    },
    "TradingEcon_EUA": {
        "cat": "market",
        "date": "live (daily)",
        "cite": "Trading Economics — EU Carbon Permits historical data.",
        "url": "https://tradingeconomics.com/commodity/carbon",
        "used_for": "EUA 시계열",
    },
    "MOTIE_CBAM": {
        "cat": "report",
        "date": "2024 (범부처 TF)",
        "cite": "산업통상자원부 (2024). CBAM 대응 범부처 TF — 한국 영향 분석 및 지원방안.",
        "url": "https://www.motie.go.kr/",
        "used_for": "한국 정부 CBAM 대응",
    },
    "ME_K_ETS": {
        "cat": "report",
        "date": "2024 (운영 현황)",
        "cite": "환경부 (2024). 「온실가스 배출권의 할당 및 거래에 관한 법률」 K-ETS 운영 현황. "
                "K-ETS 가격 ~₩7,000~10,000/tCO₂ (2024-2025).",
        "url": "https://www.law.go.kr/",
        "used_for": "K-ETS 가격 (CBAM 차감 가능성)",
    },
    "MayerBrown_Omnibus": {
        "cat": "report",
        "date": "2025-10 (post-Omnibus analysis)",
        "cite": "Mayer Brown (Oct 2025). EU Adopts CBAM Simplification Regulation: 10 Key Amendments "
                "and Challenges Ahead.",
        "url": "https://www.mayerbrown.com/en/insights/publications/2025/10/eu-adopts-cbam-simplification-regulation-10-key-amendments-and-challenges-ahead",
        "used_for": "Omnibus 단순화 규정 — 법무법인 분석",
    },
    "ReedSmith_CBAM": {
        "cat": "report",
        "date": "2025-11",
        "cite": "Reed Smith (Nov 2025). What you need to know as CBAM simplification comes into effect.",
        "url": "https://www.reedsmith.com/our-insights/blogs/viewpoints/102lr9t/what-you-need-to-know-as-cbam-simplification-comes-into-effect/",
        "used_for": "Omnibus 시행 실무 가이드",
    },
}


def ref_link(ref_id: str, label: str = None) -> str:
    if ref_id not in REFS:
        return f"[{ref_id}]"
    r = REFS[ref_id]
    text = label or ref_id
    return f"[{text}]({r['url']})" if r.get("url") else text


# 호버 툴팁 사전
TOOLTIPS = {
    "SEE": (
        "Specific Embedded Emissions — 단위 제품당 내재 탄소배출량 [tCO₂/t]\n"
        "■ Direct (Scope 1) + Indirect (Scope 2, 일부 sector만) 합산\n"
        "■ EU CBAM은 verified 데이터 우선, 미제출 시 default 값 + mark-up\n"
        "■ 출처: EU Regulation 2023/956 Annex IV, IR 2025/2621"
    ),
    "CBAM": (
        "Carbon Border Adjustment Mechanism — EU 탄소국경조정제도\n"
        "■ 근거법: EU Regulation 2023/956\n"
        "■ 본격 시행: 2026.1.1 (definitive phase)\n"
        "■ 6개 sector: 철강, 시멘트, 알루미늄, 비료, 수소, 전력"
    ),
    "EUA": (
        "EU Emissions Allowance — EU ETS 탄소배출권 가격 [€/tCO₂]\n"
        "■ CBAM 인증서 가격 = EUA 주간 평균\n"
        "■ 2025 평균 ~€75, 2026 예상 ~€85, 2030 컨센서스 €126\n"
        "■ 출처: ICE / EEX, Sandbag, GMK Center"
    ),
    "Phase-in": (
        "CBAM Phase-in factor — 연도별 부과율\n"
        "■ 2026: 2.5%, 2027: 5%, 2028: 10%, 2029: 22.5%\n"
        "■ 2030: 48.5%, 2031: 61%, 2032: 73.5%, 2033: 86%, 2034: 100%\n"
        "■ EU ETS Free Allowance phase-out과 mirror"
    ),
    "Free benchmark": (
        "EU Free Allocation Benchmark — EU 무상할당 기준값 [tCO₂/t]\n"
        "■ Sector·공정별 상위 10% 효율 평균 기반\n"
        "■ 수입품 SEE가 이 값 초과시 그 차액에 CBAM 부과\n"
        "■ 철강 BF-BOF: 1.370, DRI-EAF: 0.481, Scrap-EAF: 0.072 (HRC 기준)"
    ),
    "ETS": (
        "Emissions Trading System — 배출권 거래제\n"
        "■ EU ETS: EUA 거래\n"
        "■ K-ETS: 한국 배출권 거래제 (₩7~10천/tCO₂)\n"
        "■ CBAM은 EU ETS 가격을 기준값으로 사용"
    ),
    "Phase-in factor": (
        "연도별 CBAM 적용 비율 (= 100% − Free allocation %)\n"
        "■ 2026 2.5%, 2030 48.5%, 2034 100%\n"
        "■ Free benchmark 초과분에만 적용"
    ),
    "Embedded emissions": (
        "내재 배출량 — 제품 생산 과정에서 발생한 누적 CO₂\n"
        "■ Scope 1 (직접) + Scope 2 (전력 간접)\n"
        "■ 일부 sector(시멘트·비료)는 indirect 포함"
    ),
    "BF-BOF": (
        "Blast Furnace + Basic Oxygen Furnace — 고로-전로 일관제철법\n"
        "■ 코크스 + 철광석 → 용선 → 강. 가장 보편적·고배출\n"
        "■ POSCO·현대제철 주력 공정. SEE ~2.0 tCO₂/t"
    ),
    "DRI-EAF": (
        "Direct Reduced Iron + Electric Arc Furnace — 직접환원철 + 전기로\n"
        "■ 천연가스 또는 수소로 직접 환원 → 전기로 용해\n"
        "■ H2-DRI는 차세대 친환경 철강. SEE ~0.4~0.85"
    ),
    "Scrap-EAF": (
        "Scrap-based Electric Arc Furnace — 고철 기반 전기로\n"
        "■ 고철 + 전기 → 강. 가장 친환경 (재활용)\n"
        "■ 현대제철 EAF 라인. SEE ~0.40 tCO₂/t"
    ),
    "CCS": (
        "Carbon Capture and Storage — 탄소 포집·저장\n"
        "■ 후연소(post), 전연소(pre), 산소연소(oxy)\n"
        "■ 90~99% 포집율. SEE를 직접 감축\n"
        "■ 자매 도구: CCUS_benchmark에서 기술별 비용 비교"
    ),
    "COCA": (
        "Cost Of Carbon Avoided — 회피된 CO₂ 톤당 비용 [USD/tCO₂]\n"
        "■ CCS 도입 비용을 격리량으로 나눈 값\n"
        "■ 자매 CCUS 도구의 핵심 KPI"
    ),
    "Free allowance": (
        "EU ETS Free Allocation — 무상할당량\n"
        "■ Carbon leakage 우려 sector에 EU 사업자에게 무상 부여\n"
        "■ CBAM 시행과 함께 phase-out (2026 97.5% → 2034 0%)"
    ),
}


# ======================================================================
# 핵심 계산 함수
# ======================================================================
def calc_unit_cbam(SEE: float, benchmark: float, eua_price_eur: float,
                   year: int, mark_up_pct: float = 0.0) -> dict:
    """
    단위 제품당 CBAM 부담 계산.
    Returns: {'gap', 'phase_in', 'effective_eua', 'unit_cost_eur', 'detail'}
    """
    pi = phase_in(year)
    gap = max(0.0, SEE - benchmark)        # benchmark 이하는 0
    effective_SEE = gap * (1.0 + mark_up_pct / 100.0)   # default 사용 시 mark-up
    unit_cost_eur = effective_SEE * pi * eua_price_eur
    return {
        "gap": gap,
        "phase_in": pi,
        "effective_SEE": effective_SEE,
        "unit_cost_eur": unit_cost_eur,
        "below_benchmark": SEE <= benchmark,
    }


def calc_total_cbam(annual_production_mt: float, eu_export_share_pct: float,
                    SEE: float, benchmark: float, eua_price_eur: float,
                    year: int, mark_up_pct: float = 0.0) -> dict:
    """
    연간 CBAM 총 부담.
    """
    eu_export_t = annual_production_mt * 1e6 * (eu_export_share_pct / 100.0)
    unit = calc_unit_cbam(SEE, benchmark, eua_price_eur, year, mark_up_pct)
    annual_eur = unit["unit_cost_eur"] * eu_export_t
    return {
        **unit,
        "eu_export_t": eu_export_t,
        "annual_cost_eur": annual_eur,
    }


def required_SEE_reduction(SEE: float, benchmark: float) -> dict:
    """
    CBAM=0 만들기 위해 필요한 SEE 감축량.
    """
    if SEE <= benchmark:
        return {"required": 0.0, "required_pct": 0.0, "already_zero": True}
    gap = SEE - benchmark
    return {
        "required": gap,
        "required_pct": gap / SEE * 100.0,
        "already_zero": False,
    }


def ccs_avoided_cbam(SEE: float, benchmark: float, capture_rate: float,
                     eua_price_eur: float, year: int,
                     eu_export_t: float, mark_up_pct: float = 0.0) -> dict:
    """
    CCS 도입 시 CBAM 회피액.
    """
    new_SEE = SEE * (1.0 - capture_rate)
    base = calc_unit_cbam(SEE, benchmark, eua_price_eur, year, mark_up_pct)
    new = calc_unit_cbam(new_SEE, benchmark, eua_price_eur, year, mark_up_pct)
    avoided_unit = base["unit_cost_eur"] - new["unit_cost_eur"]
    avoided_annual = avoided_unit * eu_export_t
    return {
        "new_SEE": new_SEE,
        "base_unit_cost": base["unit_cost_eur"],
        "new_unit_cost": new["unit_cost_eur"],
        "avoided_unit": avoided_unit,
        "avoided_annual_eur": avoided_annual,
        "captured_co2_t": SEE * capture_rate * eu_export_t,
    }


# 감축 수단 라이브러리 (탭 ④ 시뮬레이터용)
ABATEMENT_OPTIONS = [
    {
        "key": "ccs_90",
        "label": "🟦 CCS 90% (자매 CCUS 도구)",
        "applies_to": ["steel_BF_BOF", "cement_clinker", "fertilizer_NH3", "hydrogen_gray", "electricity"],
        "reduction_pct": 90.0,
        "trl": 9,
        "note": "Post-combustion amine 표준. POSCO·시멘트·NH₃ 모두 적용 가능.",
    },
    {
        "key": "ccs_95",
        "label": "🟦 CCS 95% (Calcium Looping)",
        "applies_to": ["cement_clinker", "steel_BF_BOF", "electricity"],
        "reduction_pct": 95.0,
        "trl": 7,
        "note": "Calcium Looping은 시멘트와 자연 통합 (CaO 공유). 자매 도구 참조.",
    },
    {
        "key": "dri_h2_50",
        "label": "🟢 DRI-H₂ 전환 (-50%)",
        "applies_to": ["steel_BF_BOF"],
        "reduction_pct": 50.0,
        "trl": 7,
        "note": "수소 환원철 (H2 Green Steel형). 그린수소 가용성 의존.",
    },
    {
        "key": "eaf_full",
        "label": "🟢 BF→Scrap-EAF 전환 (-78%)",
        "applies_to": ["steel_BF_BOF"],
        "reduction_pct": 78.0,
        "trl": 9,
        "note": "고철 기반 전기로. 현대제철 EAF 모델. 고철 수급 중요.",
    },
    {
        "key": "re100",
        "label": "🟡 RE100 / Grid 청정화 (-15%)",
        "applies_to": ["aluminum_primary", "electricity", "hydrogen_gray", "steel_scrap_EAF"],
        "reduction_pct": 15.0,
        "trl": 9,
        "note": "전력 grid factor 감축. 알루미늄·전기로에 효과 큼. 한국 grid 의존.",
    },
    {
        "key": "beccs",
        "label": "🌱 Bio-CCS (-110%, 음의 배출)",
        "applies_to": ["fertilizer_NH3", "electricity"],
        "reduction_pct": 110.0,
        "trl": 6,
        "note": "바이오매스 + CCS. 음의 배출 가능. 바이오매스 공급 제약.",
    },
    {
        "key": "energy_eff",
        "label": "🟧 에너지 효율 개선 (-10%)",
        "applies_to": ["steel_BF_BOF", "cement_clinker", "fertilizer_NH3", "aluminum_primary"],
        "reduction_pct": 10.0,
        "trl": 9,
        "note": "공정 최적화·열회수. 단기 적용 가능.",
    },
]


# ======================================================================
# 사이드바
# ======================================================================
with st.sidebar:
    st.markdown("### 🚀 빠른 시작 — 시나리오 프리셋")
    preset_keys = list(PRESETS.keys())
    preset_labels = [PRESETS[k]["label"] for k in preset_keys]

    if "preset_select" not in st.session_state:
        st.session_state["preset_select"] = "kr_posco_BF"

    preset_choice = st.selectbox(
        "프리셋 선택",
        options=preset_keys,
        format_func=lambda k: PRESETS[k]["label"],
        key="preset_select",
        on_change=apply_preset,
        help="한국 주요 기업 시나리오를 자동 채움. 선택 후 개별 입력 미세조정 가능.",
    )
    st.caption(f"💡 _{PRESETS[preset_choice]['description']}_")

    st.markdown("---")

    # 통화 표시
    st.markdown("### 💱 표시 통화")
    currency_mode = st.radio(
        "통화 표시 모드",
        ["Both (USD+KRW)", "USD만", "KRW만"],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        key="currency_mode_radio",
    )
    if "USD만" in currency_mode:
        currency_mode_key = "USD"
    elif "KRW만" in currency_mode:
        currency_mode_key = "KRW"
    else:
        currency_mode_key = "Both"
    # 시각적으로 선택 상태를 즉시 인지할 수 있도록 배지 형식
    st.markdown(
        f"<div style='font-size:0.78rem; color:#D4D8DD; margin-top:6px;'>"
        f"현재 표시: <span style='background:#1a2330; color:#4FC3F7; "
        f"padding:2px 8px; border-radius:4px; font-weight:500;'>"
        f"{currency_mode_key}</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # 도메인 입력
    st.markdown("### ⚙️ 입력 파라미터")

    # Sector 선택
    sector_keys = list(LIT.keys())
    if "sector_lit" not in st.session_state:
        st.session_state["sector_lit"] = PRESETS[preset_choice]["sector_lit"]
    sector_lit = st.selectbox(
        "Sector / 공정",
        options=sector_keys,
        format_func=lambda k: f"{LIT[k]['name']}",
        key="sector_lit",
        help="EU CBAM 6개 sector 중 선택. 공정별 default benchmark 자동 적용.",
    )
    sector = LIT[sector_lit]

    # 회사명 (자동·직접 입력)
    company_name = st.text_input(
        "회사명 (선택)",
        value=st.session_state.get("company_name", "Custom Company"),
        key="company_name",
        help="결과·차트에 표시될 라벨",
    )

    # 연 생산량 — sector별 단위 분기
    if sector_lit == "electricity":
        prod_unit_label = "GWh/yr"
        prod_unit_caption = "MWh/yr"
    else:
        prod_unit_label = "Mt/yr (백만톤)"
        prod_unit_caption = "t/yr"
    annual_production_mt = st.number_input(
        f"연 생산량 ({prod_unit_label})",
        min_value=0.001, max_value=500.0,
        value=float(st.session_state.get("annual_production_mt", 75.0)),
        step=0.1, format="%.3f",
        key="annual_production_mt",
        help=("단위: 백만 톤(Mt). 전력 sector의 경우 GWh로 입력 "
              "(내부적으로 1 GWh = 1,000 MWh로 환산)."),
    )
    st.caption(f"≈ {annual_production_mt * 1e6:,.0f} {prod_unit_caption}")

    # EU 수출 비중
    eu_export_share_pct = st.slider(
        "EU 수출 비중 (%)",
        min_value=0.0, max_value=100.0,
        value=float(st.session_state.get("eu_export_share_pct", 5.0)),
        step=0.5, key="eu_export_share_pct",
        help="총 생산량 중 EU 수출분 비율. CBAM 부과 대상 base.",
    )

    # SEE (사용자 자체 데이터 우선)
    see_mode = st.radio(
        "📊 SEE 입력 방식",
        ["EU Default 사용 (mark-up 적용)", "한국 평균 사용", "Verified 자체 데이터"],
        index=2,
        key="see_mode_radio",
        help=("SEE = Specific Embedded Emissions, 단위 제품당 내재 탄소배출량 [tCO₂/t]. "
              "Direct(Scope 1) + Indirect(Scope 2, 일부 sector) 합산. "
              "2024.7 이후 verified 데이터 의무, 미제출 시 default + mark-up. "
              "출처: EU Reg 2023/956 Annex IV, IR 2025/2621"),
    )
    if see_mode == "EU Default 사용 (mark-up 적용)":
        user_SEE = sector["default_SEE"]
        mark_up_pct = 10.0
        st.caption(f"⚠️ Default {user_SEE:.3f} {sector['unit']} + 10% mark-up (2026 기준)")
    elif see_mode == "한국 평균 사용":
        user_SEE = sector["kr_avg_SEE"]
        mark_up_pct = 0.0
        st.caption(f"🇰🇷 한국 평균 {user_SEE:.3f} {sector['unit']} (출처 link 참조)")
    else:
        user_SEE = st.number_input(
            f"Verified SEE ({sector['unit']})",
            min_value=0.0, max_value=20.0,
            value=float(st.session_state.get("user_SEE", sector["kr_avg_SEE"])),
            step=0.01, format="%.3f",
            key="user_SEE",
            help="제3자 검증된 자체 SEE 데이터. CBAM 본격 시행 후 의무.",
        )
        mark_up_pct = 0.0

    st.caption(f"📌 EU benchmark: **{sector['eu_benchmark']:.3f}** {sector['unit']}")

    st.markdown("---")

    # 경제성 가정
    st.markdown("### 💰 경제성 가정")

    # EUA 자동 fetch
    eua_default, eua_date, eua_mode = load_eua_price()
    eua_price = st.slider(
        "EUA 가격 (€/tCO₂)",
        min_value=40.0, max_value=200.0,
        value=float(eua_default), step=1.0,
        help=("EU Emissions Allowance — EU ETS 탄소배출권 가격 [€/tCO₂]. "
              "CBAM 인증서 가격 = EUA 주간 평균. "
              "2025 평균 ~€75, 2026 예상 ~€85, 2030 컨센서스 €126. "
              "출처: ICE / EEX, Sandbag, GMK Center"),
    )
    if eua_mode == "auto":
        st.caption(f"✅ 자동 fetch (`{eua_date}`)")
    elif eua_mode == "fallback":
        st.caption("⚠️ JSON 미존재 — 기본값 €80 사용 중")
    else:
        st.caption(f"📌 GitHub Actions 주1회 갱신 예정 (`data/eua_price.json`)")

    # 환율
    fx_eur_usd = st.number_input(
        "환율 (USD/EUR)",
        min_value=0.8, max_value=1.5,
        value=1.08, step=0.01, format="%.3f",
        help="2025-2026 평균 추정. 본인 회계 환율로 수정 가능.",
    )
    fx_usd_krw = st.number_input(
        "환율 (KRW/USD)",
        min_value=800, max_value=2000,
        value=1400, step=10,
        help="2025-2026 평균 추정. 본인 헤지/회계 환율로 수정 가능.",
    )
    fx_eur_krw = fx_eur_usd * fx_usd_krw   # 파생값

    # 분석 연도
    analysis_year = st.slider(
        "분석 연도 (Phase-in 적용)",
        min_value=2026, max_value=2034, value=2026, step=1,
        help=f"CBAM phase-in factor 자동 적용. 2026: 2.5% → 2034: 100%",
    )
    st.caption(f"📌 {analysis_year}년 phase-in factor: **{phase_in(analysis_year)*100:.1f}%**")

    st.markdown("---")

    # 작성자 카드 (항상 사이드바 하단) — 차분 톤
    st.markdown(
        """
<div style='background:#11161e; border:1px solid #1f2733; border-left:2px solid #4FC3F7;
            border-radius:0 8px 8px 0; padding:12px 14px; margin-top:8px;'>
    <div style='font-size:0.66rem; color:#A8AEB6; text-transform:uppercase;
                letter-spacing:0.08em; font-weight:500;'>Built by</div>
    <div style='font-size:0.95rem; font-weight:500; color:#F0F2F5; margin-top:4px;'>송봉관 / Song BK</div>
    <div style='font-size:0.72rem; color:#D4D8DD; margin:3px 0 8px;'>DAC & CCUS 기술사업화 전문가</div>
    <div style='font-size:0.74rem; line-height:1.8; color:#D4D8DD;'>
        <a href='https://github.com/cafeon90-oss' style='color:#81C784; text-decoration:none;'>↗ GitHub</a> &nbsp;
        <a href='https://www.linkedin.com/in/bongkwan-song-95a0213ba/' style='color:#81C784; text-decoration:none;'>↗ LinkedIn</a><br>
        <a href='https://cdrmaster.tistory.com/' style='color:#81C784; text-decoration:none;'>↗ Blog</a> &nbsp;
        <a href='mailto:cafeon90@gmail.com' style='color:#81C784; text-decoration:none;'>↗ Email</a>
    </div>
    <div style='font-size:0.66rem; color:#7A8089; margin-top:8px; padding-top:8px;
                border-top:1px solid #1f2733;'>
        © 2026 Song BK · MIT License
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ======================================================================
# 메인 화면 — 헤더
# ======================================================================
# 헤더 — 그라디언트 아이콘 + 본문
st.markdown(
    f"""
<div style='display: flex; align-items: center; gap: 14px; margin-bottom: 4px;'>
    <div style='width: 40px; height: 40px; border-radius: 10px;
                background: linear-gradient(135deg, #4FC3F7 0%, #7C4DFF 100%);
                display: flex; align-items: center; justify-content: center;
                font-size: 20px; flex-shrink: 0;'>🌍</div>
    <div style='min-width: 0;'>
        <div style='font-size: 1.55rem; font-weight: 600; letter-spacing: -0.02em;
                    color: #F0F2F5; line-height: 1.2;'>EU CBAM 영향 계산기</div>
        <div style='font-size: 0.8rem; color: #A8AEB6; margin-top: 3px;'>
            한국 기업의 EU 탄소국경조정제도(CBAM) 부담 시뮬레이션 ·
            본격 시행 2026.1.1 → 2034 ·
            자매 도구: <a href='{CCUS_REPO_URL}' style='color:#9b8de8; text-decoration:none;'>🌫️ CCUS 벤치마크 ↗</a>
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# Omnibus 2025 알림 — 컴팩트 한 줄
st.markdown(
    """
<div class='omnibus-banner'>
    <div class='new-badge'>NEW</div>
    <div>Omnibus 2025-10-17 시행 · 50t 면제(H₂·전력 제외) · 인증서 2027.2.1 개시 · 분기 holding 50%</div>
    <a href='https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-legislation-and-guidance_en'>자세히 →</a>
</div>
""",
    unsafe_allow_html=True,
)

# ======================================================================
# 메인 계산 (사이드바 입력 기반)
# ======================================================================
result = calc_total_cbam(
    annual_production_mt=annual_production_mt,
    eu_export_share_pct=eu_export_share_pct,
    SEE=user_SEE,
    benchmark=sector["eu_benchmark"],
    eua_price_eur=eua_price,
    year=analysis_year,
    mark_up_pct=mark_up_pct,
)

# 통화 변환 helper
annual_usd = result["annual_cost_eur"] / fx_eur_usd
annual_krw = result["annual_cost_eur"] * (fx_eur_krw)
unit_usd = result["unit_cost_eur"] / fx_eur_usd

# ======================================================================
# 자동 인사이트 박스
# ======================================================================
gap_pct = (result["gap"] / max(user_SEE, 0.001)) * 100.0
already_zero = result["below_benchmark"]

if already_zero:
    insight_class = "good"
    insight_header = f"✓ {company_name} ({sector['name']})"
    insight_badge = f"<span class='good'>CBAM 0</span>"
    insight_msg = (
        f"SEE <strong>{user_SEE:.3f}</strong> ≤ benchmark "
        f"<strong>{sector['eu_benchmark']:.3f}</strong> {sector['unit']} — "
        f"{analysis_year}년 CBAM 부담 없음. 이 sector·공정은 한국 기업이 "
        f"EU 시장에서 가질 수 있는 가장 강력한 경쟁우위입니다."
    )
elif gap_pct < 20:
    insight_class = "warn"
    insight_header = f"⚠ {company_name}"
    insight_badge = f"<span class='warn'>+{gap_pct:.1f}% 초과</span>"
    insight_msg = (
        f"SEE <strong>{user_SEE:.3f}</strong> vs benchmark "
        f"<strong>{sector['eu_benchmark']:.3f}</strong>. "
        f"{analysis_year}년 연간 부담 <span class='warn'>{fmt_eur(result['annual_cost_eur'])}</span> "
        f"(≈ {fmt_money(annual_usd, fx_usd_krw, currency_mode_key)}). "
        f"<span class='warn'>에너지 효율 개선</span> · <span class='warn'>부분 CCS</span>로도 "
        f"benchmark 이하 달성 가능."
    )
else:
    insight_class = "bad"
    insight_header = f"⚠ {company_name}"
    insight_badge = f"<span class='bad'>+{gap_pct:.1f}% 초과</span>"
    insight_msg = (
        f"SEE <strong>{user_SEE:.3f}</strong> vs benchmark "
        f"<strong>{sector['eu_benchmark']:.3f}</strong>. "
        f"{analysis_year}년 연간 부담 <span class='bad'>{fmt_eur(result['annual_cost_eur'])}</span> "
        f"(≈ {fmt_money(annual_usd, fx_usd_krw, currency_mode_key)}). "
        f"<span class='warn'>CCS 90%</span> 또는 <span class='warn'>공정 전환(DRI-H₂/EAF)</span> 권장 → "
        f"탭 <strong>④ 감축 시뮬레이터</strong>에서 회피액 정밀 계산."
    )

st.markdown(
    f"""
<div class='insight-box {insight_class}'>
    <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 6px;'>
        <div style='font-weight: 500; font-size: 0.95rem; color: #F0F2F5;'>{insight_header}</div>
        <div style='margin-left: auto; background: #1a2028; font-size: 0.7rem; padding: 2px 8px; border-radius: 4px;'>{insight_badge}</div>
    </div>
    <div>{insight_msg}</div>
</div>
""",
    unsafe_allow_html=True,
)

# ======================================================================
# 핵심 KPI 카드 (4대)
# ======================================================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        f"연간 CBAM ({analysis_year})",
        fmt_money(annual_usd, fx_usd_krw, currency_mode_key),
        delta=f"€{result['annual_cost_eur']/1e6:,.2f}M",
        delta_color="off",
    )

with col2:
    st.metric(
        "단위 제품당 CBAM",
        fmt_money(unit_usd, fx_usd_krw, currency_mode_key, per_t=True),
        delta=f"€{result['unit_cost_eur']:.2f}/t",
        delta_color="off",
    )

with col3:
    # EU 수출가 인상률 추정 — 단위 가격 가정 시 비교
    ref_unit_price = {
        "steel_BF_BOF": 700, "steel_DRI_EAF": 800, "steel_scrap_EAF": 650,
        "cement_clinker": 80, "aluminum_primary": 2400,
        "fertilizer_NH3": 500, "hydrogen_gray": 2500, "hydrogen_blue": 4000,
        "electricity": 100,
    }.get(sector_lit, 700)
    cbam_unit_usd = result["unit_cost_eur"] / fx_eur_usd
    price_uplift_pct = (cbam_unit_usd / ref_unit_price) * 100.0
    st.metric(
        "EU 수출가 인상률",
        f"{price_uplift_pct:+.2f}%",
        delta=f"≈ ${cbam_unit_usd:.1f}/t / ${ref_unit_price} base",
        delta_color="off",
        help=f"가정: {sector['name']} 평균 EU 수출가 ${ref_unit_price}/t",
    )

with col4:
    # CCS 90% 도입 시 회피액
    avoided = ccs_avoided_cbam(
        SEE=user_SEE, benchmark=sector["eu_benchmark"],
        capture_rate=0.90, eua_price_eur=eua_price,
        year=analysis_year, eu_export_t=result["eu_export_t"],
        mark_up_pct=mark_up_pct,
    )
    avoided_usd = avoided["avoided_annual_eur"] / fx_eur_usd
    st.metric(
        "CCS 90% 회피 가능",
        fmt_money(avoided_usd, fx_usd_krw, currency_mode_key),
        delta=f"€{avoided['avoided_annual_eur']/1e6:,.2f}M/yr",
        delta_color="off",
        help="자매 CCUS 도구로 deep-dive (탭 ⑤ 참조)",
    )

# ======================================================================
# KPI 정의 expander
# ======================================================================
with st.expander("📖 KPI 정의 보기 (클릭)", expanded=False):
    st.markdown(
        f"""
**연간 CBAM 부담** = (SEE − Free benchmark) × Phase-in × EUA × EU 수출량
- 현재 SEE: **{user_SEE:.3f}** {sector['unit']}
- EU benchmark: **{sector['eu_benchmark']:.3f}** {sector['unit']}
- Gap: **{result['gap']:.3f}** ({gap_pct:.1f}%)
- {analysis_year}년 phase-in: **{result['phase_in']*100:.1f}%**
- EUA: **€{eua_price:.0f}/tCO₂**
- EU 수출량: **{result['eu_export_t']:,.0f} t/yr**

**단위 제품당 CBAM** = unit cost (€/t) × FX
**EU 수출가 인상률** = CBAM 단가 / 평균 수출가 × 100%
**CCS 회피액** = (SEE − SEE×(1−η)) × phase-in × EUA × 수출량, η=90%

📚 출처:
- {ref_link("EU_REG_2023_956", "EU Regulation 2023/956")} — CBAM 본법
- {ref_link("EU_IR_2025_2621", "EU IR 2025/2621")} — Default values + benchmark
- {ref_link("Climat_be_PhaseIn", "Phase-in factor table")}
- {ref_link("EUROMETAL_Bench", "Steel benchmark 1.370/0.481/0.072")}
"""
    )

# ======================================================================
# 탭 9개 구성
# ======================================================================
tabs = st.tabs(
    [
        "① 종합 영향",
        "② Sector별 분석",
        "③ 한국 기업 영향",
        "④ 감축 시뮬레이터",
        "⑤ CCUS 연계",
        "⑥ 시간 흐름",
        "⑦ Custom 입력",
        "⑧ 방법론",
        "⑨ 참고문헌",
    ]
)


# ────────────── 탭 ① 종합 영향 ──────────────
with tabs[0]:
    st.subheader("① 종합 영향 — 4대 KPI 한눈에")

    # 4대 KPI 2x2 비교 (모든 sector × user 입력 시나리오)
    rows = []
    for k, v in LIT.items():
        unit_calc = calc_unit_cbam(
            SEE=v["kr_avg_SEE"], benchmark=v["eu_benchmark"],
            eua_price_eur=eua_price, year=analysis_year, mark_up_pct=0,
        )
        rows.append({
            "Sector": v["name"],
            "Short": SHORT_NAMES[k],
            "SEE (kr)": v["kr_avg_SEE"],
            "Benchmark": v["eu_benchmark"],
            "Gap": unit_calc["gap"],
            "Unit cost (€/t)": unit_calc["unit_cost_eur"],
            "Unit cost (USD/t)": unit_calc["unit_cost_eur"] / fx_eur_usd,
            "color": v["color"],
        })
    df_overview = pd.DataFrame(rows).sort_values("Unit cost (€/t)", ascending=False)

    # 2x2 비교 차트
    c1, c2 = st.columns(2)

    with c1:
        # 차트 1: SEE vs Benchmark gap
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            y=df_overview["Short"], x=df_overview["SEE (kr)"],
            name="한국 평균 SEE", orientation="h",
            marker_color="#E57373",
        ))
        fig1.add_trace(go.Bar(
            y=df_overview["Short"], x=df_overview["Benchmark"],
            name="EU Benchmark", orientation="h",
            marker_color="#81C784",
        ))
        fig1.update_layout(
            title=f"한국 평균 SEE vs EU Benchmark",
            barmode="group", template="plotly_dark",
            height=420, margin=dict(l=10, r=10, t=50, b=30),
            xaxis_title="tCO₂/단위제품",
            paper_bgcolor=C_BG, plot_bgcolor=C_BG,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        lock_static(fig1)
        st.plotly_chart(fig1, use_container_width=True, config=PLOTLY_CONFIG)

    with c2:
        # 차트 2: 단위당 CBAM cost (정렬된 df_overview의 색상 사용 — 버그 수정)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            y=df_overview["Short"], x=df_overview["Unit cost (€/t)"],
            orientation="h",
            marker_color=df_overview["color"].tolist(),
            text=[f"€{v:.1f}" for v in df_overview["Unit cost (€/t)"]],
            textposition="outside",
        ))
        fig2.update_layout(
            title=f"{analysis_year}년 단위 CBAM cost (€/t)",
            template="plotly_dark", height=420,
            margin=dict(l=10, r=40, t=50, b=30),
            xaxis_title="€/단위제품",
            paper_bgcolor=C_BG, plot_bgcolor=C_BG,
            showlegend=False,
        )
        lock_static(fig2)
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

    # 데이터 테이블
    st.markdown("##### 📊 6개 sector 상세 비교 (한국 평균 기준)")
    df_show = df_overview[["Sector", "SEE (kr)", "Benchmark", "Gap", "Unit cost (€/t)", "Unit cost (USD/t)"]].copy()
    df_show["SEE (kr)"] = df_show["SEE (kr)"].map(lambda x: f"{x:.3f}")
    df_show["Benchmark"] = df_show["Benchmark"].map(lambda x: f"{x:.3f}")
    df_show["Gap"] = df_show["Gap"].map(lambda x: f"{x:.3f}")
    df_show["Unit cost (€/t)"] = df_show["Unit cost (€/t)"].map(lambda x: f"€{x:.2f}")
    df_show["Unit cost (USD/t)"] = df_show["Unit cost (USD/t)"].map(lambda x: f"${x:.2f}")
    st.dataframe(df_show, hide_index=True, use_container_width=True)


# ────────────── 탭 ② Sector별 분석 ──────────────
with tabs[1]:
    st.subheader(f"② Sector별 분석 — {sector['name']}")

    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        st.metric("Default SEE (CBAM)", f"{sector['default_SEE']:.3f}", help="EU IR 2025/2621 Annex I")
    with col_b:
        st.metric("한국 평균 SEE", f"{sector['kr_avg_SEE']:.3f}", help="한국 산업 평균")
    with col_c:
        st.metric("EU Free benchmark", f"{sector['eu_benchmark']:.3f}", help="EU 무상할당 기준")

    st.markdown("---")
    st.markdown(f"**공정**: {sector['process']}")
    st.markdown(f"**제품**: {sector['product']} · 단위: {sector['unit']}")
    st.markdown(f"**한국 EU 수출액 (2021)**: ${sector['kr_eu_export_usd_2021']/1e9:.2f}B")

    # Gap 시각화
    fig_gap = go.Figure()
    categories = ["EU Best (free)", "EU Benchmark", "Default (mark-up)", "한국 평균", "Gray/old proc"]
    values = [
        sector["eu_benchmark"] * 0.5,
        sector["eu_benchmark"],
        sector["default_SEE"] * 1.10,
        sector["kr_avg_SEE"],
        sector["default_SEE"] * 1.30,
    ]
    colors = [C_GOOD, C_PRIMARY, C_WARN, C_BAD, "#7E57C2"]
    fig_gap.add_trace(go.Bar(
        x=categories, y=values, marker_color=colors,
        text=[f"{v:.2f}" for v in values], textposition="outside",
    ))
    fig_gap.add_hline(
        y=sector["eu_benchmark"], line_dash="dash", line_color="#FFEB3B",
        annotation_text=f"Free benchmark {sector['eu_benchmark']:.2f}",
    )
    fig_gap.update_layout(
        title=f"{sector['name']} — SEE 스펙트럼",
        template="plotly_dark", height=380,
        yaxis_title=sector["unit"],
        paper_bgcolor=C_BG, plot_bgcolor=C_BG, showlegend=False,
        margin=dict(l=10, r=10, t=50, b=30),
    )
    lock_static(fig_gap)
    st.plotly_chart(fig_gap, use_container_width=True, config=PLOTLY_CONFIG)

    # 출처 link
    st.markdown("📚 **이 sector 출처:**")
    for ref_id in sector.get("refs", []):
        if ref_id in REFS:
            r = REFS[ref_id]
            st.markdown(f"- {ref_link(ref_id, r['cite'][:80] + '...')}")


# ────────────── 탭 ③ 한국 기업 영향 ──────────────
with tabs[2]:
    st.subheader("③ 한국 주요 기업 — CBAM 부담 비교")
    st.caption("프리셋 기반 시뮬레이션. 사이드바에서 입력값 조정 가능.")

    company_rows = []
    for pkey, pdata in PRESETS.items():
        if pkey == "custom":
            continue
        slit = pdata["sector_lit"]
        s = LIT[slit]
        settings = pdata["settings"]
        prod_mt = settings.get("annual_production_mt", 1.0)
        share = settings.get("eu_export_share_pct", 5.0)
        see_use = settings.get("user_SEE", s["kr_avg_SEE"])
        cname = settings.get("company_name", pdata["label"])

        r = calc_total_cbam(
            annual_production_mt=prod_mt,
            eu_export_share_pct=share,
            SEE=see_use, benchmark=s["eu_benchmark"],
            eua_price_eur=eua_price, year=analysis_year, mark_up_pct=0,
        )
        company_rows.append({
            "Company": cname,
            "Sector": s["name"],
            "Production (Mt/yr)": prod_mt,
            "EU export (%)": share,
            "SEE": see_use,
            "Benchmark": s["eu_benchmark"],
            "Annual CBAM (€M)": r["annual_cost_eur"] / 1e6,
            "Annual CBAM (USD M)": r["annual_cost_eur"] / fx_eur_usd / 1e6,
            "Annual CBAM (억원)": r["annual_cost_eur"] * fx_eur_krw / 1e8,
        })

    df_co = pd.DataFrame(company_rows).sort_values("Annual CBAM (€M)", ascending=False)

    # Bar chart
    fig_co = px.bar(
        df_co, x="Company", y="Annual CBAM (€M)",
        text=df_co["Annual CBAM (€M)"].map(lambda x: f"€{x:.1f}M"),
        color="Sector", color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_co.update_layout(
        title=f"{analysis_year}년 한국 주요 기업 CBAM 부담",
        template="plotly_dark", height=460,
        paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        xaxis_tickangle=-25,
        margin=dict(l=10, r=10, t=50, b=80),
    )
    fig_co.update_traces(textposition="outside")
    lock_static(fig_co)
    st.plotly_chart(fig_co, use_container_width=True, config=PLOTLY_CONFIG)

    # 테이블
    df_co_show = df_co.copy()
    df_co_show["Production (Mt/yr)"] = df_co_show["Production (Mt/yr)"].map(lambda x: f"{x:.2f}")
    df_co_show["EU export (%)"] = df_co_show["EU export (%)"].map(lambda x: f"{x:.1f}%")
    df_co_show["SEE"] = df_co_show["SEE"].map(lambda x: f"{x:.3f}")
    df_co_show["Benchmark"] = df_co_show["Benchmark"].map(lambda x: f"{x:.3f}")
    df_co_show["Annual CBAM (€M)"] = df_co_show["Annual CBAM (€M)"].map(lambda x: f"€{x:.2f}M")
    df_co_show["Annual CBAM (USD M)"] = df_co_show["Annual CBAM (USD M)"].map(lambda x: f"${x:.2f}M")
    df_co_show["Annual CBAM (억원)"] = df_co_show["Annual CBAM (억원)"].map(lambda x: f"{x:,.1f}억원")
    st.dataframe(df_co_show, hide_index=True, use_container_width=True)

    # 2034 완전시행 대비 증가배수 안내 (현재 연도가 이미 2034면 메시지 숨김)
    pi_now = phase_in(analysis_year)
    if pi_now < 1.0:
        ratio_2034 = 1.0 / pi_now
        ratio_msg = f"> 2034 완전 시행 시 **약 {ratio_2034:,.1f}배** 부담 증가 예상.\n"
    else:
        ratio_msg = "> 이미 2034 완전 시행 (phase-in 100%) 분석 중입니다.\n"
    st.markdown(
        f"""
> 📌 위 표는 **{analysis_year}년 phase-in {pi_now*100:.1f}%** 적용.
{ratio_msg}> 출처: {ref_link("KOTRA_CBAM")}, {ref_link("KCCI_SGI_22")}, {ref_link("InfluenceMap_KR_Steel")}
"""
    )


# ────────────── 탭 ④ 감축 시뮬레이터 ──────────────
with tabs[3]:
    st.subheader(f"④ 탄소감축 시뮬레이터 — {company_name}")

    # 4-A: 역산
    st.markdown("##### 🎯 4-A. CBAM 부담 0으로 만들려면?")

    req = required_SEE_reduction(user_SEE, sector["eu_benchmark"])
    if req["already_zero"]:
        st.success(
            f"✅ 현재 SEE {user_SEE:.3f} ≤ benchmark {sector['eu_benchmark']:.3f} — "
            f"**CBAM 0** 이미 달성 중입니다."
        )
    else:
        st.markdown(
            f"""
- 현재 SEE: <strong>{user_SEE:.3f}</strong> {sector['unit']}
- EU benchmark: <strong>{sector['eu_benchmark']:.3f}</strong> {sector['unit']}
- 필요 감축량: <strong style='color:{C_BAD}'>{req['required']:.3f}</strong>
  (= <strong style='color:{C_BAD}'>−{req['required_pct']:.1f}%</strong>)
""",
            unsafe_allow_html=True,
        )

    # 4-B: 감축 수단 비교
    st.markdown("##### 🔧 4-B. 감축 수단별 효과")

    rows = []
    for opt in ABATEMENT_OPTIONS:
        applies = sector_lit in opt["applies_to"]
        new_SEE = max(0.0, user_SEE * (1.0 - opt["reduction_pct"] / 100.0))
        achieves = new_SEE <= sector["eu_benchmark"]
        rows.append({
            "수단": opt["label"],
            "감축율": f"-{opt['reduction_pct']:.0f}%",
            "잔존 SEE": f"{new_SEE:.3f}",
            "CBAM 0 달성": "✅" if achieves else "❌",
            "Sector 적합": "✅" if applies else "△",
            "TRL": opt["trl"],
            "비고": opt["note"],
        })
    df_abate = pd.DataFrame(rows)
    st.dataframe(df_abate, hide_index=True, use_container_width=True)

    # 4-C: CCS BEP (자매 CCUS COCA × 회피액)
    st.markdown("##### 💰 4-C. CCS 도입 시 BEP 분석")

    ccus_data, ccus_mode = load_ccus_metrics()
    fit_techs = ccus_data["sector_fit"].get(sector["ccus_sector"], [])
    if not fit_techs:
        st.info(f"이 sector ({sector['ccus_sector']})에 대한 CCUS 적합 기술이 정의되지 않았습니다.")
    else:
        bep_rows = []
        for tk in fit_techs:
            tdata = ccus_data["technologies"].get(tk)
            if not tdata:
                continue
            cap_rate = tdata["capture_rate"]
            avoided = ccs_avoided_cbam(
                SEE=user_SEE, benchmark=sector["eu_benchmark"],
                capture_rate=cap_rate, eua_price_eur=eua_price,
                year=analysis_year, eu_export_t=result["eu_export_t"],
                mark_up_pct=mark_up_pct,
            )
            ccs_cost_usd = tdata["COCA_USD_per_tCO2"] * avoided["captured_co2_t"]
            avoided_usd = avoided["avoided_annual_eur"] / fx_eur_usd
            net_usd = avoided_usd - ccs_cost_usd
            bep_rows.append({
                "CCUS 기술": tdata["display_name"],
                "Capture η": f"{cap_rate*100:.0f}%",
                "COCA (USD/t)": f"${tdata['COCA_USD_per_tCO2']}",
                "포집 CO₂ (t/yr)": f"{avoided['captured_co2_t']:,.0f}",
                "CCS 비용 (USD M/yr)": f"${ccs_cost_usd/1e6:,.2f}",
                "CBAM 회피 (USD M/yr)": f"${avoided_usd/1e6:,.2f}",
                "순익 (USD M/yr)": f"${net_usd/1e6:+,.2f}",
                "TRL": tdata["TRL"],
            })
        df_bep = pd.DataFrame(bep_rows)
        st.dataframe(df_bep, hide_index=True, use_container_width=True)

        st.markdown(
            f"""
> 💡 **해석**: 위 표는 자매 CCUS 도구의 COCA 값을 mirror 하여 자동 계산.
> 순익이 양수 → CCS 도입이 CBAM 부담보다 저렴.
> 자세한 기술 비교는 [{ref_link("EU_CBAM_TaxCustoms", "자매 CCUS 벤치마크 도구")}]({CCUS_REPO_URL}) 참조.
> 데이터 모드: `{ccus_mode}` (Phase 2에서 live fetch 활성화 예정)
"""
        )


# ────────────── 탭 ⑤ CCUS 연계 (stub) ──────────────
with tabs[4]:
    st.subheader("⑤ CCUS 연계 — 자매 도구")

    ccus_data, ccus_mode = load_ccus_metrics()

    st.markdown(
        f"""
<div class='sister-card'>
<h4 style='margin:0 0 8px 0;'>🌫️ 자매 도구: CCUS 기술 벤치마크</h4>
한국·미국·EU의 5+1개 CCUS 흡수제·공정 기술의 COCA·SPECCA·CAPEX 비교 도구.<br>
이 CBAM 계산기와 데이터 연계되어 sector별 적합 기술 자동 추천 + BEP 분석 제공.<br><br>
<strong>🔗 <a href='{CCUS_REPO_URL}' target='_blank'>{CCUS_REPO_URL}</a></strong><br><br>
<small>📌 현재 Phase 1: Stub mode (placeholder 값 사용 중) ·
Phase 2 예정: <code>data/ccus_metrics.json</code> live fetch</small>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(f"##### 🔌 현재 sector ({sector['name']}) 에 적합한 CCUS 기술")

    fit_techs = ccus_data["sector_fit"].get(sector["ccus_sector"], [])
    if not fit_techs:
        st.info(f"이 sector ({sector['ccus_sector']})는 CCUS sector_fit 매핑에 정의되지 않았습니다.")
    else:
        rec_rows = []
        for tk in fit_techs:
            tdata = ccus_data["technologies"].get(tk)
            if not tdata:
                continue
            rec_rows.append({
                "기술": tdata["display_name"],
                "Short": tdata["short_name"],
                "COCA (USD/t)": f"${tdata['COCA_USD_per_tCO2']}",
                "CAPEX (USD/tpy)": f"${tdata['CAPEX_USD_per_tpy']}",
                "OPEX (USD/t)": f"${tdata['OPEX_USD_per_tCO2']}",
                "Capture η": f"{tdata['capture_rate']*100:.0f}%",
                "TRL": tdata["TRL"],
            })
        df_rec = pd.DataFrame(rec_rows)
        st.dataframe(df_rec, hide_index=True, use_container_width=True)

    st.markdown("---")
    st.markdown(
        f"""
##### 🚧 Phase 2 로드맵 (CCUS 연계)
- [ ] 자매 도구 repo에 `data/ccus_metrics.json` 추가 (단일 진실 소스)
- [ ] `load_ccus_metrics()` 함수에서 GitHub raw URL fetch 활성화
- [ ] CBAM 계산기에 "CCUS 도구로 deep-dive" 버튼 → 자매 도구 link
- [ ] 양 도구의 데이터 검증 (POSCO·시멘트 retrofit cost cross-check)
- [ ] 한국 sector × CCUS 기술 매트릭스 시각화

데이터 모드: `{ccus_mode}` · 마지막 업데이트: `{ccus_data.get('last_updated', 'n/a')}`
"""
    )


# ────────────── 탭 ⑥ 시간 흐름 (2023~2034) ──────────────
with tabs[5]:
    st.subheader("⑥ 시간 흐름 — Phase-in 2023~2034")

    years = list(range(2023, 2035))
    factors = [phase_in(y) * 100 for y in years]
    free_alloc = [100.0 - f for f in factors]

    fig_time = go.Figure()
    fig_time.add_trace(go.Bar(
        x=years, y=factors, name="CBAM 부과율 (%)",
        marker_color=C_BAD, text=[f"{f:.1f}%" for f in factors], textposition="outside",
    ))
    fig_time.add_trace(go.Scatter(
        x=years, y=free_alloc, name="Free allocation (%)",
        mode="lines+markers", line=dict(color=C_GOOD, width=3),
        yaxis="y2",
    ))
    fig_time.update_layout(
        title="EU CBAM Phase-in vs Free Allowance Phase-out",
        template="plotly_dark", height=460,
        paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        yaxis=dict(title="CBAM 부과율 (%)", range=[0, 110]),
        yaxis2=dict(title="Free allocation (%)", overlaying="y", side="right", range=[0, 110]),
        legend=dict(orientation="h", yanchor="bottom", y=-0.18),
        margin=dict(l=10, r=10, t=50, b=60),
    )
    fig_time.add_vrect(x0=2022.5, x1=2025.5, fillcolor=C_MUTED, opacity=0.15,
                      annotation_text="전이기간 (보고만)", annotation_position="top left")
    fig_time.add_vline(x=2026, line_dash="dash", line_color=C_HIGH,
                      annotation_text="본격 시행 시작")
    lock_static(fig_time)
    st.plotly_chart(fig_time, use_container_width=True, config=PLOTLY_CONFIG)

    # 회사별 연도별 부담 trajectory
    st.markdown(f"##### 📈 {company_name} — 연도별 CBAM 부담 추이")
    fig_traj = go.Figure()
    yrs = list(range(2026, 2035))
    annual_costs_eur = []
    for y in yrs:
        r = calc_total_cbam(
            annual_production_mt=annual_production_mt,
            eu_export_share_pct=eu_export_share_pct,
            SEE=user_SEE, benchmark=sector["eu_benchmark"],
            eua_price_eur=eua_price, year=y, mark_up_pct=mark_up_pct,
        )
        annual_costs_eur.append(r["annual_cost_eur"] / 1e6)
    fig_traj.add_trace(go.Bar(
        x=yrs, y=annual_costs_eur,
        marker_color=[C_GOOD if y < 2030 else C_WARN if y < 2033 else C_BAD for y in yrs],
        text=[f"€{c:.1f}M" for c in annual_costs_eur], textposition="outside",
    ))
    fig_traj.update_layout(
        title=f"{company_name} — 연간 CBAM 부담 (EUR M)",
        template="plotly_dark", height=420,
        paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        yaxis_title="€M / 년",
        margin=dict(l=10, r=10, t=50, b=30), showlegend=False,
    )
    lock_static(fig_traj)
    st.plotly_chart(fig_traj, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown(
        f"""
> 📌 **변곡점 2030**: phase-in 22.5% → 48.5% (2배 이상 급증). 한국 기업의 본격 충격 시점.
> 출처: {ref_link("Climat_be_PhaseIn")}, {ref_link("ICAP_CBAM_2026")}, {ref_link("Coolset_CBAM")}
"""
    )


# ────────────── 탭 ⑦ Custom 입력 ──────────────
with tabs[6]:
    st.subheader("⑦ Custom 입력 — 직접 시나리오 분석")
    st.caption("사이드바 입력값을 그대로 사용합니다. 추가로 multi-year 비교가 가능합니다.")

    st.markdown("##### 🔧 Multi-year 비교 (현재 sector·SEE 기준)")
    custom_years = st.multiselect(
        "비교할 연도 선택", options=list(range(2026, 2035)),
        default=[2026, 2030, 2034],
    )
    if custom_years:
        cust_rows = []
        for y in custom_years:
            r = calc_total_cbam(
                annual_production_mt=annual_production_mt,
                eu_export_share_pct=eu_export_share_pct,
                SEE=user_SEE, benchmark=sector["eu_benchmark"],
                eua_price_eur=eua_price, year=y, mark_up_pct=mark_up_pct,
            )
            cust_rows.append({
                "Year": y,
                "Phase-in": f"{phase_in(y)*100:.1f}%",
                "Unit cost (€/t)": f"€{r['unit_cost_eur']:.2f}",
                "Annual (€M)": f"€{r['annual_cost_eur']/1e6:.2f}M",
                "Annual (USD M)": f"${r['annual_cost_eur']/fx_eur_usd/1e6:.2f}M",
                "Annual (억원)": f"{r['annual_cost_eur']*fx_eur_krw/1e8:.1f}억원",
            })
        st.dataframe(pd.DataFrame(cust_rows), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.markdown("##### ⚡ EUA 가격 민감도")
    eua_range = st.slider(
        "EUA 가격 범위 (€/tCO₂)",
        min_value=40, max_value=200, value=(60, 130), step=5,
    )
    eua_grid = list(range(eua_range[0], eua_range[1] + 1, 10))
    sens_rows = []
    for ep in eua_grid:
        r = calc_total_cbam(
            annual_production_mt=annual_production_mt,
            eu_export_share_pct=eu_export_share_pct,
            SEE=user_SEE, benchmark=sector["eu_benchmark"],
            eua_price_eur=ep, year=analysis_year, mark_up_pct=mark_up_pct,
        )
        sens_rows.append({"EUA (€/t)": ep, "Annual (€M)": r["annual_cost_eur"] / 1e6})
    df_sens = pd.DataFrame(sens_rows)
    fig_sens = px.line(
        df_sens, x="EUA (€/t)", y="Annual (€M)", markers=True,
        title=f"{company_name} — EUA 가격에 따른 연간 CBAM 부담 ({analysis_year})",
    )
    fig_sens.update_traces(line_color=C_PRIMARY, marker=dict(size=8))
    fig_sens.update_layout(
        template="plotly_dark", height=400,
        paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        margin=dict(l=10, r=10, t=50, b=30),
    )
    lock_static(fig_sens)
    st.plotly_chart(fig_sens, use_container_width=True, config=PLOTLY_CONFIG)


# ────────────── 탭 ⑧ 방법론 ──────────────
with tabs[7]:
    st.subheader("⑧ 방법론 — 계산식과 가정")

    st.markdown(
        f"""
##### 🧮 핵심 수식

```
[Step 1] Gap 계산
  Gap [tCO₂/t] = max(0, SEE - EU_benchmark)

[Step 2] 단위 제품당 CBAM 부담
  Unit_cost [€/t] = Gap × (1 + markup) × Phase_in × EUA

[Step 3] 연간 부담
  Annual [€/yr] = Unit_cost × Annual_Production × EU_share

[Step 4] 통화 변환
  USD = € / FX(EUR/USD)
  KRW = USD × FX(KRW/USD)
```

##### 📐 핵심 가정

| 항목 | 값 | 출처 |
|---|---|---|
| Phase-in factor (2026) | 2.5% | {ref_link("Climat_be_PhaseIn")} |
| Phase-in factor (2030) | 48.5% | 동일 |
| Phase-in factor (2034) | 100% | 동일 |
| EUA 가격 (default) | €80/tCO₂ | {ref_link("EEX_EUA")} (2025-2026 평균) |
| Mark-up (default 사용 시) | 10% (2026~2027) | {ref_link("EU_IR_2025_2621")} |
| Steel BF-BOF benchmark | 1.370 | {ref_link("EUROMETAL_Bench")} |
| Steel DRI-EAF benchmark | 0.481 | 동일 |
| Steel Scrap-EAF benchmark | 0.072 | 동일 |
| Cement clinker benchmark | 0.693 | 동일 |
| 한국 grid factor | 0.443 tCO₂/MWh | {ref_link("KEPCO_2024")} |
| EU grid factor | 0.230 tCO₂/MWh | {ref_link("IEA_Elec_Maps_2024")} |

##### ⚠️ 한계와 가정

1. **SEE는 verified 우선**: 2024.7 이후 default 사용 시 mark-up. 본 도구는 사용자 입력을 우선.
2. **Indirect emissions**: 시멘트·비료만 indirect 포함 (CBAM 규정). 본 도구는 단순화하여 sector별 평균 적용.
3. **EUA 가격 변동성**: 매주 평균 변동. 본 도구는 사용자 슬라이더 + 자동 fetch 옵션 제공.
4. **Free benchmark 갱신**: 2025년 IR 2025/2621 기준. 향후 EU 갱신 시 LIT 업데이트 필요.
5. **Mark-up 진화**: 철강·시멘트·알루미늄 2026 10% → 2028 30%. 본 도구는 현재 10% 고정 (선택형으로 향후 확장).
6. **K-ETS 차감**: 한국 K-ETS 보고배출량 차감 가능성은 본 도구에서 미반영. {ref_link("ME_K_ETS")} 참조.

##### 🔄 자동 데이터 갱신

- **EUA 가격**: GitHub Actions cron (주 1회 월요일) → `data/eua_price.json` commit. Streamlit `@st.cache_data(ttl=86400)` 사용.
- **POSCO SEE**: 정적 + `last_verified_date` + 출처 link. POSCO ESG 보고서 갱신 시 (연 1회) 수동 업데이트.
- **CCUS 데이터**: Phase 2에서 자매 도구 `ccus_metrics.json` raw fetch 예정.

##### 🆕 2025년 CBAM Omnibus 변경사항 (반영됨)

| 항목 | 변경 전 | 변경 후 (Omnibus 2025-10-17) |
|---|---|---|
| 소액 면제 | 재무가치 €150 | **연 50톤** (mass-based, H₂·전력 제외) |
| 인증서 판매 개시 | 2026-01-01 | **2027-02-01** (2026 분 소급) |
| 연간 declaration 마감 | 매년 5-31 | **매년 9-30** |
| 분기말 holding | 80% | **50%** |
| Authorized declarant 권한 | 사전 등록 필요 | 2026-03-31까지 신청 시 grace period |
| 2026 인증서 가격 산정 | (미정) | **분기 평균 EUA**, 2027부터 주간 평균 |

출처: {ref_link("EU_OMNIBUS_2025")}, {ref_link("MayerBrown_Omnibus")}, {ref_link("ReedSmith_CBAM")}

##### 🔮 향후 확장 로드맵 (2025-12-17 EU 발표)

- **8 Implementing Acts + 1 Delegated Act** (2025-12-17 채택) — verifier 인증, registry 운영, 인증서 가격 산정 등
- **Downstream products 확장** (목표 2028) — 가공된 철강·알루미늄 제품 (예: 부품, 가공재) 포함 예정. 본 도구는 Phase 1 sector(원자재)만 다룸.
- **추가 sector** (2030+) — 화학·플라스틱·polymers 검토 중

출처: {ref_link("EU_PACKAGE_2025_12")}
"""
    )


# ────────────── 탭 ⑨ 참고문헌 ──────────────
with tabs[8]:
    st.subheader("⑨ 참고문헌 — 출처 카탈로그")

    cat_filter = st.multiselect(
        "카테고리 필터",
        options=sorted(list(set(r["cat"] for r in REFS.values()))),
        default=sorted(list(set(r["cat"] for r in REFS.values()))),
    )

    for ref_id, r in REFS.items():
        if r["cat"] not in cat_filter:
            continue
        cat_emoji = {
            "regulation": "⚖️", "report": "📄", "paper": "📚",
            "methodology": "🔬", "market": "💹",
        }.get(r["cat"], "📌")
        url_str = f" — [link]({r['url']})" if r.get("url") else ""
        date_str = (f"<span style='color:#FFB74D; font-size:0.82em;'>📅 {r['date']}</span>  \n"
                    if r.get("date") else "")
        st.markdown(
            f"**{cat_emoji} `{ref_id}`** _{r['cat']}_  \n"
            f"{date_str}"
            f"{r['cite']}{url_str}  \n"
            f"<span style='color:#8b95a7; font-size:0.85em;'>📍 사용처: {r['used_for']}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("---")


# ======================================================================
# 풀 footer
# ======================================================================
st.markdown(
    f"""
<div class='footer-card'>
    <div style='display: flex; align-items: center; gap: 12px; margin-bottom: 10px;'>
        <div style='width: 36px; height: 36px; border-radius: 9px;
                    background: linear-gradient(135deg, #4FC3F7 0%, #7C4DFF 100%);
                    display: flex; align-items: center; justify-content: center;
                    font-size: 18px; flex-shrink: 0;'>🌍</div>
        <div>
            <div style='font-size: 1.0rem; font-weight: 500; color:#F0F2F5; line-height: 1.2;'>EU CBAM 영향 계산기</div>
            <div style='font-size: 0.78rem; color:#A8AEB6; margin-top: 2px;'>Built by 송봉관 / Song BK · DAC & CCUS 기술사업화 전문가</div>
        </div>
    </div>
    <div style='font-size:0.84rem; color:#D4D8DD; margin: 8px 0 12px 0;'>
        자매 도구:
        <a href='{CCUS_REPO_URL}' style='color:#9b8de8; text-decoration:none;'>🌫️ CCUS 벤치마크 ↗</a>
    </div>
    <div style='display: flex; flex-wrap: wrap; gap: 14px; font-size:0.84rem; margin-bottom: 12px;'>
        <a href='https://github.com/cafeon90-oss' style='color:#81C784; text-decoration:none;'>↗ GitHub</a>
        <a href='https://www.linkedin.com/in/bongkwan-song-95a0213ba/' style='color:#81C784; text-decoration:none;'>↗ LinkedIn</a>
        <a href='https://cdrmaster.tistory.com/' style='color:#81C784; text-decoration:none;'>↗ Blog</a>
        <a href='mailto:cafeon90@gmail.com' style='color:#81C784; text-decoration:none;'>↗ Email</a>
    </div>
    <div style='padding-top: 12px; border-top: 1px solid #1f2733;
                color:#7A8089; font-size:0.72rem; line-height: 1.6;'>
        © 2026 Song BK · MIT License<br>
        Data sources: EU Commission · ICAP · KOTRA · KCCI SGI · IEA · IEAGHG · NETL · World Steel Association
    </div>
</div>
""",
    unsafe_allow_html=True,
)
