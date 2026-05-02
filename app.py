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
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        color: #A8AEB6 !important;
        padding: 9px 8px !important;       /* 좌우 패딩 압축으로 10개 다 보이게 */
        border-bottom: 2px solid transparent !important;
        transition: color 0.15s ease;
        min-width: auto !important;
    }
    /* 데스크톱에서 탭 사이 간격 미세조정 */
    div[data-baseweb="tab-list"] button + button {
        margin-left: 4px !important;
    }
    /* 모바일에서는 더 압축 + 가로 스크롤 허용 */
    @media (max-width: 768px) {
        div[data-baseweb="tab-list"] button {
            font-size: 0.76rem !important;
            padding: 8px 7px !important;
        }
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
       DataFrame — Streamlit 자동 다크모드에 맡기되, 외곽만 정돈
       (canvas 기반 glide-data-grid는 CSS color가 안 먹힘 — 강제 X)
       ───────────────────────────────────────────────── */
    div[data-testid="stDataFrame"] {
        border: 1px solid #1f2733;
        border-radius: 8px;
        overflow: hidden;
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
       Radio 버튼 — 텍스트 + 동그라미 둘 다 보이게
       ───────────────────────────────────────────────── */
    /* 라벨 텍스트 */
    .stRadio label,
    div[data-testid="stRadio"] label,
    .stRadio p {
        color: #F0F2F5 !important;
        font-size: 0.86rem !important;
    }
    /* radiogroup 가로 정렬 */
    div[role="radiogroup"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 14px !important;
        align-items: center !important;
    }
    div[role="radiogroup"] > label {
        display: inline-flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 6px !important;
        white-space: nowrap !important;
        margin: 0 !important;
    }

    /* 동그라미 가시성 — Streamlit 기본 동그라미가 어두운 배경에 묻히는 문제 해결 */
    /* 외부 원: 흰색 1.5px 테두리 + 본문보다 살짝 밝은 채움으로 윤곽 살림 */
    div[data-baseweb="radio"] > div:first-child {
        border-color: #A8AEB6 !important;
        border-width: 1.5px !important;
        background-color: #1a2028 !important;
    }
    /* 호버 시 테두리 더 밝게 */
    div[data-baseweb="radio"]:hover > div:first-child {
        border-color: #F0F2F5 !important;
    }
    /* 선택 시: cyan으로 채움 */
    div[data-baseweb="radio"] > div[aria-checked="true"],
    div[data-baseweb="radio"] > div:first-child:has(input:checked) {
        background-color: #4FC3F7 !important;
        border-color: #4FC3F7 !important;
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
# ─────────────────────────────────────────────────
# 색상 팔레트 (차분 다크모드 v3 — 톤다운된 흰색 통일)
# 모든 텍스트는 흰색 계열, 명도만 단계 — 회색 일절 사용 X
# ─────────────────────────────────────────────────
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
# 호환용 alias (구버전에서 C_MUTED 참조 시 안전)
C_MUTED    = C_TEXT4

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
    # 기본 layout 갱신 — title은 강제로 건드리지 않음
    # (title.text가 None인 fig에 title.font를 강제하면 빈 객체로 그려져 'undefined' 노출)
    fig.update_layout(
        dragmode=False,
        hovermode=False,
        clickmode="none",
        font=dict(color=C_TEXT2, family="-apple-system, sans-serif", size=12),
        legend=dict(font=dict(color=C_TEXT2, size=11)),
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
    )
    # title은 이미 텍스트가 있는 경우만 폰트 색상 적용
    existing_title = fig.layout.title
    if existing_title is not None and existing_title.text:
        fig.update_layout(title=dict(text=existing_title.text,
                                     font=dict(color=C_TEXT, size=14)))
    else:
        # 명시적으로 title 비활성화 (Plotly 일부 버전에서 빈 title이 'undefined'로 렌더되는 케이스 차단)
        fig.update_layout(title=dict(text=""))
    # 축 라벨/눈금/그리드
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
CCUS_APP_URL = "https://ccusamineanalysis-9z3cxdmxmd3muuepqlhaqb.streamlit.app/"   # 사용자 노출용 (라이브 앱)
CCUS_REPO_URL = "https://github.com/cafeon90-oss/CCUS_benchmark"                       # GitHub raw fetch 용 (Phase 2)
CCUS_JSON_URL = "https://raw.githubusercontent.com/cafeon90-oss/CCUS_benchmark/main/data/ccus_metrics.json"

# Phase 2에서 위 URL로 fetch — 현재는 placeholder mirror
DEFAULT_CCUS_METRICS = {
    "schema_version": "1.1-stub-9tech",
    "last_updated": "2026-05-01",
    "currency": "USD",
    "year_basis": 2025,
    "source_tool": CCUS_REPO_URL,
    "note": ("자매 CCUS 도구의 9개 기술을 모두 포함 (MEA + 3 Advanced Amine + 5 Non-amine). "
             "COCA·CAPEX·OPEX는 placeholder — Phase 2에서 자매 도구 LIT과 자동 동기화."),
    "technologies": {
        # ─── 1세대 amine baseline ───
        "MEA_30wt": {
            "display_name": "MEA 30wt% (baseline)", "short_name": "MEA",
            "category": "Amine (1st gen)",
            "COCA_USD_per_tCO2": 60, "CAPEX_USD_per_tpy": 950, "OPEX_USD_per_tCO2": 35,
            "TRL": 9, "capture_rate": 0.90,
        },
        # ─── 2세대 advanced amine (상용) ───
        "MHI_KS21": {
            "display_name": "MHI KS-21™", "short_name": "KS-21",
            "category": "Advanced Amine",
            "COCA_USD_per_tCO2": 52, "CAPEX_USD_per_tpy": 920, "OPEX_USD_per_tCO2": 30,
            "TRL": 9, "capture_rate": 0.90,
        },
        "Cansolv_DC103": {
            "display_name": "Shell Cansolv DC-103", "short_name": "DC-103",
            "category": "Advanced Amine",
            "COCA_USD_per_tCO2": 48, "CAPEX_USD_per_tpy": 880, "OPEX_USD_per_tCO2": 28,
            "TRL": 9, "capture_rate": 0.90,
        },
        "Aker_S26": {
            "display_name": "Aker S26", "short_name": "Aker S26",
            "category": "Advanced Amine",
            "COCA_USD_per_tCO2": 53, "CAPEX_USD_per_tpy": 1000, "OPEX_USD_per_tCO2": 31,
            "TRL": 9, "capture_rate": 0.90,
        },
        # ─── Non-amine 5종 ───
        "K2CO3_KIERSOL": {
            "display_name": "KIERSOL (KIER 한국)", "short_name": "KIERSOL",
            "category": "Hot Carbonate",
            "COCA_USD_per_tCO2": 50, "CAPEX_USD_per_tpy": 1050, "OPEX_USD_per_tCO2": 28,
            "TRL": 7, "capture_rate": 0.90,
        },
        "Chilled_NH3_CAP": {
            "display_name": "Chilled Ammonia (CAP)", "short_name": "CAP",
            "category": "Chilled NH₃",
            "COCA_USD_per_tCO2": 55, "CAPEX_USD_per_tpy": 1200, "OPEX_USD_per_tCO2": 30,
            "TRL": 8, "capture_rate": 0.90,
        },
        "Biphasic_DMX": {
            "display_name": "Biphasic DMX™", "short_name": "DMX",
            "category": "Biphasic",
            "COCA_USD_per_tCO2": 42, "CAPEX_USD_per_tpy": 1100, "OPEX_USD_per_tCO2": 22,
            "TRL": 7, "capture_rate": 0.90,
        },
        "Solid_TSA": {
            "display_name": "Solid Sorbent TSA", "short_name": "TSA",
            "category": "Solid Sorbent",
            "COCA_USD_per_tCO2": 70, "CAPEX_USD_per_tpy": 1400, "OPEX_USD_per_tCO2": 40,
            "TRL": 6, "capture_rate": 0.90,
        },
        "Calcium_Looping": {
            "display_name": "Calcium Looping (CaL)", "short_name": "CaL",
            "category": "Calcium Looping",
            "COCA_USD_per_tCO2": 38, "CAPEX_USD_per_tpy": 1300, "OPEX_USD_per_tCO2": 20,
            "TRL": 7, "capture_rate": 0.95,
        },
    },
    # 적합도 기준: flue gas CO₂ 농도, 온도, 열원 가용성, retrofit 용이성
    "sector_fit": {
        # 철강 BF-BOF (CO₂ 25~30%, retrofit 어려움)
        "steel_BF_BOF":   ["MHI_KS21", "Cansolv_DC103", "Aker_S26",
                            "Chilled_NH3_CAP", "Calcium_Looping", "MEA_30wt"],
        # 철강 EAF (CO₂ 5~10%, 저농도)
        "steel_EAF":      ["Solid_TSA", "Biphasic_DMX", "MEA_30wt"],
        # 시멘트 (CO₂ 14~20%, calcination 공정 자체에서 발생, CaL이 자연 통합)
        "cement":         ["Calcium_Looping", "Aker_S26", "MHI_KS21",
                            "Chilled_NH3_CAP", "MEA_30wt"],
        # 알루미늄 (anode 공정 CO₂ + 전력 grid factor)
        "aluminum":       ["MEA_30wt", "Cansolv_DC103", "Biphasic_DMX"],
        # NH₃ 비료 (고농도 CO₂ 99%+ 부생, 가장 저렴)
        "fertilizer_NH3": ["MEA_30wt", "K2CO3_KIERSOL", "Cansolv_DC103"],
        # 수소 SMR (PSA off-gas 고농도 CO₂)
        "hydrogen_SMR":   ["MEA_30wt", "Cansolv_DC103", "Biphasic_DMX",
                            "K2CO3_KIERSOL", "MHI_KS21"],
        # 발전 (CO₂ 12~15%, 표준 케이스)
        "power":          ["MHI_KS21", "Cansolv_DC103", "Aker_S26",
                            "Chilled_NH3_CAP", "Calcium_Looping", "MEA_30wt"],
    },
}


def load_ccus_metrics():
    """CCUS 도구 metrics fetch. Phase 2에서 live fetch 활성화.
    현재는 stub mode이므로 캐싱 없이 매번 최신 dict 반환 (개발 중 갱신 즉시 반영)."""
    # Phase 2 — 활성화 시 @st.cache_data(ttl=86400) 데코레이터 추가:
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
CBAM_NEWS_LOCAL = Path(__file__).parent / "data" / "cbam_news.json"
USAGE_MD_LOCAL = Path(__file__).parent / "USAGE.md"
USAGE_SVG_LOCAL = Path(__file__).parent / "cbam_mechanism.svg"


@st.cache_data(ttl=3600)
def load_usage_md():
    """USAGE.md 파일 로드. 실패 시 fallback 안내."""
    try:
        if USAGE_MD_LOCAL.exists():
            return USAGE_MD_LOCAL.read_text(encoding="utf-8"), "auto"
    except Exception:
        pass
    return "(USAGE.md를 불러올 수 없습니다.)", "fallback"


@st.cache_data(ttl=3600)
def load_usage_svg():
    """cbam_mechanism.svg 파일 로드."""
    try:
        if USAGE_SVG_LOCAL.exists():
            return USAGE_SVG_LOCAL.read_text(encoding="utf-8"), "auto"
    except Exception:
        pass
    return None, "fallback"

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


@st.cache_data(ttl=3600)   # 1시간 캐시 (월 1회 갱신이지만 새로고침 시 빠르게 보이게)
def load_cbam_news():
    """data/cbam_news.json에서 최신 EU CBAM 뉴스 로드. GitHub Actions 월 1회 갱신."""
    try:
        if CBAM_NEWS_LOCAL.exists():
            data = json.loads(CBAM_NEWS_LOCAL.read_text(encoding="utf-8"))
            items = sorted(
                data.get("items", []),
                key=lambda x: x.get("date", ""),
                reverse=True,
            )
            return items, data.get("last_updated", "n/a"), "auto"
    except Exception:
        pass
    return [], "fallback", "fallback"


# 카테고리별 표시 색상 + 이모지
NEWS_CATEGORY_META = {
    "milestone":   {"emoji": "🚀", "label": "이정표",  "color": "#4FC3F7"},
    "regulation":  {"emoji": "⚖️", "label": "규제",   "color": "#FFB74D"},
    "guidance":    {"emoji": "📘", "label": "가이드", "color": "#9575CD"},
    "notice":      {"emoji": "📢", "label": "공지",   "color": "#81C784"},
    "proposal":    {"emoji": "💡", "label": "제안",   "color": "#80DEEA"},
    "negotiation": {"emoji": "🗳️", "label": "협상",   "color": "#B0BEC5"},
    "other":       {"emoji": "📰", "label": "기타",   "color": "#A8AEB6"},
}

NEWS_IMPORTANCE_BADGE = {
    "high":   {"label": "⚠️ 중요",  "bg": "#3a1f1f", "fg": "#EF9A9A"},
    "medium": {"label": "○ 보통",  "bg": "#1f2733", "fg": "#A8AEB6"},
    "low":    {"label": "·",       "bg": "#1f2733", "fg": "#7A8089"},
}


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """#RRGGBB → rgba(r,g,b,a). Streamlit HTML sanitizer가 #RRGGBBAA 표기를
    잘못 파싱하는 문제 회피."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(79,195,247,{alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def render_news_card(item: dict, compact: bool = False) -> str:
    """뉴스 카드 HTML 렌더링. Streamlit st.markdown 호환을 위해 단일 라인 HTML."""
    cat = item.get("category", "other")
    cat_meta = NEWS_CATEGORY_META.get(cat, NEWS_CATEGORY_META["other"])
    importance = item.get("importance", "medium")
    imp_meta = NEWS_IMPORTANCE_BADGE.get(importance, NEWS_IMPORTANCE_BADGE["medium"])
    color = cat_meta["color"]
    color_bg = _hex_to_rgba(color, 0.13)
    title = item.get("title_ko") or item.get("title_en", "(제목 없음)")
    summary = item.get("summary_ko") or item.get("title_en", "")
    date = item.get("date", "")
    url = item.get("url", "#")
    src = item.get("source", "")
    cat_label = cat_meta["label"]
    cat_emoji = cat_meta["emoji"]

    if compact:
        return (
            '<div style="border-left:2px solid ' + color + ';padding:10px 14px;'
            'margin:6px 0;background:#11161e;border-radius:0 6px 6px 0;">'
            '<div style="font-size:0.72rem;color:#A8AEB6;margin-bottom:4px;">'
            + cat_emoji + ' ' + date + ' · ' + cat_label + '</div>'
            '<div style="font-size:0.88rem;color:#F0F2F5;font-weight:500;'
            'margin-bottom:6px;line-height:1.4;">' + title + '</div>'
            '<a href="' + url + '" target="_blank" style="color:' + color + ';'
            'text-decoration:none;font-size:0.76rem;">원문 보기 ↗</a>'
            '</div>'
        )

    return (
        '<div style="border-left:3px solid ' + color + ';padding:14px 18px;'
        'margin:10px 0;background:#11161e;border:1px solid #1f2733;'
        'border-left-width:3px;border-radius:0 8px 8px 0;">'
        # 메타 행
        '<div style="display:flex;align-items:center;gap:10px;'
        'margin-bottom:8px;flex-wrap:wrap;">'
        '<span style="background:' + color_bg + ';color:' + color + ';'
        'font-size:0.72rem;padding:2px 8px;border-radius:4px;font-weight:500;">'
        + cat_emoji + ' ' + cat_label + '</span>'
        '<span style="color:#A8AEB6;font-size:0.78rem;">' + date + '</span>'
        '<span style="color:#7A8089;font-size:0.74rem;">· ' + src + '</span>'
        '<span style="margin-left:auto;background:' + imp_meta['bg'] + ';'
        'color:' + imp_meta['fg'] + ';font-size:0.7rem;padding:2px 8px;'
        'border-radius:4px;">' + imp_meta['label'] + '</span>'
        '</div>'
        # 제목
        '<div style="font-size:0.96rem;color:#F0F2F5;font-weight:500;'
        'margin-bottom:8px;line-height:1.4;">' + title + '</div>'
        # 요약
        '<div style="color:#D4D8DD;font-size:0.86rem;line-height:1.65;'
        'margin-bottom:10px;">' + summary + '</div>'
        # 원문 링크
        '<a href="' + url + '" target="_blank" style="color:' + color + ';'
        'text-decoration:none;font-size:0.82rem;font-weight:500;">'
        '원문 보기 ↗</a>'
        '</div>'
    )


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
        # IAI 2023 글로벌 평균 14.8 tCO₂/t (전년 15.1 → 2023 14.8 감소 추세)
        # 한국은 primary smelter 없이 ingot 수입(중국·러시아·중동) → 수입품 SEE가 적용됨
        # 중국 평균 ~18 (석탄 grid 의존), 중동 ~9 (가스 + 수력 mix), 러시아 ~3 (수력)
        # 가중평균(중국 비중 큼) 약 16
        "default_SEE": 16.0,
        "kr_avg_SEE": 16.0,            # 한국 수입품의 가중평균 (중국 ingot 의존도 큼)
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
        # IEA Global Hydrogen Review 2024: SMR with unabated NG → 10~14 tCO₂/t H₂
        # (process 8~9 + upstream methane/NG 2~5)
        # 한국 SMR은 LNG 기반(상대적으로 낮은 upstream) → ~11
        "default_SEE": 11.0,
        "kr_avg_SEE": 11.0,
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
        "description": "재활용 기반 알루미늄 (재활용 비중 60%+) · EU 수출",
        "sector_lit": "aluminum_primary",
        "settings": {
            "annual_production_mt": 1.5,
            "eu_export_share_pct": 15.0,
            # 재활용 알루미늄 SEE = 0.5~3.0 (primary의 5% 에너지)
            # 노벨리스는 재활용 60%+ 비중 → primary 16 × 0.4 + recycled 1.5 × 0.6 ≈ 7.3
            # 더 보수적으로 6.0 (실제 verified 값 입력 권장)
            "user_SEE": 6.0,
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
            "user_SEE": 11.0,
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
    "se_h2gs": {
        "label": "🇸🇪 H2 Green Steel (DRI-H₂ 글로벌 베스트)",
        "description": "스웨덴 H2GS — Green H₂ DRI-EAF · 한국 기업 비교 기준 (EU 수출 100% 가정 = CBAM 회피)",
        "sector_lit": "steel_DRI_EAF",
        "settings": {
            "annual_production_mt": 5.0,
            "eu_export_share_pct": 100.0,    # EU 내 생산자 — CBAM 0
            "user_SEE": 0.40,
            "company_name": "H2 Green Steel (SE)",
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

def get_markup(sector_key: str, year: int) -> float:
    """EU IR 2025/2621 sector × year mark-up.
    철강·시멘트·알루미늄: 2026-2027 10% → 2028+ 30%
    비료: 1% (계속)
    수소·전력: 0% (default 값 신뢰도 높음)
    """
    if sector_key == "fertilizer":
        return 1.0
    if sector_key in ("hydrogen", "electricity"):
        return 0.0
    if sector_key in ("steel", "cement", "aluminum"):
        return 10.0 if year < 2028 else 30.0
    return 10.0   # 기본값


def calc_unit_cbam(SEE: float, benchmark: float, eua_price_eur: float,
                   year: int, mark_up_pct: float = 0.0,
                   k_ets_credit_eur: float = 0.0) -> dict:
    """
    단위 제품당 CBAM 부담.
    k_ets_credit_eur: 한국 K-ETS 등 수출국 carbon price 차감액 (€/t product).
                     EU CBAM Reg 2023/956 Art.9에 따라 verified 지불액 차감 가능.
    """
    pi = phase_in(year)
    gap = max(0.0, SEE - benchmark)
    effective_SEE = gap * (1.0 + mark_up_pct / 100.0)
    gross_unit_cost_eur = effective_SEE * pi * eua_price_eur
    # K-ETS 차감 (음수 방지)
    net_unit_cost_eur = max(0.0, gross_unit_cost_eur - k_ets_credit_eur)
    return {
        "gap": gap,
        "phase_in": pi,
        "effective_SEE": effective_SEE,
        "gross_unit_cost_eur": gross_unit_cost_eur,
        "k_ets_credit_eur": k_ets_credit_eur,
        "unit_cost_eur": net_unit_cost_eur,    # K-ETS 차감 후
        "below_benchmark": SEE <= benchmark,
    }


def calc_kets_credit(SEE: float, kets_price_krw: float, fx_eur_krw: float,
                     credit_share_pct: float = 100.0) -> float:
    """K-ETS 차감액 (€/t product) = SEE × K-ETS 가격 × verified 비율
    fx_eur_krw: KRW/EUR 환율
    credit_share_pct: verified 100% / partial 50% / none 0%
    """
    kets_price_eur = kets_price_krw / fx_eur_krw   # KRW/tCO₂ → EUR/tCO₂
    return SEE * kets_price_eur * (credit_share_pct / 100.0)


def calc_total_cbam(annual_production_mt: float, eu_export_share_pct: float,
                    SEE: float, benchmark: float, eua_price_eur: float,
                    year: int, mark_up_pct: float = 0.0,
                    k_ets_credit_eur: float = 0.0) -> dict:
    """연간 CBAM 총 부담."""
    eu_export_t = annual_production_mt * 1e6 * (eu_export_share_pct / 100.0)
    unit = calc_unit_cbam(SEE, benchmark, eua_price_eur, year, mark_up_pct, k_ets_credit_eur)
    annual_eur = unit["unit_cost_eur"] * eu_export_t
    annual_gross_eur = unit["gross_unit_cost_eur"] * eu_export_t
    annual_kets_credit_eur = unit["k_ets_credit_eur"] * eu_export_t
    return {
        **unit,
        "eu_export_t": eu_export_t,
        "annual_cost_eur": annual_eur,             # K-ETS 차감 후 net
        "annual_gross_cost_eur": annual_gross_eur, # K-ETS 차감 전 gross
        "annual_kets_credit_eur": annual_kets_credit_eur,
    }


def required_SEE_reduction(SEE: float, benchmark: float) -> dict:
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
                     eu_export_t: float, mark_up_pct: float = 0.0,
                     k_ets_credit_eur: float = 0.0) -> dict:
    """CCS 도입 시 CBAM 회피액. K-ETS 차감 후 net 비교."""
    new_SEE = SEE * (1.0 - capture_rate)
    base = calc_unit_cbam(SEE, benchmark, eua_price_eur, year, mark_up_pct, k_ets_credit_eur)
    new = calc_unit_cbam(new_SEE, benchmark, eua_price_eur, year, mark_up_pct, k_ets_credit_eur)
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


def ccs_npv_analysis(SEE: float, benchmark: float, capture_rate: float,
                     eua_price_eur: float, eu_export_t: float,
                     ccs_capex_usd_per_tpy: float, ccs_opex_usd_per_tco2: float,
                     fx_eur_usd: float,
                     start_year: int = 2026, ccs_online_year: int = 2030,
                     ccs_lifetime_yr: int = 20, discount_rate: float = 0.08,
                     ramping_curve: list = None,
                     mark_up_pct: float = 10.0,
                     k_ets_credit_eur: float = 0.0) -> dict:
    """CCS 도입 NPV 분석 — 가동개시 연도 + ramping + 할인율 반영.

    가정:
      - CCS 가동 전(start_year~ccs_online_year-1): 회피액 0, CAPEX 분할 지출 없음
        (단순화 — CAPEX는 ccs_online_year에 일시 집중)
      - 가동 후: ramping_curve에 따라 점진 capture rate
      - 수명 종료(ccs_online_year + ccs_lifetime_yr) 후 분석 종료
    """
    if ramping_curve is None:
        # 기본 ramping: 1년차 70%, 2년차 85%, 3년차+ 100% capture (target 대비)
        ramping_curve = [0.70, 0.85, 1.00]

    # 포집 plant 규모 = 이론 최대 = SEE × 수출량 × capture_rate (target)
    target_capture_t_yr = SEE * capture_rate * eu_export_t
    capex_total_usd = ccs_capex_usd_per_tpy * target_capture_t_yr
    capex_total_eur = capex_total_usd / fx_eur_usd

    end_year = ccs_online_year + ccs_lifetime_yr
    yearly = []
    npv_avoided = 0.0
    npv_cost = 0.0

    for y in range(start_year, end_year + 1):
        t = y - start_year
        df = 1.0 / ((1.0 + discount_rate) ** t)

        if y < ccs_online_year:
            avoided = 0.0
            cost = 0.0
        elif y == ccs_online_year:
            # CAPEX 일시 집중 (단순화)
            ramp_idx = 0
            ramp = ramping_curve[ramp_idx]
            actual_capture_rate = capture_rate * ramp
            avoided_dict = ccs_avoided_cbam(
                SEE, benchmark, actual_capture_rate, eua_price_eur, y,
                eu_export_t, mark_up_pct, k_ets_credit_eur,
            )
            avoided = avoided_dict["avoided_annual_eur"]
            opex_usd = ccs_opex_usd_per_tco2 * avoided_dict["captured_co2_t"]
            cost = capex_total_eur + opex_usd / fx_eur_usd
        else:
            # 가동 중
            ramp_idx = min(y - ccs_online_year, len(ramping_curve) - 1)
            ramp = ramping_curve[ramp_idx]
            actual_capture_rate = capture_rate * ramp
            avoided_dict = ccs_avoided_cbam(
                SEE, benchmark, actual_capture_rate, eua_price_eur, y,
                eu_export_t, mark_up_pct, k_ets_credit_eur,
            )
            avoided = avoided_dict["avoided_annual_eur"]
            opex_usd = ccs_opex_usd_per_tco2 * avoided_dict["captured_co2_t"]
            cost = opex_usd / fx_eur_usd

        npv_avoided += avoided * df
        npv_cost += cost * df
        yearly.append({
            "year": y,
            "phase_in": phase_in(y),
            "avoided_eur": avoided,
            "cost_eur": cost,
            "df": df,
        })

    npv_net = npv_avoided - npv_cost
    bep_year = None
    cum_avoided = 0.0
    cum_cost = 0.0
    for row in yearly:
        cum_avoided += row["avoided_eur"]
        cum_cost += row["cost_eur"]
        if cum_avoided >= cum_cost and bep_year is None and row["year"] > ccs_online_year:
            bep_year = row["year"]

    return {
        "yearly": yearly,
        "capex_total_eur": capex_total_eur,
        "npv_avoided_eur": npv_avoided,
        "npv_cost_eur": npv_cost,
        "npv_net_eur": npv_net,
        "bep_year": bep_year,
        "ccs_online_year": ccs_online_year,
        "lifetime": ccs_lifetime_yr,
        "discount_rate": discount_rate,
    }


# 감축 수단 라이브러리 (탭 ④ 시뮬레이터용)
ABATEMENT_OPTIONS = [
    {
        "key": "ccs_90",
        "label": "🟦 CCS 90% (자매 CCUS 도구)",
        "applies_to": ["steel_BF_BOF", "cement_clinker", "fertilizer_NH3",
                        "hydrogen_gray", "electricity", "aluminum_primary"],
        "reduction_pct": 90.0,
        "trl": 9,
        "note": "Post-combustion amine 표준. 자매 CCUS 도구의 9개 기술 비교 가능.",
    },
    {
        "key": "ccs_95",
        "label": "🟦 CCS 95% (Calcium Looping)",
        "applies_to": ["cement_clinker", "steel_BF_BOF", "electricity"],
        "reduction_pct": 95.0,
        "trl": 7,
        "note": "Calcium Looping은 시멘트와 자연 통합 (CaO 공유). 자매 도구 참조.",
    },
    # ─── DRI-H₂ 3분할 (수소 색깔별) ───
    {
        "key": "dri_h2_gray",
        "label": "🟧 DRI-H₂ Gray (-30%)",
        "applies_to": ["steel_BF_BOF"],
        "reduction_pct": 30.0,
        "trl": 9,
        "note": "Gray H₂(SMR) 기반 DRI. SMR 자체 배출 때문에 감축 효과 제한적.",
    },
    {
        "key": "dri_h2_blue",
        "label": "🟦 DRI-H₂ Blue (-76%)",
        "applies_to": ["steel_BF_BOF"],
        "reduction_pct": 76.0,
        "trl": 7,
        "note": "Blue H₂(SMR + CCS 90%) 기반 DRI. 중간 단계 솔루션.",
    },
    {
        "key": "dri_h2_green",
        "label": "🟢 DRI-H₂ Green (-95%)",
        "applies_to": ["steel_BF_BOF"],
        "reduction_pct": 95.0,
        "trl": 6,
        "note": "Green H₂(전해, RE 기반) 기반 DRI. H2 Green Steel 모델. 그린수소 가용성·가격 의존.",
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
        "applies_to": ["aluminum_primary", "electricity", "hydrogen_gray",
                        "steel_scrap_EAF", "steel_DRI_EAF"],
        "reduction_pct": 15.0,
        "trl": 9,
        "note": "전력 grid factor 감축. 알루미늄·전기로에 효과 큼. 한국 grid 의존.",
    },
    # ─── Bio-CCS sector 확장 (시멘트·철강 추가) ───
    {
        "key": "beccs",
        "label": "🌱 Bio-CCS (-110%, 음의 배출)",
        "applies_to": ["fertilizer_NH3", "electricity",
                        "cement_clinker", "steel_BF_BOF"],
        "reduction_pct": 110.0,
        "trl": 6,
        "note": "Biomass + CCS. 음의 배출 가능. 시멘트(LafargeHolcim CHRYSALIS), "
                "철강(Vale charcoal) 사례. 바이오매스 공급 제약.",
    },
    {
        "key": "energy_eff",
        "label": "🟧 에너지 효율 개선 (-10%)",
        "applies_to": ["steel_BF_BOF", "cement_clinker", "fertilizer_NH3",
                        "aluminum_primary", "hydrogen_gray"],
        "reduction_pct": 10.0,
        "trl": 9,
        "note": "공정 최적화·열회수. 단기 적용 가능. 가장 빠른 개선책.",
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
    eu_export_share_pct = st.number_input(
        "EU 수출 비중 (%)",
        min_value=0.0, max_value=100.0,
        value=float(st.session_state.get("eu_export_share_pct", 5.0)),
        step=0.5, format="%.2f",
        key="eu_export_share_pct",
        help="총 생산량 중 EU 수출분 비율 (0 ~ 100). CBAM 부과 대상 base.",
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
    # Mark-up은 사이드바 하단의 analysis_year 결정 후 자동 적용 (get_markup)
    if see_mode == "EU Default 사용 (mark-up 적용)":
        user_SEE = sector["default_SEE"]
        mark_up_pct = 10.0   # 임시값 — analysis_year 입력 후 자동 갱신
        st.caption(f"⚠️ Default {user_SEE:.3f} {sector['unit']} (mark-up은 분석연도 따라 자동)")
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

    # ─── Scope 2 (전력 간접배출) — 알루미늄·수소·전력 sector 한정 ───
    SCOPE2_INTENSIVE = {
        "aluminum_primary": {"kwh_per_unit": 14000, "label": "알루미늄 (~14,000 kWh/t)"},
        "hydrogen_gray": {"kwh_per_unit": 50000,
                            "label": "수소 SMR (전력+가스, ~50,000 kWh/t equivalent)"},
        "electricity": {"kwh_per_unit": 0, "label": "전력 (자체)"},
        "steel_scrap_EAF": {"kwh_per_unit": 600, "label": "Scrap-EAF (~600 kWh/t)"},
        "steel_DRI_EAF": {"kwh_per_unit": 800, "label": "DRI-EAF (~800 kWh/t)"},
    }
    if sector_lit in SCOPE2_INTENSIVE:
        with st.expander("⚡ Scope 2 (전력 간접배출) 상세 입력 — 선택"):
            sc2_meta = SCOPE2_INTENSIVE[sector_lit]
            st.caption(
                f"이 sector는 전력 사용이 SEE에 큰 영향을 줍니다. "
                f"표준 사용량: {sc2_meta['label']}. "
                f"한국 grid 기본값 {KR_GRID_FACTOR} tCO₂/MWh."
            )
            override_grid = st.checkbox(
                "전력 배출계수 직접 입력 (RE100·계약 청정전력 등)",
                value=False, key="override_grid",
            )
            if override_grid and sector_lit != "electricity":
                custom_grid = st.number_input(
                    "전력 배출계수 (tCO₂/MWh)",
                    min_value=0.0, max_value=1.5,
                    value=KR_GRID_FACTOR, step=0.01, format="%.3f",
                    help=("한국 평균 0.443. RE100 ~0.05. 100% 그린파워 0. "
                          "중국 grid 0.85. 계약 청정전력 인증 시 차감 가능."),
                )
                # SEE 자동 재계산 (kwh × grid_factor / 1000)
                see_grid_component = sc2_meta["kwh_per_unit"] * custom_grid / 1000.0
                see_direct_estimate = max(0, user_SEE - sc2_meta["kwh_per_unit"]
                                            * KR_GRID_FACTOR / 1000.0)
                user_SEE_recalc = see_direct_estimate + see_grid_component
                st.caption(
                    f"🔄 SEE 재산정: direct ~{see_direct_estimate:.2f} + "
                    f"electricity {see_grid_component:.2f} = "
                    f"**{user_SEE_recalc:.3f}** {sector['unit']}"
                )
                user_SEE = user_SEE_recalc

    st.markdown("---")

    # 경제성 가정
    st.markdown("### 💰 경제성 가정")

    # EUA 자동 fetch
    eua_default, eua_date, eua_mode = load_eua_price()
    eua_price = st.number_input(
        "EUA 가격 (€/tCO₂)",
        min_value=20.0, max_value=300.0,
        value=float(eua_default), step=1.0, format="%.1f",
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
    analysis_year = st.selectbox(
        "분석 연도 (Phase-in 적용)",
        options=list(range(2026, 2035)),
        index=0,
        format_func=lambda y: f"{y}년 (phase-in {phase_in(y)*100:.1f}%)",
        help="CBAM phase-in factor 자동 적용. 2026: 2.5% → 2034: 100%",
    )

    # ─── Mark-up 자동 결정 (sector × year) ─────────────────────
    # EU IR 2025/2621: 철강·시멘트·알루미늄 2026-2027 10% → 2028+ 30%
    auto_markup = get_markup(sector["sector_key"], analysis_year)
    if see_mode == "EU Default 사용 (mark-up 적용)":
        mark_up_pct = auto_markup
        st.caption(f"📌 자동 mark-up: **{mark_up_pct:.0f}%** "
                   f"({sector['sector_key']}, {analysis_year}년 기준 — IR 2025/2621)")

    st.markdown("---")

    # ─── K-ETS 차감 (한국 할당대상업체) ─────────────────────
    st.markdown("### 🇰🇷 K-ETS 차감")
    use_kets = st.checkbox(
        "K-ETS 지불액 차감 (Reg 2023/956 Art.9)",
        value=False,
        help=("한국 K-ETS 할당대상업체는 K-ETS에서 이미 지불한 carbon price를 "
              "EU CBAM에서 verified 차감 가능. Reg 2023/956 Art.9. "
              "POSCO·현대제철 등 대형 배출원에 적용."),
    )
    if use_kets:
        kets_price_krw = st.number_input(
            "K-ETS 가격 (₩/tCO₂)",
            min_value=1000, max_value=50000,
            value=8000, step=500,
            help="K-ETS 시장 가격. 2024-2025 평균 ~₩7,000~10,000.",
        )
        kets_credit_share = st.slider(
            "Verified 차감 비율 (%)",
            min_value=0, max_value=100, value=50, step=5,
            help=("실제 차감 가능 비율. EU 협상·MRV 호환·검증 절차에 따라 변동. "
                  "보수적: 50%, 낙관적: 80~100%, 비관적: 0~30%."),
        )
        k_ets_credit_eur = calc_kets_credit(
            user_SEE, kets_price_krw,
            fx_eur_krw, kets_credit_share,
        )
        st.caption(f"📌 차감액: **€{k_ets_credit_eur:.2f}/t product**")
    else:
        k_ets_credit_eur = 0.0
        kets_price_krw = 8000
        kets_credit_share = 0

    st.markdown("---")

    # ─── EU 수출 평균가 (인상률 KPI 계산용) ───────────────────
    st.markdown("### 📈 EU 수출 평균가")
    DEFAULT_REF_PRICES = {
        "steel_BF_BOF": 700, "steel_DRI_EAF": 800, "steel_scrap_EAF": 650,
        "cement_clinker": 100, "aluminum_primary": 2400,
        "fertilizer_NH3": 500, "hydrogen_gray": 2500, "hydrogen_blue": 4000,
        "electricity": 100,
    }
    ref_unit_price = st.number_input(
        f"평균 수출가 (USD/{sector['product_unit']})",
        min_value=10, max_value=10000,
        value=DEFAULT_REF_PRICES.get(sector_lit, 700),
        step=10,
        help=("EU 수출가 인상률 KPI 산정용 분모. LME(알루미늄), "
              "SBB(철강), CemNet(시멘트) 등 시장가 기준. 본인의 실제 수출가로 조정."),
    )

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
            자매 도구: <a href='{CCUS_APP_URL}' target='_blank' style='color:#9b8de8; text-decoration:none;'>🌫️ CCUS 벤치마크 ↗</a>
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

# ────────────── 최신 CBAM 공지 미리보기 (헤더 expander) ──────────────
_news_items, _news_updated, _news_mode = load_cbam_news()
if _news_items:
    _latest_3 = _news_items[:3]
    _latest_label = (
        f"📰 EU CBAM 최신 공지 — 전체 {len(_news_items)}건 · "
        f"마지막 갱신 {_news_updated}"
    )
    with st.expander(_latest_label, expanded=False):
        for it in _latest_3:
            st.markdown(render_news_card(it, compact=True), unsafe_allow_html=True)
        st.markdown(
            "<div style='text-align: right; font-size: 0.78rem; "
            "color: #A8AEB6; margin-top: 8px;'>"
            "탭 <strong>⑩ 📰 CBAM 뉴스</strong>에서 전체 보기 →"
            "</div>",
            unsafe_allow_html=True,
        )

# ======================================================================
# 메인 계산 (사이드바 입력 기반) — K-ETS 차감 포함
# ======================================================================
result = calc_total_cbam(
    annual_production_mt=annual_production_mt,
    eu_export_share_pct=eu_export_share_pct,
    SEE=user_SEE,
    benchmark=sector["eu_benchmark"],
    eua_price_eur=eua_price,
    year=analysis_year,
    mark_up_pct=mark_up_pct,
    k_ets_credit_eur=k_ets_credit_eur,
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
    # EU 수출가 인상률 — 사이드바에서 받은 사용자 입력 ref_unit_price 사용
    cbam_unit_usd = result["unit_cost_eur"] / fx_eur_usd
    price_uplift_pct = (cbam_unit_usd / max(ref_unit_price, 1)) * 100.0
    st.metric(
        "EU 수출가 인상률",
        f"{price_uplift_pct:+.2f}%",
        delta=f"≈ ${cbam_unit_usd:.1f}/t / ${ref_unit_price} base",
        delta_color="off",
        help=f"기준: 사이드바에서 입력한 EU 수출가 ${ref_unit_price}/{sector['product_unit']}",
    )

with col4:
    # CCS 90% 도입 시 회피액 — K-ETS 차감 후 net 비교
    avoided = ccs_avoided_cbam(
        SEE=user_SEE, benchmark=sector["eu_benchmark"],
        capture_rate=0.90, eua_price_eur=eua_price,
        year=analysis_year, eu_export_t=result["eu_export_t"],
        mark_up_pct=mark_up_pct,
        k_ets_credit_eur=k_ets_credit_eur,
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
        "① 종합",
        "② Sector별 분석",
        "③ 기업영향",
        "④ 감축 시뮬레이션",
        "⑤ CCUS",
        "⑥ 연도별 변화",
        "⑦ Custom 입력",
        "⑧ 방법론",
        "⑨ 출처",
        "⑩ CBAM 뉴스",
        "📘 설명서",
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

    # ────────────── 차트: SEE vs Benchmark ──────────────
    st.markdown("##### 📊 한국 평균 SEE vs EU Benchmark")
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
        title=None,                   # 'undefined' 텍스트 노출 방지
        barmode="group", template="plotly_dark",
        height=440,
        margin=dict(l=10, r=10, t=20, b=70),
        paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        xaxis=dict(title=dict(text="tCO₂/단위제품", standoff=12)),
        yaxis=dict(title=None),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.28,
            xanchor="center", x=0.5,
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    lock_static(fig1)
    st.plotly_chart(fig1, use_container_width=True, config=PLOTLY_CONFIG)

    # ────────────── 표: 9개 sector 단위 CBAM cost ──────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"<h5 style='color:#F0F2F5; margin: 12px 0 8px 0;'>"
        f"📋 {analysis_year}년 단위 CBAM cost — 9개 sector 상세 비교"
        f"</h5>",
        unsafe_allow_html=True,
    )
    df_show = df_overview[[
        "Sector", "SEE (kr)", "Benchmark", "Gap",
        "Unit cost (€/t)", "Unit cost (USD/t)"
    ]].copy()
    df_show["SEE (kr)"] = df_show["SEE (kr)"].map(lambda x: f"{x:.3f}")
    df_show["Benchmark"] = df_show["Benchmark"].map(lambda x: f"{x:.3f}")
    df_show["Gap"] = df_show["Gap"].map(lambda x: f"{x:.3f}")
    df_show["Unit cost (€/t)"] = df_show["Unit cost (€/t)"].map(lambda x: f"€{x:.2f}")
    df_show["Unit cost (USD/t)"] = df_show["Unit cost (USD/t)"].map(lambda x: f"${x:.2f}")
    df_show.columns = ["Sector", "한국 SEE", "EU benchmark", "Gap",
                        f"단가 €/t ({analysis_year})", f"단가 $/t ({analysis_year})"]
    st.dataframe(df_show, hide_index=True, use_container_width=True)
    st.caption(
        f"↑ {analysis_year}년 phase-in {phase_in(analysis_year)*100:.1f}% × EUA €{eua_price:.0f}/tCO₂ 적용. "
        f"Unit cost 내림차순 정렬 — 부담 큰 sector가 위."
    )


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

    # 4-C: CCS BEP — 자매 CCUS 도구의 모든 기술 평가
    ccus_data_check, _ = load_ccus_metrics()
    n_total_techs = len(ccus_data_check.get("technologies", {}))
    st.markdown(f"##### 💰 4-C. CCS 도입 시 BEP 분석 — 전체 {n_total_techs}개 기술 비교")

    ccus_data, ccus_mode = load_ccus_metrics()
    fit_techs = set(ccus_data["sector_fit"].get(sector["ccus_sector"], []))
    all_techs = list(ccus_data["technologies"].keys())

    bep_rows = []
    for tk in all_techs:
        tdata = ccus_data["technologies"].get(tk)
        if not tdata:
            continue
        cap_rate = tdata["capture_rate"]
        is_recommended = tk in fit_techs
        avoided = ccs_avoided_cbam(
            SEE=user_SEE, benchmark=sector["eu_benchmark"],
            capture_rate=cap_rate, eua_price_eur=eua_price,
            year=analysis_year, eu_export_t=result["eu_export_t"],
            mark_up_pct=mark_up_pct,
            k_ets_credit_eur=k_ets_credit_eur,
        )
        ccs_cost_usd = tdata["COCA_USD_per_tCO2"] * avoided["captured_co2_t"]
        avoided_usd = avoided["avoided_annual_eur"] / fx_eur_usd
        net_usd = avoided_usd - ccs_cost_usd
        bep_rows.append({
            "추천": "⭐" if is_recommended else "",
            "CCUS 기술": tdata["display_name"],
            "Capture η": f"{cap_rate*100:.0f}%",
            "COCA (USD/t)": f"${tdata['COCA_USD_per_tCO2']}",
            "포집 CO₂ (t/yr)": f"{avoided['captured_co2_t']:,.0f}",
            "CCS 비용 ($M/yr)": f"${ccs_cost_usd/1e6:,.2f}",
            "CBAM 회피 ($M/yr)": f"${avoided_usd/1e6:,.2f}",
            "_net": net_usd,
            "순익 ($M/yr)": f"${net_usd/1e6:+,.2f}",
            "TRL": tdata["TRL"],
        })
    df_bep = pd.DataFrame(bep_rows)
    df_bep = df_bep.sort_values("_net", ascending=False).drop(columns=["_net"])
    st.dataframe(df_bep, hide_index=True, use_container_width=True)

    n_recommended = len(fit_techs)
    st.markdown(
        f"""
> 💡 **해석**: 자매 CCUS 도구의 **{n_total_techs}개 기술 모두** mirror하여 자동 계산. ⭐는 sector 적합 기술 ({n_recommended}개).
> 순익 내림차순 정렬 — 가장 위가 가장 경제적. 순익 양수 → CCS 도입이 CBAM 부담보다 저렴.
> 단, 위 분석은 **단년도 정태 분석** — 실제로는 가동개시 연도·ramping·할인율을 고려해야. 아래 4-D 참조.
> 자세한 기술 비교는 [자매 CCUS 벤치마크 도구 ↗]({CCUS_APP_URL}) 에서 직접 시뮬레이션 가능.
"""
    )

    # 4-D: NPV 기반 동태 BEP 분석 (CCS ramping + 할인율)
    st.markdown("##### 📅 4-D. NPV 기반 동태 BEP 분석 (CCS 가동개시·ramping·할인율 반영)")
    st.caption(
        "단년도 정태(static) 분석은 'CCS가 분석 연도에 즉시 100% 가동 중'을 가정합니다. "
        "현실은 FID → 건설 → 가동까지 4~6년이 걸리고, 가동 후에도 ramping이 필요합니다. "
        "여기서는 가동 개시 연도와 ramping 곡선을 반영한 NPV 분석을 제공합니다."
    )

    npv_c1, npv_c2, npv_c3 = st.columns(3)
    with npv_c1:
        ccs_online_year = st.number_input(
            "CCS 가동 개시 연도",
            min_value=2027, max_value=2034, value=2030, step=1,
            key="ccs_online_year",
            help="FID 후 EPC 4~6년. POSCO·Norcem 사례상 2030년이 현실적.",
        )
    with npv_c2:
        discount_rate_pct = st.number_input(
            "할인율 (%)",
            min_value=3.0, max_value=15.0, value=8.0, step=0.5, format="%.1f",
            key="discount_rate_pct",
            help="WACC 기반. 한국 산업평균 7~9%, 보수적 평가는 10%+.",
        )
    with npv_c3:
        ccs_lifetime = st.number_input(
            "CCS 수명 (년)",
            min_value=10, max_value=30, value=20, step=1,
            key="ccs_lifetime",
            help="회계 감가상각 기준. 일반 화학플랜트 25년, CCS retrofit 15~20년 일반.",
        )

    npv_tech = st.selectbox(
        "NPV 분석할 기술 선택",
        options=all_techs,
        index=0,
        format_func=lambda k: ccus_data["technologies"][k]["display_name"],
        key="npv_tech_select",
    )
    npv_tdata = ccus_data["technologies"][npv_tech]
    npv_result = ccs_npv_analysis(
        SEE=user_SEE, benchmark=sector["eu_benchmark"],
        capture_rate=npv_tdata["capture_rate"],
        eua_price_eur=eua_price,
        eu_export_t=result["eu_export_t"],
        ccs_capex_usd_per_tpy=npv_tdata["CAPEX_USD_per_tpy"],
        ccs_opex_usd_per_tco2=npv_tdata["OPEX_USD_per_tCO2"],
        fx_eur_usd=fx_eur_usd,
        start_year=2026,
        ccs_online_year=int(ccs_online_year),
        ccs_lifetime_yr=int(ccs_lifetime),
        discount_rate=discount_rate_pct / 100.0,
        mark_up_pct=mark_up_pct,
        k_ets_credit_eur=k_ets_credit_eur,
    )

    # NPV KPI 4개
    npv_k1, npv_k2, npv_k3, npv_k4 = st.columns(4)
    with npv_k1:
        st.metric("CCS CAPEX (총)",
                  fmt_money(npv_result["capex_total_eur"] / fx_eur_usd, fx_usd_krw, currency_mode_key))
    with npv_k2:
        st.metric("NPV 회피액 (수명누적)",
                  fmt_money(npv_result["npv_avoided_eur"] / fx_eur_usd, fx_usd_krw, currency_mode_key))
    with npv_k3:
        st.metric("NPV 비용 (CAPEX+OPEX)",
                  fmt_money(npv_result["npv_cost_eur"] / fx_eur_usd, fx_usd_krw, currency_mode_key))
    with npv_k4:
        net_color = "normal" if npv_result["npv_net_eur"] > 0 else "inverse"
        st.metric("NPV 순익", fmt_money(npv_result["npv_net_eur"] / fx_eur_usd, fx_usd_krw, currency_mode_key),
                  delta=f"BEP {npv_result['bep_year'] or 'N/A'}",
                  delta_color="off")

    # 연도별 trajectory 차트
    df_npv = pd.DataFrame(npv_result["yearly"])
    df_npv["avoided_M_eur"] = df_npv["avoided_eur"] / 1e6
    df_npv["cost_M_eur"] = df_npv["cost_eur"] / 1e6
    df_npv["cum_avoided_M"] = df_npv["avoided_M_eur"].cumsum()
    df_npv["cum_cost_M"] = df_npv["cost_M_eur"].cumsum()
    df_npv["cum_net_M"] = df_npv["cum_avoided_M"] - df_npv["cum_cost_M"]

    fig_npv = go.Figure()
    fig_npv.add_trace(go.Scatter(x=df_npv["year"], y=df_npv["cum_avoided_M"],
                                  mode="lines+markers", name="누적 CBAM 회피",
                                  line=dict(color=C_GOOD, width=2.5)))
    fig_npv.add_trace(go.Scatter(x=df_npv["year"], y=df_npv["cum_cost_M"],
                                  mode="lines+markers", name="누적 CCS 비용",
                                  line=dict(color=C_BAD, width=2.5)))
    fig_npv.add_trace(go.Scatter(x=df_npv["year"], y=df_npv["cum_net_M"],
                                  mode="lines+markers", name="누적 순익",
                                  line=dict(color=C_PRIMARY, width=3, dash="solid")))
    fig_npv.add_hline(y=0, line_dash="dash", line_color=C_TEXT4)
    fig_npv.add_vline(x=int(ccs_online_year), line_dash="dot", line_color=C_HIGH,
                      annotation_text=f"가동 {int(ccs_online_year)}", annotation_position="top right")
    fig_npv.update_layout(
        title=None, template="plotly_dark", height=380,
        margin=dict(l=10, r=10, t=20, b=40),
        xaxis_title="연도", yaxis_title="누적 €M (할인 미적용)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )
    lock_static(fig_npv)
    st.plotly_chart(fig_npv, use_container_width=True, config=PLOTLY_CONFIG)

    if npv_result["npv_net_eur"] > 0:
        st.success(
            f"✅ {npv_tdata['display_name']} 도입 권장 — "
            f"NPV 순익 €{npv_result['npv_net_eur']/1e6:+,.1f}M, "
            f"BEP {npv_result['bep_year'] or 'N/A'}년."
        )
    else:
        st.warning(
            f"⚠️ {npv_tdata['display_name']} 도입 시 NPV 적자 "
            f"€{npv_result['npv_net_eur']/1e6:,.1f}M. "
            f"다른 기술 선택 또는 EUA 가격·할인율 가정 점검 필요."
        )

    st.caption(
        f"가정: 분석기간 2026 ~ {int(ccs_online_year) + int(ccs_lifetime)}년 · "
        f"가동개시 일시 CAPEX (단순화) · ramping 1년차 70% / 2년차 85% / 3년차+ 100% · "
        f"phase-in factor 연도별 자동 적용 · "
        f"K-ETS 차감 {'적용' if use_kets else '미적용'} · "
        f"할인율 {discount_rate_pct:.1f}%."
    )


# ────────────── 탭 ⑤ CCUS 연계 (stub) ──────────────
with tabs[4]:
    st.subheader("⑤ CCUS 연계 — 자매 도구")

    ccus_data, ccus_mode = load_ccus_metrics()

    st.markdown(
        f"""
<div class='sister-card'>
<h4 style='margin:0 0 8px 0;'>🌫️ 자매 도구: CCUS 기술 벤치마크</h4>
한국·미국·EU의 9개 CCUS 흡수제·공정 기술의 COCA·SPECCA·CAPEX 비교 도구.<br>
이 CBAM 계산기와 데이터 연계되어 sector별 적합 기술 자동 추천 + BEP 분석 제공.<br><br>
<strong>🚀 <a href='{CCUS_APP_URL}' target='_blank'>라이브 앱에서 직접 시뮬레이션 ↗</a></strong>
&nbsp;·&nbsp;
<a href='{CCUS_REPO_URL}' target='_blank' style='font-size:0.82rem;'>📦 GitHub repo ↗</a>
<br><br>
<small>📌 현재 Phase 1: Stub mode (placeholder 값 사용 중) ·
Phase 2 예정: <code>data/ccus_metrics.json</code> live fetch</small>
</div>
""",
        unsafe_allow_html=True,
    )

    n_total_techs_5 = len(ccus_data.get("technologies", {}))
    st.markdown(f"##### 🔌 자매 CCUS 도구의 {n_total_techs_5}개 기술 — 전체 비교 (현재 sector: {sector['name']})")

    fit_techs = set(ccus_data["sector_fit"].get(sector["ccus_sector"], []))
    all_techs = list(ccus_data["technologies"].keys())

    rec_rows = []
    for tk in all_techs:
        tdata = ccus_data["technologies"].get(tk)
        if not tdata:
            continue
        is_recommended = tk in fit_techs
        rec_rows.append({
            "추천": "⭐" if is_recommended else "",
            "기술": tdata["display_name"],
            "Short": tdata["short_name"],
            "COCA (USD/t)": f"${tdata['COCA_USD_per_tCO2']}",
            "CAPEX (USD/tpy)": f"${tdata['CAPEX_USD_per_tpy']}",
            "OPEX (USD/t)": f"${tdata['OPEX_USD_per_tCO2']}",
            "Capture η": f"{tdata['capture_rate']*100:.0f}%",
            "TRL": tdata["TRL"],
            "_coca": tdata["COCA_USD_per_tCO2"],
        })
    df_rec = pd.DataFrame(rec_rows).sort_values("_coca", ascending=True).drop(columns=["_coca"])
    st.dataframe(df_rec, hide_index=True, use_container_width=True)
    n_recommended = len(fit_techs)
    st.caption(
        f"⭐ 표시: 현재 sector({sector['name']})에 적합한 기술 {n_recommended}개. "
        f"COCA 오름차순 정렬 — 가장 저렴한 기술이 위. "
        f"적합도는 sector별 flue gas 농도·온도·열원 가용성 기반."
    )

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
    fig_time.add_vrect(x0=2022.5, x1=2025.5, fillcolor=C_TEXT4, opacity=0.15,
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
    st.markdown("**EUA 가격 범위 (€/tCO₂)** — 민감도 분석")
    cmin, cmax = st.columns(2)
    with cmin:
        eua_min = st.number_input(
            "최저", min_value=20, max_value=300, value=60, step=5,
            key="eua_min_input",
        )
    with cmax:
        eua_max = st.number_input(
            "최고", min_value=20, max_value=300, value=130, step=5,
            key="eua_max_input",
        )
    if eua_min >= eua_max:
        st.warning("최저값은 최고값보다 작아야 합니다.")
        eua_min, eua_max = 60, 130
    eua_grid = list(range(int(eua_min), int(eua_max) + 1, 10))
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


# ────────────── 탭 ⑩ EU CBAM 뉴스 ──────────────
with tabs[9]:
    st.subheader("⑩ 📰 EU CBAM 최신 공지")

    news_items, news_updated, news_mode = load_cbam_news()

    if not news_items:
        st.info("⚠️ 뉴스 데이터를 불러올 수 없습니다 (`data/cbam_news.json` 미존재). "
                "GitHub Actions의 `cbam_news_fetch.yml` workflow가 매월 1일 자동 fetch합니다.")
    else:
        # 상태 안내 — 완전 자동화 모드 강조
        n_total = len(news_items)
        n_high = len([n for n in news_items if n.get("importance") == "high"])
        st.markdown(
            f"""
<div style='display: flex; gap: 14px; align-items: center; margin-bottom: 14px;
            padding: 10px 14px; background: #11161e; border: 1px solid #1f2733;
            border-radius: 8px; font-size: 0.84rem; color: #D4D8DD; flex-wrap: wrap;'>
    <span>📅 마지막 갱신: <strong style='color:#F0F2F5;'>{news_updated}</strong></span>
    <span style='color: #7A8089;'>·</span>
    <span>전체 <strong style='color:#F0F2F5;'>{n_total}</strong>건</span>
    <span style='color: #7A8089;'>·</span>
    <span>⚠️ 중요도 high <strong style='color:#EF9A9A;'>{n_high}</strong>건</span>
    <span style='margin-left: auto; background: #1d2b22; color: #81C784;
                  font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 500;'>
        🤖 완전 자동화
    </span>
</div>
""",
            unsafe_allow_html=True,
        )

        # 카테고리 필터만 (중요/전체 필터는 모두 important이므로 제거)
        cats_in_data = sorted({n.get("category", "other") for n in news_items})
        cat_options = [
            f"{NEWS_CATEGORY_META.get(c, NEWS_CATEGORY_META['other'])['emoji']} "
            f"{NEWS_CATEGORY_META.get(c, NEWS_CATEGORY_META['other'])['label']}"
            for c in cats_in_data
        ]
        selected_cat_labels = st.multiselect(
            "카테고리 필터 (전체 표시 중)",
            options=cat_options,
            default=cat_options,
            key="news_cat_multi",
        )
        selected_cats = [
            cats_in_data[i]
            for i, lbl in enumerate(cat_options)
            if lbl in selected_cat_labels
        ]

        filtered = [n for n in news_items if n.get("category", "other") in selected_cats]

        if not filtered:
            st.info("선택한 카테고리에 해당하는 공지가 없습니다.")
        else:
            st.markdown(f"#### 📋 {len(filtered)}건")
            for it in filtered:
                st.markdown(render_news_card(it, compact=False), unsafe_allow_html=True)

        # 자동화 안내
        st.markdown("---")
        st.markdown(
            """
##### 🤖 완전 자동화 시스템

이 탭은 **사용자 개입 없이 매월 자동 갱신**됩니다:

| 단계 | 동작 |
|---|---|
| 1 | 매월 1일 09:00 KST, GitHub Actions cron 자동 실행 |
| 2 | EU Taxation & Customs CBAM 페이지 스크래핑 |
| 3 | 카테고리 자동 분류 (제목 키워드 휴리스틱) |
| 4 | 한글 제목 자동 생성 (단어 치환 — 약 50개 매핑) |
| 5 | 모든 항목 `important: True`로 추가 (필터링 없이 즉시 표시) |
| 6 | 12개월 초과 항목 자동 제거 |
| 7 | repo에 commit + push → Streamlit Cloud 자동 재배포 |

**소스**: [EU Taxation & Customs CBAM](https://taxation-customs.ec.europa.eu/news_en?f%5B0%5D=topic%3A39)
**한글 번역**: 영문 단어를 매핑된 한글로 부분 치환 (100% 자연스럽지 않을 수 있음).
정확한 의미는 원문 링크 클릭하여 확인.

📝 큐레이션 제안: [GitHub issue](https://github.com/cafeon90-oss/CBAM_calculator/issues)
또는 [email](mailto:cafeon90@gmail.com).
"""
        )


# ────────────── 탭 ⑪ 📘 사용설명서 ──────────────
with tabs[10]:
    st.subheader("📘 사용설명서")

    usage_md, usage_mode = load_usage_md()
    usage_svg, svg_mode = load_usage_svg()

    if usage_mode == "fallback":
        st.warning(
            "⚠️ `USAGE.md` 파일을 찾을 수 없습니다. "
            "GitHub repo에서 직접 보기: "
            "[USAGE.md ↗](https://github.com/cafeon90-oss/CBAM_calculator/blob/main/USAGE.md)"
        )
    else:
        # 1.2 다이어그램 위치에서 SVG로 대체 — markdown은 ![](./xxx.svg) 라서 GitHub에선 보이지만
        # Streamlit에선 직접 SVG render 필요
        usage_md_for_streamlit = usage_md.replace(
            "![CBAM 작동 메커니즘](./cbam_mechanism.svg)\n\n"
            "> 다이어그램이 보이지 않으면 [`cbam_mechanism.svg`](./cbam_mechanism.svg)를 직접 열어보세요.",
            "<!-- SVG는 별도 렌더링 -->",
        )

        # 다이어그램 표시 (SVG 직접 렌더)
        if svg_mode == "auto" and usage_svg:
            # SVG embed (Streamlit 컨테이너 폭 맞춤)
            st.markdown(
                "##### 📊 작동 메커니즘 다이어그램",
            )
            st.markdown(
                f'<div style="background:#0a0d14; border:1px solid #1f2733; '
                f'border-radius:8px; padding:8px; margin: 8px 0 18px 0; '
                f'overflow-x:auto;">{usage_svg}</div>',
                unsafe_allow_html=True,
            )

        # 본문 매뉴얼
        st.markdown(usage_md_for_streamlit)

    # 추가 link
    st.markdown("---")
    st.markdown(
        """
##### 📚 더 알아보기

- 📄 [USAGE.md GitHub에서 보기](https://github.com/cafeon90-oss/CBAM_calculator/blob/main/USAGE.md)
- 📊 [작동 메커니즘 SVG](https://github.com/cafeon90-oss/CBAM_calculator/blob/main/cbam_mechanism.svg)
- 🌫️ [자매 CCUS 도구 라이브 앱](https://ccusamineanalysis-9z3cxdmxmd3muuepqlhaqb.streamlit.app/)
- 📖 [EU CBAM 공식](https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en)
- 📝 [작성자 블로그](https://cdrmaster.tistory.com/)

문의·기여: [GitHub issue](https://github.com/cafeon90-oss/CBAM_calculator/issues) · [email](mailto:cafeon90@gmail.com)
"""
    )


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
        <a href='{CCUS_APP_URL}' target='_blank' style='color:#9b8de8; text-decoration:none;'>🌫️ CCUS 벤치마크 ↗</a>
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
