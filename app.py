"""
비아민계 CO₂ 포집 흡수제 기술 벤치마크 Streamlit 앱
=====================================================

비교 기술 (5종 + MEA 기준):
  0. MEA 30wt% (Baseline 비교용)
  1. K₂CO₃ 계열 (Hot Carbonate / KIERSOL)
  2. 냉각 암모니아 공정 (CAP) — NETL Rev4a B12C
  3. 이중상 용매 (Biphasic / DMX™)
  4. 고체 흡착제 TSA
  5. 칼슘 루핑 (CaL)

데이터 소스:
  - NETL Rev4a Case B12C (Chilled Ammonia 공식 케이스)
  - IEAGHG Technical Reports (Calcium Looping, Biphasic 솔벤트)
  - DOE NETL 고체흡착제 R&D 보고서
  - KIER KIERSOL 파일럿 실증 보고서

지표 정의 (사용자 정의식, 아민 툴과 동일 기준):
  We     [GJe/tCO₂]  = We_thermal(Carnot) + We_elec(펌프·압축·냉동기·보조)
  SPECCA [MJ/tCO₂]   = (SRD×500 + We_elec×2500) / capture
  COCA   [USD/tCO₂]  = (연간 CAPEX + OPEX) / 연간 CO₂ 포집량

실행:
  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# ======================================================================
# 페이지 설정 & 다크모드 / 모바일 CSS
# ======================================================================
st.set_page_config(
    page_title="CO₂ 포집·CCUS 벤치마크",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Streamlit 다크모드 강제 (config.toml 대용)
st.markdown(
    """
<style>
    /* 사이드바 완전 불투명 (모바일 투명도 이슈) */
    section[data-testid="stSidebar"] {
        background-color: #0E1117 !important;
        opacity: 1 !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        background-color: #0E1117 !important;
    }
    section[data-testid="stSidebar"] * {
        background-color: transparent;
    }

    /* 탭 가로 스크롤 (모바일) */
    div[data-baseweb="tab-list"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        scrollbar-width: thin;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar { height: 4px; }
    div[data-baseweb="tab-list"]::-webkit-scrollbar-thumb { background: #4a5160; border-radius: 2px; }
    div[data-baseweb="tab-list"] button { flex-shrink: 0 !important; white-space: nowrap; }

    /* 메트릭 카드 (3단계 축소) */
    div[data-testid="stMetric"] {
        background-color: #1E2128;
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid #2C313C;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.7rem !important;
        color: #8b95a7;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.0rem !important;
        font-weight: 600;
        line-height: 1.2;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 0.7rem !important;
    }

    /* 파일럿 경고 배너 */
    .pilot-warning {
        background: linear-gradient(90deg, #4a3500 0%, #3a2900 100%);
        border-left: 4px solid #ffc107;
        padding: 10px 14px;
        margin: 10px 0;
        border-radius: 4px;
        color: #ffe082;
        font-size: 0.9rem;
    }
    .pilot-warning strong { color: #ffd54f; }

    /* 본문 표 헤더 */
    .stDataFrame thead th { background-color: #1E2128 !important; }

    /* 모바일 폰트 축소 */
    @media (max-width: 640px) {
        h1 { font-size: 1.4rem !important; }
        h2 { font-size: 1.1rem !important; }
        div[data-testid="stMetricValue"] { font-size: 0.9rem !important; }
        div[data-testid="stMetricLabel"] { font-size: 0.65rem !important; }
    }

    /* 그래프 완전 정적화 — 모든 디바이스에서 줌·팬·터치 인터랙션 차단 */
    .js-plotly-plot, .plotly, .plot-container, .main-svg {
        touch-action: pan-y !important;  /* 페이지 세로 스크롤만 허용 */
        -webkit-user-select: none;
        user-select: none;
    }
    /* 모드바·hover 효과 완전 제거 */
    .js-plotly-plot .plotly .modebar,
    .js-plotly-plot .plotly .modebar-container {
        display: none !important;
    }
    .js-plotly-plot * {
        cursor: default !important;
    }

    /* 사이드바 multiselect 칩 — 글자 잘림만 방지 (단순) */
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

    /* 데스크톱에서 사이드바 폭 확대 — 풀네임 한 줄에 들어가게 */
    @media (min-width: 768px) {
        section[data-testid="stSidebar"] {
            min-width: 340px !important;
            width: 340px !important;
        }
        section[data-testid="stSidebar"] > div {
            min-width: 340px !important;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================
# 상수 (사용자식 그대로)
# ======================================================================
SRD_TO_SPECCA = 500     # SPECCA 식 가중치 (사용자 정의)
WE_TO_SPECCA = 2500     # SPECCA 식 가중치 (사용자 정의)
GJ_PER_KWH = 3.6e-3     # GJ/kWh
HOURS_YR = 8760
CF_DEFAULT = 0.85       # capacity factor

# Carnot 보정 (실제 열기관 효율은 Carnot의 ~50~60%)
ETA_CARNOT_FRAC = 0.55  # second-law efficiency

# 단위 환산
USD_PER_MWH_GRID = 80   # 보조전력의 가치 (kWh 가격 환산용)

# 자매 도구 (CBAM 계산기)
CBAM_TOOL_URL = "https://ccusbenchmark-rcuf9appppppppykmyeca8nwgk.streamlit.app/"

# ──────────────────────────────────────────────────────────
# CCS 특화 스케일링 (IEAGHG / NETL 벤치마크 기반)
# 일반 화공의 Lang's rule이 아니라 CCS plant-specific 데이터
# ──────────────────────────────────────────────────────────
REF_CAPTURE_MT_YR = 3.7         # NETL B12C/B12B 기준 규모

# CAPEX scaling (IEAGHG 2007, NETL QGESS — CCS 표준)
CAPEX_SCALE_EXPONENT = 0.65     # CCS 플랜트 평균 (일반 화공 0.7보다 낮음)

# SRD scaling (IEAGHG 2013/04 Solvent R&D Priorities)
# 큰 플랜트일수록 실운영 조건의 SRD ↑ (열손실, 열통합 한계, integration penalty)
SRD_SCALE_PER_DECADE = 0.10     # ±10% per decade of scale (10× → +10%)
SRD_CLIP = (0.85, 1.20)          # 범위 제한

# We_comp scaling (NETL Rev4, IEAGHG 2014)
# 압축기 효율: 소형 왕복식(η~75%) → 대형 다단 원심(η~85%)
# 큰 플랜트일수록 We_comp ↓ (높은 효율)
WE_COMP_SCALE_PER_DECADE = 0.06  # ±6% per decade
WE_COMP_CLIP = (0.85, 1.20)

# Capture rate effect (IEAGHG 2019, NETL "Beyond 90% capture")
# 포집율이 100%에 접근할수록 lean loading의 평형 한계로 SRD/CAPEX 비선형 증가
# Reference: 90% capture (NETL baseline)
REF_CAPTURE_EFF = 0.90
SRD_VS_CAPTURE_COEF = 0.18    # ±18% per decade of (1-η) → 99%에서 약 +18%
CAPEX_VS_CAPTURE_COEF = 0.10  # ±10% per decade — column size 증가
CAPTURE_FACTOR_CLIP = (0.85, 1.35)

# ──────────────────────────────────────────────
# LCA / Lifecycle CO2 Emission Factors
# 출처: IEAGHG 2010-09, NETL 2021 LCA, ISO 14067, Singh et al. 2011, Pour et al. 2018
# ──────────────────────────────────────────────
HEAT_SOURCES = {
    "natural_gas":     {"label": "🔥 천연가스 보일러 (default)", "kgCO2_GJ": 55,
                         "note": "산업 표준, 가장 일반적"},
    "coal_boiler":     {"label": "🔥 석탄 보일러",                "kgCO2_GJ": 100,
                         "note": "구형 발전소·일부 산업"},
    "industrial_waste":{"label": "♻️ 산업 폐열 회수",             "kgCO2_GJ": 5,
                         "note": "거의 zero-emission (열 자체는 폐열)"},
    "electric_heat":   {"label": "⚡ 전기 히트펌프 (grid 의존)",    "kgCO2_GJ": -1,
                         "note": "grid factor × 3.6 / COP_3 자동 계산"},
    "renewable_heat":  {"label": "🌱 재생E 기반 열 (CSP/연료)",   "kgCO2_GJ": 8,
                         "note": "태양열·바이오연료 등"},
    "custom_heat":     {"label": "✏️ Custom",                     "kgCO2_GJ": 55,
                         "note": "사용자 직접 입력"},
}

GRID_FACTORS = {
    "us_avg":     {"label": "🇺🇸 US grid 평균 (default)", "gCO2_kWh": 380},
    "kr_avg":     {"label": "🇰🇷 한국 grid 평균",          "gCO2_kWh": 470},
    "eu_avg":     {"label": "🇪🇺 EU grid 평균",            "gCO2_kWh": 230},
    "uk_avg":     {"label": "🇬🇧 UK grid 평균",            "gCO2_kWh": 200},
    "fr_nuclear": {"label": "🇫🇷 프랑스 (원전 위주)",      "gCO2_kWh": 60},
    "no_hydro":   {"label": "🇳🇴 노르웨이 (수력)",         "gCO2_kWh": 30},
    "renewable":  {"label": "🌱 100% 재생E",                "gCO2_kWh": 20},
    "coal_grid":  {"label": "⚫ 석탄 위주 grid",            "gCO2_kWh": 800},
    "custom_grid":{"label": "✏️ Custom",                    "gCO2_kWh": 380},
}

# 흡수제·소재별 생산 시 배출계수 (kgCO2eq / kg solvent or sorbent produced)
# 출처: Singh 2011, Pour 2018, Strazza 2020, ecoinvent 3.x DB
SOLVENT_EMISSION_FACTORS = {
    "MEA_baseline":   1.4,   # Haber-Bosch NH3 + EO synthesis
    "MHI_KS21":       2.2,   # Hindered amine (복잡 합성)
    "Cansolv_DC103":  2.0,   # 2세대 amine 혼합물
    "Aker_S26":       2.2,   # Proprietary amine blend
    "K2CO3_KIERSOL":  1.2,   # K2CO3 + PZ activator (가중평균)
    "CAP_B12C":       2.2,   # NH3 Haber-Bosch
    "Biphasic_DMX":   2.5,   # 3차 amine 혼합물
    "TSA_Solid":      3.5,   # 아민 함침 MOF/zeolite
    "CaL":            0.10,  # 석회석 caO 자체는 calcination 시 process CO2 별도
                              # Makeup limestone CO2 = 30 kg × 0.65 = 19.5 (이건 LIT loss 자체에 포함됨)
                              # 여기서는 채굴/가공 CF만
}

# Embodied CAPEX 배출계수 (kgCO2 / USD CAPEX 투자, lifetime amortized)
# 출처: NETL 2021 LCA, IPCC AR6 WG3 Annex II
EMBODIED_CO2_PER_USD_CAPEX = 0.20  # 평균: 0.15~0.25 kgCO2/$ for industrial CAPEX

# ======================================================================
# 기술 라이브러리 (LIT) — NETL Rev4a / IEAGHG / DOE / KIER 기반
# ======================================================================
LIT = {
    "MEA_baseline": {
        "name": "MEA 30 wt% (참고)",
        "category": "Amine (ref)",
        "source": "NETL B12B / IEAGHG 2014",
        "status": "commercial",
        "TRL": 9,
        "SRD": 3.60,
        "T_regen": 120,
        "T_abs": 40,
        "p_regen_bar": 1.8,
        "We_pump": 0.012,
        "We_comp": 0.40,
        "We_chill": 0.00,
        "We_aux": 0.05,
        "CAPEX_per_t": 950,
        "OPEX_solvent": 1.5,
        "OPEX_other": 12.0,
        "loss_kg_per_tCO2": 1.5,
        "loss_mech": "산화·열분해 (degradation)",
        "is_pilot": False,
        "notes": "30 wt% MEA + reclaimer. 1세대 표준, 비교 기준선.",
    },
    "MHI_KS21": {
        "name": "MHI KS-21™",
        "category": "Advanced Amine",
        "source": "Mitsubishi Heavy Industries (Petra Nova KS-1 → KS-21)",
        "status": "commercial",
        "TRL": 9,
        "SRD": 2.80,
        "T_regen": 120,
        "T_abs": 40,
        "p_regen_bar": 1.8,
        "We_pump": 0.011,
        "We_comp": 0.40,
        "We_chill": 0.00,
        "We_aux": 0.04,
        "CAPEX_per_t": 920,
        "OPEX_solvent": 1.8,
        "OPEX_other": 12.0,
        "loss_kg_per_tCO2": 0.6,
        "loss_mech": "Hindered amine 구조 → 산화 분해 ↓",
        "is_pilot": False,
        "notes": "MHI 2세대 hindered amine. Petra Nova(KS-1)에서 KS-21로 진화 (2020+). 일본·동남아 적용.",
    },
    "Cansolv_DC103": {
        "name": "Cansolv DC-103",
        "category": "Advanced Amine",
        "source": "Shell Cansolv (NETL 2022 Baseline)",
        "status": "commercial",
        "TRL": 9,
        "SRD": 2.50,
        "T_regen": 110,
        "T_abs": 40,
        "p_regen_bar": 1.8,
        "We_pump": 0.012,
        "We_comp": 0.40,
        "We_chill": 0.00,
        "We_aux": 0.04,
        "CAPEX_per_t": 880,
        "OPEX_solvent": 1.6,
        "OPEX_other": 11.5,
        "loss_kg_per_tCO2": 0.7,
        "loss_mech": "낮은 휘발성, 산화 안정성 ↑",
        "is_pilot": False,
        "notes": "Shell 상용 솔벤트. Boundary Dam (1 Mt/yr 운영). NETL 2022 B11B/B12B/B31B 공식 reference.",
    },
    "Aker_S26": {
        "name": "Aker S26",
        "category": "Advanced Amine",
        "source": "Aker Carbon Capture (Norcem Brevik, Twence)",
        "status": "commercial",
        "TRL": 9,
        "SRD": 2.80,
        "T_regen": 120,
        "T_abs": 40,
        "p_regen_bar": 1.8,
        "We_pump": 0.012,
        "We_comp": 0.40,
        "We_chill": 0.00,
        "We_aux": 0.045,
        "CAPEX_per_t": 1000,
        "OPEX_solvent": 1.7,
        "OPEX_other": 12.5,
        "loss_kg_per_tCO2": 0.8,
        "loss_mech": "낮은 emission, 안정성 ↑",
        "is_pilot": False,
        "notes": "Norcem Brevik (시멘트, 0.4 Mt/yr, 2024 가동), Twence WtE. 유럽 대표 상용 솔벤트.",
    },
    "K2CO3_KIERSOL": {
        "name": "KIERSOL (KIER 한국) †",
        "category": "Hot Carbonate",
        "source": "KIER KIERSOL 파일럿 (Korea Institute of Energy Research)",
        "status": "pilot",
        "TRL": 6,
        "SRD": 2.95,
        "T_regen": 105,
        "T_abs": 70,
        "p_regen_bar": 1.5,
        "We_pump": 0.025,
        "We_comp": 0.38,
        "We_chill": 0.00,
        "We_aux": 0.06,
        "CAPEX_per_t": 1050,
        "OPEX_solvent": 0.8,
        "OPEX_other": 11.0,
        "loss_kg_per_tCO2": 0.5,
        "loss_mech": "촉진제 열화·미량 분해",
        "is_pilot": True,
        "notes": "한국에너지기술연구원(KIER) 자체 개발 솔벤트. "
                 "K₂CO₃ 25-30 wt% + 활성화제 (Piperazine 계열 amine). "
                 "0.5 MWe 파일럿 실증. 70°C warm absorber로 reaction kinetics 보완.",
    },
    "CAP_B12C": {
        "name": "Chilled Ammonia (CAP)",
        "category": "Chilled NH₃",
        "source": "NETL Rev4a Case B12C",
        "status": "demo",
        "TRL": 7,
        "SRD": 2.40,
        "T_regen": 150,
        "T_abs": 5,
        "p_regen_bar": 24.0,
        "We_pump": 0.018,
        "We_comp": 0.18,
        "We_chill": 0.18,
        "We_aux": 0.05,
        "CAPEX_per_t": 1200,
        "OPEX_solvent": 0.6,
        "OPEX_other": 13.0,
        "loss_kg_per_tCO2": 0.3,
        "loss_mech": "NH₃ slip (water wash 회수)",
        "is_pilot": False,
        "notes": "흡수탑 0~10 °C 냉각. 가압 재생 → CO₂ 압축 부하 절감. NETL B12C 공식 케이스.",
    },
    "Biphasic_DMX": {
        "name": "Biphasic DMX™ †",
        "category": "Biphasic",
        "source": "TotalEnergies / IFP-EN / 3D Project",
        "status": "pilot",
        "TRL": 6,
        "SRD": 2.30,
        "T_regen": 155,
        "T_abs": 40,
        "p_regen_bar": 1.8,
        "We_pump": 0.020,
        "We_comp": 0.36,
        "We_chill": 0.00,
        "We_aux": 0.05,
        "CAPEX_per_t": 1100,
        "OPEX_solvent": 1.8,
        "OPEX_other": 12.0,
        "loss_kg_per_tCO2": 1.0,
        "loss_mech": "용매 분해·휘발",
        "is_pilot": True,
        "notes": "상분리 후 CO₂ 농후상만 재생 → 재생 유량 ½. SRD 보정계수 ≈ 0.7 적용.",
    },
    "TSA_Solid": {
        "name": "Solid Sorbent TSA",
        "category": "Solid Sorbent",
        "source": "DOE NETL R&D / SRI / RTI",
        "status": "demo",
        "TRL": 7,
        "SRD": 2.20,
        "T_regen": 110,
        "T_abs": 40,
        "p_regen_bar": 1.2,
        "We_pump": 0.005,
        "We_comp": 0.40,
        "We_chill": 0.00,
        "We_aux": 0.10,
        "CAPEX_per_t": 1300,
        "OPEX_solvent": 2.5,
        "OPEX_other": 10.0,
        "loss_kg_per_tCO2": 2.0,
        "loss_mech": "사이클 열화·마모 (attrition)",
        "is_pilot": False,
        "notes": "고체 흡착제, 무수계, 사이클 시간 변수 영향 大. 분산형 소규모에 유리.",
    },
    "CaL": {
        "name": "Calcium Looping (CaL)",
        "category": "CaO/CaCO₃",
        "source": "IEAGHG 2013/14 CaL Report",
        "status": "demo",
        "TRL": 7,
        "SRD": 3.20,
        "T_regen": 900,
        "T_abs": 650,
        "p_regen_bar": 1.0,
        "We_pump": 0.000,
        "We_comp": 0.36,
        "We_chill": 0.00,
        "We_aux": 0.15,
        "CAPEX_per_t": 850,
        "OPEX_solvent": 1.5,
        "OPEX_other": 14.0,
        "loss_kg_per_tCO2": 30.0,
        "loss_mech": "다회 사이클 비활성화 (CaO sintering)",
        "is_pilot": False,
        "notes": "650/900 °C 고온 순환. 시멘트 산업 통합 가능. ASU 포함 oxy-calcination.",
    },
}

TECH_KEYS = list(LIT.keys())

# ======================================================================
# 레퍼런스 통합 라이브러리 (REFS)
# ======================================================================
REFS = {
    "NETL_Rev4a": {
        "cat": "report",
        "cite": "DOE/NETL (2019). Cost and Performance Baseline for Fossil Energy Plants, "
                "Vol. 1: Bituminous Coal & Natural Gas to Electricity, Rev. 4a. "
                "DOE/NETL-2015/1723. Cases B11A/B11B (NGCC), B12A/B12B (Subcritical PC + MEA), "
                "B12C (Subcritical PC + Chilled Ammonia).",
        "url": "https://netl.doe.gov/projects/files/CostAndPerformanceBaselineForFossilEnergyPlantsVolume1BituminousCoalAndNaturalGasToElectricity.pdf",
        "used_for": "CAP SRD 2.4 GJ/t, 보조전력 분해, COE/COC, MEA baseline",
    },
    "NETL_QGESS": {
        "cat": "report",
        "cite": "DOE/NETL (2021). Quality Guidelines for Energy System Studies (QGESS): "
                "Cost Estimation Methodology for NETL Assessments of Power Plant Performance. "
                "DOE/NETL-2019/2080.",
        "url": "https://netl.doe.gov/energy-analysis/details?id=2710",
        "used_for": "CRF 공식, 할인율 8%, 수명 25년, TPC→COE 변환",
    },
    "IEAGHG_CaL_2013": {
        "cat": "report",
        "cite": "IEAGHG (2013). Deployment of CCS in the Cement Industry. Calcium Looping "
                "Technology Status. Report 2013/19.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "CaL SRD 3.2 GJ/t, makeup limestone 30 kg/tCO₂, calciner 900 °C",
    },
    "IEAGHG_Solvents_2014": {
        "cat": "report",
        "cite": "IEAGHG (2014). Evaluation of Reclaimer Sludge Disposal from Post-Combustion "
                "CO₂ Capture. Report 2014/02.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "MEA reclaimer/loss, 솔벤트 분해 메커니즘",
    },
    "DOE_NETL_Sorbent_Program": {
        "cat": "report",
        "cite": "DOE/NETL Carbon Capture Program (2018). Solid Sorbent Process Designs "
                "for CO₂ Capture from Coal-Fired Power Plants. NETL Carbon Capture R&D.",
        "url": "https://netl.doe.gov/coal/carbon-capture",
        "used_for": "TSA SRD 2.2 GJ/t, attrition rate, blower fluidization 부하",
    },
    "KIER_KIERSOL_2013": {
        "cat": "report",
        "cite": "KIER 한국에너지기술연구원 (2013-2018). KIERSOL 흡수제 파일럿 실증 보고서. "
                "K₂CO₃ 기반 + 활성화제 (Cesar). 0.5 MWe 파일럿.",
        "url": "https://www.kier.re.kr/",
        "used_for": "KIERSOL SRD 2.95 GJ/t, 70 °C 흡수, 활성화제 손실",
    },
    "TotalEnergies_3D": {
        "cat": "report",
        "cite": "3D Project Consortium (2017-2023). DMX™ Demonstration in Dunkirk. "
                "H2020 Grant 838031. TotalEnergies / IFP Energies Nouvelles.",
        "url": "https://www.3d-ccus.com/",
        "used_for": "Biphasic DMX SRD 2.3 GJ/t, 상분리 후 ½ 재생",
    },
    "Rochelle2009": {
        "cat": "paper",
        "cite": "Rochelle, G. T. (2009). Amine Scrubbing for CO₂ Capture. Science, 325(5948), 1652-1654.",
        "url": "https://www.science.org/doi/10.1126/science.1176731",
        "used_for": "MEA SRD 3.6 GJ/t 기준, 솔벤트 화학",
    },
    "Bui2018": {
        "cat": "paper",
        "cite": "Bui, M. et al. (2018). Carbon capture and storage (CCS): the way forward. "
                "Energy & Environmental Science, 11(5), 1062-1176.",
        "url": "https://pubs.rsc.org/en/content/articlehtml/2018/ee/c7ee02342a",
        "used_for": "전기술 SRD 비교 범위, COCA 통합 리뷰",
    },
    "Darde2010": {
        "cat": "paper",
        "cite": "Darde, V., Thomsen, K., van Well, W. J. M., Stenby, E. H. (2010). "
                "Chilled ammonia process for CO₂ capture. International Journal of Greenhouse "
                "Gas Control, 4(2), 131-136.",
        "url": "https://doi.org/10.1016/j.ijggc.2009.10.005",
        "used_for": "CAP SRD 2.0~2.4 범위, 흡수탑 0~10 °C, NH₃ slip",
    },
    "Telikapalli2011": {
        "cat": "paper",
        "cite": "Telikapalli, V., Kozak, F., Francuz, J., Sherrick, B., Black, J., Muraskin, D., "
                "Cage, M., Hammond, M., Spitznogle, G. (2011). CCS with the Alstom Chilled "
                "Ammonia Process Development Program — Field Pilot Results. Energy Procedia, 4, 273-281.",
        "url": "https://doi.org/10.1016/j.egypro.2011.01.052",
        "used_for": "Alstom (현 GE) CAP 파일럿 실증값",
    },
    "Raynal2011": {
        "cat": "paper",
        "cite": "Raynal, L., Bouillon, P. A., Gomez, A., Broutin, P. (2011). From MEA to "
                "demixing solvents and future steps, a roadmap for lowering the cost of "
                "post-combustion carbon capture. Chemical Engineering Journal, 171(3), 742-752.",
        "url": "https://doi.org/10.1016/j.cej.2011.01.008",
        "used_for": "Biphasic DMX 컨셉, SRD 보정계수 0.7",
    },
    "Cullinane2004": {
        "cat": "paper",
        "cite": "Cullinane, J. T., Rochelle, G. T. (2004). Carbon dioxide absorption with aqueous "
                "potassium carbonate promoted by piperazine. Chemical Engineering Science, 59(17), 3619-3630.",
        "url": "https://doi.org/10.1016/j.ces.2004.03.029",
        "used_for": "K₂CO₃ + 활성화제 (PZ) 화학, 반응속도 보완",
    },
    "Yoo2013": {
        "cat": "paper",
        "cite": "Yoo, M. et al. (KIER) (2013). Development of carbon dioxide absorbents for "
                "power plant flue gas. Korean J. Chem. Eng., 30(7), 1497-1503.",
        "url": "https://doi.org/10.1007/s11814-013-0060-5",
        "used_for": "KIERSOL 흡수제 조성 및 성능",
    },
    "Abanades2002": {
        "cat": "paper",
        "cite": "Abanades, J. C. (2002). The maximum capture efficiency of CO₂ using a "
                "carbonation/calcination cycle of CaO/CaCO₃. Chemical Engineering Journal, 90(3), 303-306.",
        "url": "https://doi.org/10.1016/S1385-8947(02)00126-2",
        "used_for": "CaL 사이클 효율, CaO sintering 모델",
    },
    "Grasa2006": {
        "cat": "paper",
        "cite": "Grasa, G. S., Abanades, J. C. (2006). CO₂ capture capacity of CaO in long "
                "series of carbonation/calcination cycles. Industrial & Engineering Chemistry "
                "Research, 45(26), 8846-8851.",
        "url": "https://doi.org/10.1021/ie0606946",
        "used_for": "CaL 비활성화 곡선, makeup limestone 비율",
    },
    "Romeo2008": {
        "cat": "paper",
        "cite": "Romeo, L. M., Abanades, J. C., Escosa, J. M., Paño, J., Giménez, A., "
                "Sánchez-Biezma, A., Ballesteros, J. C. (2008). Oxyfuel carbonation/calcination "
                "cycle for low cost CO₂ capture in existing power plants. "
                "Energy Conversion and Management, 49(10), 2809-2814.",
        "url": "https://doi.org/10.1016/j.enconman.2008.03.022",
        "used_for": "CaL CAPEX, 압축 log-scaling 모델",
    },
    "Lepaumier2009": {
        "cat": "paper",
        "cite": "Lepaumier, H., Picq, D., Carrette, P. L. (2009). New amines for CO₂ capture. "
                "II. Oxidative degradation mechanisms. Industrial & Engineering Chemistry "
                "Research, 48(20), 9068-9075.",
        "url": "https://doi.org/10.1021/ie9004749",
        "used_for": "MEA 1.5 kg/tCO₂ 손실, 산화·열분해 메커니즘",
    },
    "Manzolini2015": {
        "cat": "paper",
        "cite": "Manzolini, G., Macchi, E., Gazzani, M. (2015). CO₂ capture in Integrated "
                "Gasification Combined Cycle with SEWGS — Part B: Economic assessment. Fuel, 161, 209-218.",
        "url": "https://doi.org/10.1016/j.fuel.2015.07.062",
        "used_for": "SPECCA 표준 정의 (literature 비교용)",
    },
    "Bejan2016": {
        "cat": "methodology",
        "cite": "Bejan, A. (2016). Advanced Engineering Thermodynamics, 4th ed. Wiley. "
                "Carnot 효율, 2nd-law efficiency 개념.",
        "url": "https://doi.org/10.1002/9781119245964",
        "used_for": "Carnot η = (T_h-T_c)/T_h, second-law factor",
    },
    "Kotas1985": {
        "cat": "methodology",
        "cite": "Kotas, T. J. (1985). The Exergy Method of Thermal Plant Analysis. "
                "Butterworths. Real-process exergy efficiency typically 40-65% of Carnot.",
        "url": "",
        "used_for": "ETA_CARNOT_FRAC = 0.55 가정 근거",
    },
    "ASHRAE_HVAC": {
        "cat": "methodology",
        "cite": "ASHRAE Handbook — HVAC Systems and Equipment (2020). Chapter on Refrigeration. "
                "Real chiller COP ≈ 0.5-0.6 × inverse-Carnot COP.",
        "url": "https://www.ashrae.org/technical-resources/ashrae-handbook",
        "used_for": "CAP 냉동기 COP_eff = COP_Carnot × 0.55",
    },
    "EIA_AEO_2024": {
        "cat": "methodology",
        "cite": "U.S. Energy Information Administration (2024). Annual Energy Outlook 2024. "
                "Industrial electricity price ~$80/MWh average.",
        "url": "https://www.eia.gov/outlooks/aeo/",
        "used_for": "전기 가격 default 80 USD/MWh",
    },
    "Aspen_NETL": {
        "cat": "methodology",
        "cite": "DOE/NETL (2014). Compression of CO₂ in Carbon Capture & Storage Applications. "
                "Aspen Plus 모델 기반 다단 압축 일.",
        "url": "https://netl.doe.gov/",
        "used_for": "압축 W ∝ log(p_out/p_in) 근사식 (5단 압축 + 중간냉각 가정)",
    },
    "KRX_KAU_2024": {
        "cat": "report",
        "cite": "한국거래소 KRX (2024). 배출권 시장 운영 통계, KAU 시세. "
                "2024년 평균 9,500~10,500 KRW/tCO₂.",
        "url": "https://ets.krx.co.kr/",
        "used_for": "K-ETS default 단가 ($7/t)",
    },
    "ICE_EUA_2024": {
        "cat": "report",
        "cite": "Intercontinental Exchange (ICE) EUA Futures (2024). EU ETS 배출권 시세. "
                "2024년 평균 €70~80/tCO₂.",
        "url": "https://www.ice.com/products/197/EUA-Futures",
        "used_for": "EU ETS default 단가 ($80/t)",
    },
    "IRS_45Q_IRA": {
        "cat": "report",
        "cite": "IRS Notice 2022-38; Inflation Reduction Act 2022, Section 13104. "
                "Section 45Q tax credit: $85/t (CCS), $60/t (EOR/CCU), $180/t (DAC+CCS), "
                "$130/t (DAC+CCU). 12-year credit period.",
        "url": "https://www.irs.gov/credits-deductions/credit-for-carbon-oxide-sequestration",
        "used_for": "US 45Q 보조금 단가 ($85/$60/$180/$130/t)",
    },
    "NL_SDE_2024": {
        "cat": "report",
        "cite": "RVO Netherlands (2024). SDE++ 2024 Round Results. "
                "Stimulering Duurzame Energieproductie en Klimaattransitie. "
                "CCS strike price €100~130/tCO₂.",
        "url": "https://www.rvo.nl/subsidies-financiering/sde",
        "used_for": "NL SDE++ default 단가 ($120/t)",
    },
    "UK_CCUS_BEIS": {
        "cat": "report",
        "cite": "UK BEIS (2023). CCUS Cluster Sequencing — Track 1 & 2 Outcomes. "
                "Industrial CCS DRI/CfD £100~200/tCO₂. £20B 할당.",
        "url": "https://www.gov.uk/government/publications/cluster-sequencing-for-carbon-capture-usage-and-storage-ccus-deployment-phase-1-expressions-of-interest",
        "used_for": "UK CfD default ($180/t)",
    },
    "K_CCUS_Act_2024": {
        "cat": "report",
        "cite": "산업통상자원부 (2024). 「이산화탄소 포집·활용·저장에 관한 법률」 제정. "
                "2024.2 공포, 2024.8 시행. 단가 시행령 미발표.",
        "url": "https://www.motie.go.kr/",
        "used_for": "Korea CCUS Act placeholder (30,000 KRW/t 추정)",
    },
    "IPCC_SR_CCS_2005": {
        "cat": "report",
        "cite": "IPCC (2005). Special Report on Carbon Dioxide Capture and Storage. "
                "Cambridge University Press. CCS chain yield 90~95%.",
        "url": "https://www.ipcc.ch/report/carbon-dioxide-capture-and-storage/",
        "used_for": "CCS 격리수율 92% default, 손실 분해",
    },
    "GCCSI_2023": {
        "cat": "report",
        "cite": "Global CCS Institute (2023). Global Status of CCS 2023. "
                "운영 중 CCS 시설 yield 데이터.",
        "url": "https://www.globalccsinstitute.com/resources/global-status-report/",
        "used_for": "CCS chain yield 검증, CCS:CCU split 통계",
    },
    "CGA_G62_2018": {
        "cat": "methodology",
        "cite": "Compressed Gas Association (CGA) G-6.2 (2018). Commodity Specification for "
                "Carbon Dioxide. Grade A~T 순도 분류 (99.5%~99.9999%).",
        "url": "https://www.cganet.com/",
        "used_for": "CCU 식품·고순도 등급 분류 기준",
    },
    "SEMI_C3": {
        "cat": "methodology",
        "cite": "SEMI C3 (Standard for Carbon Dioxide). Semiconductor 등급 99.999% 이상 사양.",
        "url": "https://www.semi.org/en/standards",
        "used_for": "CCU 초고순도 (99.999%) 사양",
    },
    "Linde_AirLiquide_LCO2": {
        "cat": "report",
        "cite": "Linde / Air Liquide (2020-2023). Industrial CO₂ market data and pricing. "
                "Korea food-grade LCO₂ 250,000~400,000 KRW/t.",
        "url": "",
        "used_for": "CCU 액화탄산 default 가격 (300,000 KRW/t food-grade)",
    },
    "PetersTimmerhaus": {
        "cat": "methodology",
        "cite": "Peters, M. S., Timmerhaus, K. D., West, R. E. (2003). Plant Design and "
                "Economics for Chemical Engineers, 5th ed. McGraw-Hill. "
                "Six-tenths rule (n≈0.6~0.7) for CAPEX scaling.",
        "url": "",
        "used_for": "규모의 경제 일반 화공 표준",
    },
    # ────────────── CCS 특화 스케일링 출처 ──────────────
    "IEAGHG_2007_PostComb": {
        "cat": "report",
        "cite": "IEAGHG (2007). Improvement in Power Generation with Post-Combustion "
                "Capture of CO₂. Report 2004/4 (Updated 2007). "
                "CCS plant CAPEX scaling exponent ≈ 0.65.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "CAPEX 스케일링 n=0.65 (CCS 표준)",
    },
    "IEAGHG_2013_SolventRD": {
        "cat": "report",
        "cite": "IEAGHG (2013). Evaluation of Post-Combustion CO₂ Capture Solvent R&D "
                "Priorities. Report 2013/06. SRD penalty scaling: pilot → commercial "
                "+10~15% due to heat loss, integration limits, real-world penalties.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "SRD 규모 보정 (±10%/decade)",
    },
    "IEAGHG_2014_Solvents": {
        "cat": "report",
        "cite": "IEAGHG (2014). Assessment of Emerging CO₂ Capture Technologies and Their "
                "Potential to Reduce Costs. Report 2014/TR4. Compressor efficiency scaling.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "We_comp 규모 보정 (±6%/decade)",
    },
    "NETL_2022_Baseline": {
        "cat": "report",
        "cite": "DOE/NETL (2022). Cost and Performance Baseline for Fossil Energy Plants — "
                "Cases B11B (SubC PC), B12B (SC PC), B31B (NGCC) with Cansolv DC-103. "
                "DOE/NETL-2023/4320. October 2022. SRD: 3.38~3.56 GJ/tCO₂.",
        "url": "https://netl.doe.gov/energy-analysis/details?id=a8e92d29-b73f-4d80-8b8d-97c1e5654e84",
        "used_for": "최신 commercial-scale CCS 벤치마크 (Cansolv DC-103)",
    },
    "NETL_Rev3_2015": {
        "cat": "report",
        "cite": "DOE/NETL (2015, updated). Cost and Performance Baseline for Fossil Energy "
                "Plants, Revision 3. DOE/NETL-2010/1397. Cansolv DC-103 SRD ≈ 2.56 GJ/tCO₂.",
        "url": "https://netl.doe.gov/projects/files/Rev3FinalReport.pdf",
        "used_for": "Cansolv 솔벤트 SRD 진화 (Rev3)",
    },
    "GPSA_2017": {
        "cat": "methodology",
        "cite": "GPSA (Gas Processors Suppliers Association) (2017). Engineering Data Book, "
                "14th ed. Section 13: Compressors and Expanders. Industry-standard "
                "compressor efficiency curves.",
        "url": "https://gpsamidstreamsuppliers.org/databook",
        "used_for": "압축기 효율 (소형 왕복식 75% → 대형 다단 원심 85%) 표준",
    },
    "IPCC_AR6_WG3_2022": {
        "cat": "report",
        "cite": "IPCC (2022). Climate Change 2022: Mitigation of Climate Change. "
                "Contribution of WG III to the Sixth Assessment Report. Chapter 6, 11 — "
                "CCS/CCU role in 1.5/2°C pathways.",
        "url": "https://www.ipcc.ch/report/ar6/wg3/",
        "used_for": "Climate context, 2050 net-zero CCS deployment scenarios",
    },
    "IEA_CCUS_2023": {
        "cat": "report",
        "cite": "IEA (2023). CCUS Projects Database / CCUS Tracking Report. "
                "Global pipeline ~700 projects, ~400 MtCO₂/yr by 2030.",
        "url": "https://www.iea.org/reports/ccus-in-clean-energy-transitions",
        "used_for": "글로벌 CCUS 동향, 프로젝트 규모 분포",
    },
    "POSCO_KoreanCCS": {
        "cat": "report",
        "cite": "POSCO E&C (2020-2023). 한국 산업 CCS 사례 — 동해가스전 CO₂ 저장 (2030 계획), "
                "현대제철·삼성전자 CCUS 도입 검토.",
        "url": "",
        "used_for": "한국 산업 CCS 적용 맥락 (동해가스전, 시멘트·철강·반도체)",
    },
    "IPCC_SRCCS_Ch5": {
        "cat": "report",
        "cite": "IPCC (2005). Special Report on Carbon Dioxide Capture and Storage, "
                "Chapter 5: Underground Geological Storage. Storage chain loss breakdown: "
                "dehydration -0.5%, compression -1%, pipeline -1.5%, injection -1%.",
        "url": "https://www.ipcc.ch/site/assets/uploads/2018/03/srccs_chapter5-1.pdf",
        "used_for": "CCS 격리 수율 92% 분해 근거 (단계별 손실)",
    },
    "Sjostrom_Krutka_2010": {
        "cat": "paper",
        "cite": "Sjostrom, S., Krutka, H. (2010). Evaluation of solid sorbents as a retrofit "
                "technology for CO₂ capture. Fuel, 89(6), 1298-1306.",
        "url": "https://doi.org/10.1016/j.fuel.2009.11.019",
        "used_for": "TSA solid sorbent attrition rate, cycle stability",
    },
    "Hanak_2015": {
        "cat": "paper",
        "cite": "Hanak, D. P., Anthony, E. J., Manovic, V. (2015). A review of developments "
                "in pilot-plant testing and modelling of calcium looping process. "
                "Energy Environ. Sci., 8(8), 2199-2249.",
        "url": "https://doi.org/10.1039/C5EE01228G",
        "used_for": "CaL 종합 리뷰 (CAPEX, 운전 데이터)",
    },
    "Cousins_2011": {
        "cat": "paper",
        "cite": "Cousins, A., Wardhaugh, L. T., Feron, P. H. M. (2011). A survey of process "
                "flow sheet modifications for energy efficient CO₂ capture from flue gases. "
                "International Journal of Greenhouse Gas Control, 5(4), 605-619.",
        "url": "https://doi.org/10.1016/j.ijggc.2011.01.002",
        "used_for": "MEA 공정 변형 (split flow, intercooling) — SRD 감소 메커니즘",
    },
    # ────────────── Retrofit vs Greenfield CAPEX 출처 ──────────────
    "IEAGHG_2011_Retrofit": {
        "cat": "report",
        "cite": "IEAGHG (2011). Retrofitting CO₂ Capture to Existing Power Plants. "
                "Report 2011/02. Retrofit CAPEX 1.2~1.8× greenfield, site constraints, "
                "tie-in complexity, derating analysis.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "Retrofit 발전소 CAPEX multiplier 1.0× (baseline), "
                    "greenfield 0.75× 근거",
    },
    "NETL_QGESS_Retrofit": {
        "cat": "methodology",
        "cite": "DOE/NETL (2019). Quality Guidelines for Energy System Studies — "
                "Retrofit Cost Estimation Methodology. DOE/NETL-2019/2095. "
                "Site-specific cost factors, brownfield premium 0.85~0.95×.",
        "url": "https://netl.doe.gov/energy-analysis/details?id=4314",
        "used_for": "Retrofit/Brownfield CAPEX 산정 방법론",
    },
    "IEAGHG_2013_Cement": {
        "cat": "report",
        "cite": "IEAGHG (2013). Deployment of CCS in the Cement Industry. Report 2013/19. "
                "Cement retrofit CAPEX $1,500~2,500/(t/yr), low-CO₂ flue gas (12~20%), "
                "small unit scale.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "Retrofit 산업 (시멘트) multiplier 1.65× 근거",
    },
    "Norcem_Brevik_2024": {
        "cat": "report",
        "cite": "Heidelberg Materials / Norcem Brevik CCS Project (2024). "
                "World's first cement plant CCS, 0.4 Mt/yr, ~€500M CAPEX, "
                "Norwegian government 80% funding.",
        "url": "https://www.heidelbergmaterials.com/en/sustainability/ccus",
        "used_for": "시멘트 retrofit 실제 CAPEX 검증",
    },
    "CMU_CAEM_Retrofit": {
        "cat": "paper",
        "cite": "Rubin, E. S., Davison, J. E., Herzog, H. J. (2015). The cost of CO₂ "
                "capture and storage. International Journal of Greenhouse Gas Control, "
                "40, 378-400. CMU CAEM retrofit cost framework.",
        "url": "https://doi.org/10.1016/j.ijggc.2015.05.018",
        "used_for": "Retrofit/Greenfield CAPEX 비교 학술 표준",
    },
    "POSCO_Steel_CCS": {
        "cat": "report",
        "cite": "POSCO E&C (2022-2024). 한국 철강·시멘트 산업 CCS 도입 검토 보고서. "
                "Retrofit ~$1,800~2,400/(t/yr), 한국 산업단지 적용 가능성 분석.",
        "url": "",
        "used_for": "한국 철강·시멘트 retrofit CAPEX 검증",
    },
    "GCCSI_Boundary_Petra": {
        "cat": "report",
        "cite": "Global CCS Institute. Boundary Dam Carbon Capture Project (Saskatchewan, "
                "2014, 1.0 Mt/yr, $1.3B CAD). Petra Nova (Texas, 2017, 1.4 Mt/yr, ~$1B). "
                "공개된 retrofit 실제 CAPEX 데이터.",
        "url": "https://www.globalccsinstitute.com/resources/projects-database/",
        "used_for": "Retrofit 발전소 실제 CAPEX 검증 ($900~1,800/(t/yr))",
    },
    "Northern_Lights_2024": {
        "cat": "report",
        "cite": "Northern Lights JV (Equinor/Shell/TotalEnergies, 2024). 1.5 Mt/yr "
                "transport & storage, ~€800M CAPEX. Greenfield 산업 (blue H₂) 대표 사례.",
        "url": "https://norlights.com/",
        "used_for": "Greenfield 산업 (blue H₂) CAPEX 1.10× 근거",
    },
    # ────────────── Advanced Commercial Amine 출처 ──────────────
    "MHI_KS21_2020": {
        "cat": "report",
        "cite": "Mitsubishi Heavy Industries (2020). KS-21™ Advanced Amine Solvent for CO₂ "
                "Capture. KS-1 후속 (Petra Nova 1.4 Mt/yr 사용). Hindered amine 구조로 "
                "산화 분해 ↓, SRD 2.7~2.9 GJ/tCO₂.",
        "url": "https://www.mhi.com/products/engineering/co2plant.html",
        "used_for": "MHI KS-21 SRD/손실/CAPEX",
    },
    "Cansolv_DC103_Tech": {
        "cat": "report",
        "cite": "Shell Cansolv (2018-2022). DC-103 Solvent Technical Specifications. "
                "NETL 2022 Baseline B11B/B12B/B31B 공식 reference solvent. "
                "Boundary Dam (1.0 Mt/yr) 운영 데이터.",
        "url": "https://www.shell.com/business-customers/catalysts-technologies/",
        "used_for": "Cansolv DC-103 SRD 2.5, NETL B11B/B12B/B31B 직접 매칭",
    },
    "Aker_S26_2023": {
        "cat": "report",
        "cite": "Aker Carbon Capture (2023). Just Catch™ S26 Solvent — Performance Reports. "
                "Norcem Brevik Cement CCS (0.4 Mt/yr, 2024 commissioning), Twence WtE.",
        "url": "https://akercarboncapture.com/",
        "used_for": "Aker S26 SRD 2.8, 시멘트·WtE retrofit 데이터",
    },
    "IEAGHG_2019_99pct": {
        "cat": "report",
        "cite": "IEAGHG (2019). Towards Zero Emissions CCS in Power Plants Using Higher "
                "Capture Rates. Report 2019/02. 90% → 99% 포집율 SRD +15~20%, "
                "CAPEX +8~12% (column size, lean loading 평형 한계).",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "포집율 효과 — SRD ±18%/decade, CAPEX ±10%/decade",
    },
    # ────────────── LCA / Net CO₂ (Lifecycle) 출처 ──────────────
    "IEAGHG_2010_LCA": {
        "cat": "report",
        "cite": "IEAGHG (2010). Environmental Evaluation of CCS — LCA Guidelines. "
                "Report 2010/TR3. CCS lifecycle boundary, scope 1/2/3 정의.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "LCA 평가 framework, scope boundary",
    },
    "EU_CRCF_2024": {
        "cat": "report",
        "cite": "European Commission (2024). Carbon Removal Certification Framework "
                "(CRCF) Regulation. Voluntary credits 등급 산정 (net removed 기준).",
        "url": "https://climate.ec.europa.eu/eu-action/sustainable-carbon-cycles/carbon-removal-certification_en",
        "used_for": "Net removed 기반 voluntary credit 발행 기준",
    },
    "ICVCM_CCP_2023": {
        "cat": "report",
        "cite": "Integrity Council for the Voluntary Carbon Market (2023). "
                "Core Carbon Principles. High-integrity carbon credit 평가 기준.",
        "url": "https://icvcm.org/core-carbon-principles/",
        "used_for": "Voluntary carbon credit 등급 (A~D) 분류 기준",
    },
    "ISO_14067": {
        "cat": "methodology",
        "cite": "ISO 14067:2018. Greenhouse gases — Carbon footprint of products. "
                "LCA scope 1+2+3 산정 표준.",
        "url": "https://www.iso.org/standard/71206.html",
        "used_for": "LCA 산정 ISO 표준",
    },
    "Singh_2011_MEA_LCA": {
        "cat": "paper",
        "cite": "Singh, B., Strømman, A. H., Hertwich, E. (2011). Comparative life cycle "
                "environmental assessment of CCS technologies. International Journal of "
                "Greenhouse Gas Control, 5(4), 911-921. MEA solvent EF 1.4 kgCO₂/kg.",
        "url": "https://doi.org/10.1016/j.ijggc.2011.03.012",
        "used_for": "MEA 흡수제 배출계수 1.4 kgCO₂/kg",
    },
    "Pour_2018_BECCS_LCA": {
        "cat": "paper",
        "cite": "Pour, N., Webley, P. A., Cook, P. J. (2018). Potential for using municipal "
                "solid waste as a resource for bioenergy with carbon capture and storage "
                "(BECCS). International Journal of Greenhouse Gas Control, 68, 1-15.",
        "url": "https://doi.org/10.1016/j.ijggc.2017.11.007",
        "used_for": "BECCS LCA, hindered amine EF 2.2",
    },
    "Strazza_2020_Solvent_LCA": {
        "cat": "paper",
        "cite": "Strazza, C., Magrassi, F., Gallo, M., Del Borghi, A. (2020). Life cycle "
                "assessment of advanced amine solvents for CO₂ capture. Solid sorbent and "
                "MOF emission factors.",
        "url": "https://doi.org/10.1016/j.jclepro.2020.121553",
        "used_for": "솔벤트·고체 흡착제 배출계수 (MOF/zeolite 3.5)",
    },
    "NETL_2021_LCA": {
        "cat": "report",
        "cite": "DOE/NETL (2021). LCA Boundaries for CCS Reporting and Embodied Carbon "
                "in CAPEX. Industrial CAPEX → 0.20 kgCO₂/$ embodied (steel/concrete).",
        "url": "https://netl.doe.gov/energy-analysis/details?id=2710",
        "used_for": "Embodied CAPEX emission factor 0.20 kgCO₂/$",
    },
    "IEA_Electricity_Maps_2024": {
        "cat": "report",
        "cite": "IEA / Electricity Maps (2024). Grid Carbon Intensity Database. "
                "US 380, 한국 470, EU 230, 노르웨이 30 gCO₂/kWh (2024 평균).",
        "url": "https://app.electricitymaps.com/",
        "used_for": "Grid 배출계수 default 값",
    },
    "K_ETS_Act_Art14": {
        "cat": "report",
        "cite": "환경부 (2012-2024). 「온실가스 배출권의 할당 및 거래에 관한 법률」"
                "제14조 (배출량 산정·보고). 「배출량 보고·검증 지침」 환경부 고시 (최신). "
                "할당대상업체가 CO₂ 포집 후 외부 판매(CCU) 시 출하량만큼 보고배출량 차감 가능.",
        "url": "https://www.law.go.kr/lsInfoP.do?lsiSeq=215091",
        "used_for": "한국 K-ETS CCU 차감 제도 — 출하량 × K-ETS 가격 implicit revenue",
    },
}


def ref_link(ref_id: str, label: str = None) -> str:
    """REFS의 항목을 마크다운 링크로 변환"""
    if ref_id not in REFS:
        return f"[{ref_id}]"
    r = REFS[ref_id]
    text = label or ref_id
    if r["url"]:
        return f"[{text}]({r['url']})"
    return text


LIT_REFS = {
    "MEA_baseline":    ["NETL_Rev4a", "NETL_2022_Baseline", "Rochelle2009",
                         "IEAGHG_Solvents_2014", "Lepaumier2009", "Bui2018", "Cousins_2011"],
    "MHI_KS21":        ["MHI_KS21_2020", "GCCSI_Boundary_Petra", "Cousins_2011"],
    "Cansolv_DC103":   ["NETL_2022_Baseline", "Cansolv_DC103_Tech", "GCCSI_Boundary_Petra"],
    "Aker_S26":        ["Aker_S26_2023", "Norcem_Brevik_2024"],
    "K2CO3_KIERSOL":   ["KIER_KIERSOL_2013", "Yoo2013", "Cullinane2004"],
    "CAP_B12C":        ["NETL_Rev4a", "Darde2010", "Telikapalli2011"],
    "Biphasic_DMX":    ["TotalEnergies_3D", "Raynal2011"],
    "TSA_Solid":       ["DOE_NETL_Sorbent_Program", "Sjostrom_Krutka_2010", "Bui2018"],
    "CaL":             ["IEAGHG_CaL_2013", "Abanades2002", "Grasa2006", "Romeo2008", "Hanak_2015"],
}

FORMULA_REFS = {
    "Carnot 효율 η = (T_h - T_c) / T_h":                                              ["Bejan2016"],
    "Second-law factor 0.55":                                                          ["Bejan2016", "Kotas1985"],
    "역카르노 COP = T_c / (T_h - T_c) × 0.55":                                         ["ASHRAE_HVAC"],
    "압축 W ∝ log(p_out / p_in) (5단 + 중간냉각)":                                     ["Aspen_NETL", "Romeo2008"],
    "CRF = i(1+i)^n / [(1+i)^n - 1]":                                                 ["NETL_QGESS"],
    "할인율 8%, 수명 25년 (default)":                                                  ["NETL_QGESS"],
    "전기 가격 80 USD/MWh (default)":                                                   ["EIA_AEO_2024"],
    "SPECCA = (SRD×500 + We_elec×2500) / capture":                                    ["Manzolini2015"],
    "CAP 냉각부하 = SRD × 0.18 휴리스틱":                                               ["NETL_Rev4a", "Darde2010"],
    "CAPEX 규모 효과: ∝ scale^0.65 (CCS specific, ref=3.7 Mt/yr)":                      ["IEAGHG_2007_PostComb", "NETL_QGESS"],
    "SRD 규모 효과: ±10%/decade (파일럿 → 상용 +10%, 메가 +5%)":                         ["IEAGHG_2013_SolventRD"],
    "We_comp 규모 효과: ±6%/decade (소형 왕복식 → 대형 다단 원심)":                       ["IEAGHG_2014_Solvents", "NETL_Rev3_2015"],
    "Retrofit 발전소 multiplier 1.00× (baseline)":                                      ["IEAGHG_2011_Retrofit", "GCCSI_Boundary_Petra"],
    "Greenfield 발전소 multiplier 0.75× (통합 설계 최적화)":                              ["IEAGHG_2011_Retrofit", "NETL_2022_Baseline", "CMU_CAEM_Retrofit"],
    "Greenfield 산업 multiplier 1.10× (blue H₂, LNG)":                                   ["Northern_Lights_2024", "CMU_CAEM_Retrofit"],
    "Retrofit 산업 multiplier 1.65× (시멘트·철강)":                                       ["IEAGHG_2013_Cement", "Norcem_Brevik_2024", "POSCO_Steel_CCS"],
    "Brownfield multiplier 0.90× (부지 재활용)":                                          ["NETL_QGESS_Retrofit"],
    "포집율 효과: SRD ±18%/decade (90% 기준, 99% → +18%)":                                 ["IEAGHG_2019_99pct"],
    "포집율 효과: CAPEX ±10%/decade (column 크기, lean loading 한계)":                      ["IEAGHG_2019_99pct", "NETL_2022_Baseline"],
    "LCA: e_heat = SRD × heat_factor (kgCO₂/GJ)":                                         ["IEAGHG_2010_LCA", "ISO_14067"],
    "LCA: e_elec = We_elec × 277.78 × grid_factor / 1e6":                                 ["IEA_Electricity_Maps_2024"],
    "LCA: e_solvent = loss_kg × emission_factor / 1000":                                  ["Singh_2011_MEA_LCA", "Pour_2018_BECCS_LCA", "Strazza_2020_Solvent_LCA"],
    "LCA: e_embodied = CAPEX × 0.20 / lifetime / 1000":                                   ["NETL_2021_LCA"],
    "Net Removed = Stored - Σ(lifecycle emissions)":                                      ["EU_CRCF_2024", "ICVCM_CCP_2023", "IEAGHG_2010_LCA"],
    "시장 매출 기준 (compliance): 격리량 기준 (gross stored)":                              ["IRS_45Q_IRA", "K_ETS_Act_Art14"],
    "시장 매출 기준 (voluntary, CRCF): net removed 기준":                                   ["EU_CRCF_2024", "ICVCM_CCP_2023"],
    "한국 K-ETS CCU 차감: 보고배출량 차감만 (직접 매출 아님, 조건부 가치)":                    ["K_ETS_Act_Art14"],
}

SHORT_NAMES = {
    "MEA_baseline":   "MEA",
    "MHI_KS21":       "KS-21",
    "Cansolv_DC103":  "DC-103",
    "Aker_S26":       "Aker S26",
    "K2CO3_KIERSOL":  "KIERSOL†",
    "CAP_B12C":       "CAP",
    "Biphasic_DMX":   "DMX†",
    "TSA_Solid":      "TSA",
    "CaL":            "CaL",
}

MATERIALS = {
    "MEA_baseline":   "MEA 30 wt% 수용액 (HOCH₂CH₂NH₂)",
    "MHI_KS21":       "Hindered amine 혼합물 (KS-21™, MHI 2세대)",
    "Cansolv_DC103":  "2세대 amine 혼합물 (Shell Cansolv proprietary)",
    "Aker_S26":       "Aker S26 솔벤트 (proprietary blend)",
    "K2CO3_KIERSOL":  "KIERSOL™ — K₂CO₃ 25~30wt% + Piperazine 계열 활성화제",
    "CAP_B12C":       "NH₃ 28 wt% 수용액 (0~10 °C 냉각)",
    "Biphasic_DMX":   "3차 아민 혼합액 (DMX™, 상분리형)",
    "TSA_Solid":      "고체 흡착제 (아민 함침/제올라이트/MOF)",
    "CaL":            "CaO ⇌ CaCO₃ (석회석 기원, 고체)",
}

CCU_GRADES = {
    "food":    {"label": "식품·음료급 (99.9%)",     "purity": 99.9,
                "yield": 0.88, "price_krw_t": 300_000, "capex_mult": 1.05},
    "high":    {"label": "고순도 (99.99%)",         "purity": 99.99,
                "yield": 0.82, "price_krw_t": 450_000, "capex_mult": 1.25},
    "ultra":   {"label": "초고순도 반도체/의료 (99.999%)", "purity": 99.999,
                "yield": 0.75, "price_krw_t": 700_000, "capex_mult": 1.65},
}

# ────────────── 시나리오 프리셋 (Quick Start) ──────────────
PRESETS = {
    "us_petra_nova": {
        "label": "🇺🇸 미국 발전소 retrofit + 45Q (Petra Nova형)",
        "description": "1.4 Mt/yr 석탄 발전소 retrofit · 45Q-CCS + EOR 매출",
        "techs": ["MEA_baseline", "K2CO3_KIERSOL", "CAP_B12C"],
        "settings": {
            "capture_mt_yr": 1.4, "facility_mode": "CCS",
            "project_scenario": "retrofit_power",
            "cm_select": "None", "sub_select": "45Q-CCS",
            "sub_price_45Q-CCS": 85.0, "extra_rev": 30.0,
        },
    },
    "kr_cement": {
        "label": "🇰🇷 한국 시멘트 산업 retrofit (POSCO형)",
        "description": "0.5 Mt/yr 시멘트 retrofit · K-ETS + K-CCUS Act",
        "techs": ["MEA_baseline", "CaL"],
        "settings": {
            "capture_mt_yr": 0.5, "facility_mode": "CCS",
            "project_scenario": "retrofit_industrial",
            "cm_select": "K-ETS", "cm_price_K-ETS": 7.0,
            "sub_select": "K-CCUS-est", "sub_price_K-CCUS-est": 21.0,
            "extra_rev": 0.0,
        },
    },
    "eu_blue_h2": {
        "label": "🇪🇺 EU 블루수소 greenfield + SDE++",
        "description": "1.5 Mt/yr 신규 산업 + 네덜란드 SDE++ (€110/t)",
        "techs": ["MEA_baseline", "CAP_B12C", "Biphasic_DMX"],
        "settings": {
            "capture_mt_yr": 1.5, "facility_mode": "CCS",
            "project_scenario": "greenfield_industrial",
            "cm_select": "None", "sub_select": "NL-SDE",
            "sub_price_NL-SDE": 120.0, "extra_rev": 0.0,
        },
    },
    "us_dac_lcfs": {
        "label": "🇺🇸 미국 DAC + LCFS (Carbon Engineering형)",
        "description": "0.5 Mt/yr DAC급 · 45Q-DAC $180 + LCFS $150",
        "techs": ["MEA_baseline", "CAP_B12C", "TSA_Solid"],
        "settings": {
            "capture_mt_yr": 0.5, "facility_mode": "CCS",
            "project_scenario": "greenfield_industrial",
            "cm_select": "CA-CAT", "cm_price_CA-CAT": 30.0,
            "sub_select": "Custom_subsidy", "sub_custom": 180.0,
            "extra_rev": 150.0,
        },
    },
    "kr_food_lco2": {
        "label": "🇰🇷 한국 식품급 액화탄산 (300천원/t)",
        "description": "0.3 Mt/yr CCU · 식품급 99.9% · 무보조금",
        "techs": ["MEA_baseline", "K2CO3_KIERSOL"],
        "settings": {
            "capture_mt_yr": 0.3, "facility_mode": "CCU",
            "project_scenario": "greenfield_industrial",
            "ccu_grade": "food", "ccu_price_krw": 300_000,
            "sub_select": "None", "extra_rev": 0.0,
        },
    },
    "kr_ultra_lco2": {
        "label": "🇰🇷 반도체 초고순도 LCO₂ (700천원/t)",
        "description": "0.05 Mt/yr 소규모 CCU · 초고순도 99.999%",
        "techs": ["MEA_baseline", "CAP_B12C", "TSA_Solid"],
        "settings": {
            "capture_mt_yr": 0.05, "facility_mode": "CCU",
            "project_scenario": "greenfield_industrial",
            "ccu_grade": "ultra", "ccu_price_krw": 700_000,
            "sub_select": "None", "extra_rev": 0.0,
        },
    },
}


def apply_preset():
    """프리셋 선택 시 모든 입력값을 자동 세팅"""
    preset_key = st.session_state.get("preset_select")
    if not preset_key or preset_key == "custom":
        return
    preset = PRESETS.get(preset_key)
    if not preset:
        return
    # 설정값 적용
    for k, v in preset["settings"].items():
        st.session_state[k] = v
    # 선택 기술 적용
    st.session_state["selected_techs"] = preset["techs"]


# ────────────── 통화 표시 헬퍼 ──────────────
def fmt_money(usd_amount, fx, mode="Both", per_t=False):
    """
    통화 표시 헬퍼.
    mode: "USD" | "KRW" | "Both"
    per_t: True면 단위 톤당 (KRW 단위로 원/t 표기), False면 총액 (억원/조원 자동)
    """
    if per_t:
        krw_str = f"{usd_amount * fx:+,.0f} 원/t" if usd_amount < 0 else f"{usd_amount * fx:,.0f} 원/t"
        usd_str = f"${usd_amount:+,.1f}/t" if usd_amount < 0 else f"${usd_amount:,.1f}/t"
    else:
        krw_str = fmt_krw_amt(usd_amount * fx, sign=usd_amount < 0)
        usd_str = f"${usd_amount/1e6:+,.1f}M" if usd_amount < 0 else f"${usd_amount/1e6:,.1f}M"
    if mode == "USD":
        return usd_str
    if mode == "KRW":
        return krw_str
    return f"{usd_str} ({krw_str})"


# ────────────── 호버 툴팁용 정의 (계산식·출처 포함) ──────────────
TOOLTIPS = {
    "SRD": (
        "Specific Reboiler Duty — 흡수제 재생탑 reboiler 열부하 [GJ/tCO₂]\n"
        "■ 계산: LIT base × 규모 보정(±10%/decade) × 포집율 효과\n"
        "■ 규모: 큰 플랜트일수록 +SRD (실운영 비효율, 열통합 한계)\n"
        "■ 포집율: 90%→99% 시 +18% (평형 한계)\n"
        "■ 출처: NETL Rev4a/2022 B12B, IEAGHG 2013/04 (Solvent R&D), IEAGHG 2019"
    ),
    "We": (
        "Equivalent Work — 전력등가 일 [GJe/tCO₂]\n"
        "■ 계산: We_thermal(Carnot) + 펌프 + CO₂ 압축 + 냉동기(CAP) + 보조\n"
        "■ We_thermal = SRD × Carnot η × 0.55 (second-law factor)\n"
        "■ Carnot η = (T_regen − T_cool) / T_regen (절대온도 K)\n"
        "■ 압축: log(p_final/p_regen) × We_comp_LIT (5단 + intercool)\n"
        "■ CAP 냉동기: Q_chill / COP_eff (역카르노 × 0.55)\n"
        "■ 출처: Bejan 2016, Kotas 1985, ASHRAE, NETL Aspen"
    ),
    "SPECCA": (
        "Specific Primary Energy Consumption for CO₂ Avoided [MJ/tCO₂]\n"
        "■ 계산: (SRD × 500 + We_elec × 2,500) / capture_rate\n"
        "■ 가중치 500/2500: 1차 에너지(steam/elec) 환산\n"
        "■ 포집율로 정규화 (다른 포집율 기술 간 비교)\n"
        "■ 출처: Manzolini et al. 2015 변형식"
    ),
    "COCA": (
        "Cost Of CO₂ Captured — 단위 CO₂당 종합 비용 [USD/tCO₂]\n"
        "■ 계산: 연환산 CAPEX + OPEX(용매 + 기타 + 전력)\n"
        "■ CAPEX 적용: LIT × project type × 포집율 × 규모(0.65) × CCU adder\n"
        "■ 연환산 CAPEX = CAPEX × CRF\n"
        "■ CRF = i(1+i)ⁿ/[(1+i)ⁿ-1], default 8%/25년 = 0.0937\n"
        "■ 출처: NETL QGESS 2019, IEAGHG 2007, Peters & Timmerhaus"
    ),
    "Net COCA": (
        "Net COCA = COCA − 매출/보조금 [USD/tCO₂]\n"
        "■ 음수 = 흑자, 양수 = 적자\n"
        "■ 매출 = 배출권 + 정부보조금 + LCFS + CCU 매출(액화탄산)\n"
        "■ 격리량 기준 (CCS) 또는 출하량 기준 (CCU) 적용\n"
        "■ 다중 인센티브 stacking 가능 (45Q + 주별 시장 + LCFS)"
    ),
    "CRF": (
        "Capital Recovery Factor — 연환산 자본금 비율\n"
        "■ CRF = i(1+i)ⁿ / [(1+i)ⁿ - 1]\n"
        "■ default i=8%, n=25년 → CRF = 0.0937\n"
        "■ 출처: NETL QGESS Cost Methodology"
    ),
    "Carnot": (
        "이론 열기관 효율 = (T_hot − T_cold) / T_hot (절대온도 K)\n"
        "■ 열을 일로 바꾸는 thermodynamic 한계\n"
        "■ 실효 효율 = Carnot η × 0.55 (second-law factor)\n"
        "■ 출처: Bejan 2016, Kotas 1985"
    ),
    "LCFS": (
        "Low Carbon Fuel Standard\n"
        "■ 캘리포니아 운송연료 탄소집약도 인센티브\n"
        "■ DAC pathway: ~$150/tCO₂\n"
        "■ Voluntary credits (Stripe/Frontier): $200~600/tCO₂\n"
        "■ 출처: California ARB LCFS Program"
    ),
    "NPV": (
        "Net Present Value — 순현재가치 [USD]\n"
        "■ 계산: NPV = Σ CF_t / (1+r)^t,  t=0..N\n"
        "■ t=0: -CAPEX, t=1..lifetime: 연 손익\n"
        "■ NPV > 0 → 사업성 있음, NPV < 0 → 손실\n"
        "■ 할인율 r = default 8% (NETL QGESS)"
    ),
    "IRR": (
        "Internal Rate of Return — 내부수익률 [%]\n"
        "■ NPV = 0이 되는 할인율\n"
        "■ IRR > 할인율 (8%) → 양호\n"
        "■ CCUS 평균 IRR: -5% ~ +15% (인센티브 의존)\n"
        "■ 본 모델: bisection 수치해법"
    ),
    "TRL": (
        "Technology Readiness Level — 기술 성숙도 (1~9)\n"
        "■ NASA 표준, EU·IEA 채택\n"
        "■ TRL 9: 상용 (다수 운영 사례)\n"
        "■ TRL 7-8: Demo (대규모 실증)\n"
        "■ TRL 5-6: Pilot (중·소형 실증)\n"
        "■ ⚠️ 낮은 TRL = idealized 데이터 경향 (+10~20% 페널티)"
    ),
}


def tip(term: str, label: str = None) -> str:
    """HTML abbr 태그로 호버 툴팁 적용"""
    desc = TOOLTIPS.get(term, "")
    text = label or term
    if desc:
        return f"<abbr title=\"{desc}\" style=\"text-decoration: underline dotted; cursor: help;\">{text}</abbr>"
    return text


# ────────────── 프로젝트 시나리오 (CAPEX scope + multiplier) ──────────────
# 출처: IEAGHG 2011/02, NETL QGESS Retrofit, Bui 2018, GCCSI 2023
PROJECT_SCENARIOS = {
    "retrofit_power": {
        "label": "🔧 Retrofit 발전소 (default)",
        "multiplier": 1.00,
        "scope": "기존 발전소에 CCS 추가",
        "examples": "Boundary Dam, Petra Nova, AEP Mountaineer",
        "color": "#FFB74D",
    },
    "greenfield_power": {
        "label": "🏭 Greenfield 발전소 (신규)",
        "multiplier": 0.75,
        "scope": "발전소 + CCS 동시 신축, 통합 설계 최적화",
        "examples": "NETL B12B SC PC 신규, FutureGen-style",
        "color": "#81C784",
    },
    "greenfield_industrial": {
        "label": "🏗️ Greenfield 산업 (수소·LNG)",
        "multiplier": 1.10,
        "scope": "신규 산업시설 + CCS",
        "examples": "Northern Lights, Blue H₂ 신축, Quest",
        "color": "#4FC3F7",
    },
    "retrofit_industrial": {
        "label": "🔩 Retrofit 산업 (시멘트·철강)",
        "multiplier": 1.65,
        "scope": "저농도/불순물 flue gas, 소규모 + 공정 통합 어려움",
        "examples": "Norcem Brevik, POSCO 철강, 시멘트 retrofit",
        "color": "#E57373",
    },
    "brownfield": {
        "label": "🏘️ Brownfield (부지 재활용)",
        "multiplier": 0.90,
        "scope": "폐기 시설 부지 재활용 (기존 인프라 일부 활용)",
        "examples": "폐탄광 EOR, 기존 산업단지 전환",
        "color": "#BA68C8",
    },
}


CARBON_MARKETS = {
    "K-ETS":      {"label": "🇰🇷 K-ETS (한국)",            "type": "credit",   "price_usd_t": 7.0,   "native": "10,000 KRW/t",        "region": "KR"},
    "EU-ETS":     {"label": "🇪🇺 EU ETS (유럽)",           "type": "credit",   "price_usd_t": 80.0,  "native": "€75/t",               "region": "EU"},
    "RGGI":       {"label": "🇺🇸 RGGI (미 동부)",           "type": "credit",   "price_usd_t": 20.0,  "native": "$20/t",               "region": "US"},
    "CA-CAT":     {"label": "🇺🇸 CA Cap-Trade (캘리포니아)", "type": "credit",   "price_usd_t": 30.0,  "native": "$30/t",               "region": "US"},
    "45Q-CCS":    {"label": "🇺🇸 US 45Q — CCS 지중저장",    "type": "subsidy",  "price_usd_t": 85.0,  "native": "$85/t (12yr)",        "region": "US"},
    "45Q-EOR":    {"label": "🇺🇸 US 45Q — CCU/EOR",        "type": "subsidy",  "price_usd_t": 60.0,  "native": "$60/t (12yr)",        "region": "US"},
    "NL-SDE":     {"label": "🇳🇱 NL SDE++ (네덜란드)",      "type": "subsidy",  "price_usd_t": 120.0, "native": "€110/t",              "region": "EU"},
    "UK-CfD":     {"label": "🇬🇧 UK CCUS CfD",              "type": "subsidy",  "price_usd_t": 180.0, "native": "£150/t",              "region": "UK"},
    "K-CCUS-est": {"label": "🇰🇷 Korea CCUS Act (추정)",   "type": "subsidy",  "price_usd_t": 21.0,  "native": "30,000 KRW/t (placeholder)", "region": "KR"},
    "Custom":     {"label": "✏️ Custom 입력",                "type": "credit",   "price_usd_t": 0.0,   "native": "—",                   "region": "ANY"},
}


# 지역별 정적 색상 그룹 (양 dropdown 동일 — 같은 색끼리만 stack 가능)
REGION_COLORS = {
    "US": "🟦",   # 미국
    "EU": "🟨",   # 유럽 / NL
    "UK": "🟪",   # 영국
    "KR": "🟧",   # 한국
    "ANY": "⚪",  # 없음 / Custom
}


def region_icon(key: str) -> str:
    """LIT 키 → 지역 색깔 이모지 (정적, 다른 선택과 무관)"""
    if key in ("None", "Custom", "Custom_subsidy", None):
        return "⚪"
    region = CARBON_MARKETS.get(key, {}).get("region", "ANY")
    return REGION_COLORS.get(region, "⚪")

# ────────────── 기술별 실용적 capacity 범위 (Mt/yr) ──────────────
# 출처: GCCSI 2023, IEAGHG 2014, NETL Rev4a, 각 기술 운영 사례
CAPACITY_RANGE = {
    "MEA_baseline":   (0.1,  10.0),    # 광범위, 검증된 상용
    "MHI_KS21":       (0.5,  10.0),    # 대형 발전소 retrofit
    "Cansolv_DC103":  (0.5,  10.0),    # Boundary Dam 1 Mt 입증
    "Aker_S26":       (0.1,   5.0),    # 시멘트~중형 발전소
    "K2CO3_KIERSOL":  (0.05,  1.0),    # 파일럿 스케일 (KIER 0.5 MWe)
    "CAP_B12C":       (1.0,   5.0),    # 대형 (냉동 cycle 경제성)
    "Biphasic_DMX":   (0.05,  2.0),    # 파일럿~중규모 (3D Project)
    "TSA_Solid":      (0.01,  1.0),    # 분산형 소규모 적합
    "CaL":            (0.5,   5.0),    # 시멘트 산업 통합
}


def trl_group(trl: int) -> str:
    """TRL → 그룹 라벨 (필터·시각화용)"""
    if trl >= 9:
        return "🟢 TRL 9 (상용)"
    if trl >= 7:
        return "🟡 TRL 7-8 (Demo)"
    return "🟠 TRL ≤6 (Pilot/연구)"


def trl_group_color(trl: int) -> str:
    if trl >= 9:
        return "#81C784"   # 녹색
    if trl >= 7:
        return "#FFB74D"   # 주황
    return "#E57373"        # 빨강


def short_name(key_or_name: str) -> str:
    if key_or_name in SHORT_NAMES:
        return SHORT_NAMES[key_or_name]
    for k, t in LIT.items():
        if t["name"] == key_or_name:
            return SHORT_NAMES.get(k, key_or_name)
    return key_or_name


def fmt_krw_amt(krw: float, sign: bool = False) -> str:
    """
    원화 금액을 한국식 단위로 자동 변환.
      < 1조원      → 억원 (예: 18.6억원, 186억원, 9,500억원)
      ≥ 1조원      → 조원 (예: 1.52조원, 15.20조원)
    sign=True 면 +/- 부호 강제 표시.
    """
    abs_krw = abs(krw)
    if abs_krw >= 1e12:
        val = krw / 1e12
        prec = 2
        unit = "조원"
    else:
        val = krw / 1e8
        # 100억 이상은 정수, 미만은 소수 1자리
        prec = 0 if abs(val) >= 100 else 1
        unit = "억원"
    s = f"{val:+,.{prec}f}" if sign else f"{val:,.{prec}f}"
    return f"{s}{unit}"


def fmt_krw_per_t(krw_per_t: float, sign: bool = False) -> str:
    """단위 CO₂당 원화 (보통 만원~수십만원 단위) — 그냥 원/t 표기 + 천단위 쉼표"""
    s = f"{krw_per_t:+,.0f}" if sign else f"{krw_per_t:,.0f}"
    return f"{s} 원/t"


CHART_MARGIN = dict(l=10, r=10, t=50, b=80)
CHART_MARGIN_STACK = dict(l=10, r=10, t=50, b=120)

# 그래프 완전 정적화: 줌·팬·더블클릭·호버·툴바 모두 비활성
# (모바일에서 터치 시 의도치 않은 줌/팬 방지 — 정적 이미지처럼 동작)
PLOTLY_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showTips": False,
    "displaylogo": False,
    "staticPlot": True,           # 완전 정적 — 모든 인터랙션 차단
    "showAxisDragHandles": False,
    "showAxisRangeEntryBoxes": False,
    "responsive": True,            # 화면 크기 따라 반응 (정적 + 반응형)
}

# ======================================================================
# 계산 함수
# ======================================================================
def carnot_efficiency(T_hot_C: float, T_cold_C: float) -> float:
    Th = T_hot_C + 273.15
    Tc = T_cold_C + 273.15
    if Th <= Tc:
        return 0.0
    return (Th - Tc) / Th


def chiller_We(Q_chill_GJ: float, T_abs_C: float, T_amb_C: float) -> float:
    Tc = T_abs_C + 273.15
    Th = T_amb_C + 273.15 + 10
    if Th <= Tc:
        return 0.0
    cop_carnot = Tc / (Th - Tc)
    cop_eff = max(cop_carnot * ETA_CARNOT_FRAC, 1.0)
    return Q_chill_GJ / cop_eff


def calc_We(tech: dict, T_cool_C: float, p_final_bar: float,
            capture_t_yr: float = REF_CAPTURE_MT_YR * 1e6,
            capture_eff: float = REF_CAPTURE_EFF) -> dict:
    """
    보정 적용:
      SRD     → 규모 (IEAGHG 2013/04) + 포집율 (IEAGHG 2019)
      We_comp → 규모 (NETL Rev4 / IEAGHG 2014)
    """
    # 1) 규모 효과 적용 (SRD, We_comp)
    srd_scaled = scale_srd(tech["SRD"], capture_t_yr)
    we_comp_scaled = scale_we_comp(tech["We_comp"], capture_t_yr)
    # 2) 포집율 효과 적용 (SRD에만 — 99% 접근 시 비선형 ↑)
    srd_capture_factor = capture_rate_factor(capture_eff, SRD_VS_CAPTURE_COEF)
    srd_scaled = srd_scaled * srd_capture_factor

    # 2) 열의 전기등가
    eta_c = carnot_efficiency(tech["T_regen"], T_cool_C) * ETA_CARNOT_FRAC
    We_thermal_eq = srd_scaled * eta_c

    # 3) 압축 — 최종 압력 보정
    base_p = 152.0
    p_factor = np.log(p_final_bar / tech["p_regen_bar"]) / np.log(base_p / 1.8)
    p_factor = max(p_factor, 0.3)
    we_comp_eff = we_comp_scaled * p_factor

    # 4) 냉동기 (CAP만 동적)
    if tech["category"] == "Chilled NH₃":
        Q_chill = srd_scaled * 0.18
        we_chill_eff = chiller_We(Q_chill, tech["T_abs"], T_cool_C)
    else:
        we_chill_eff = tech.get("We_chill", 0.0)

    we_pump = tech["We_pump"]
    we_aux = tech["We_aux"]

    We_elec = we_pump + we_comp_eff + we_chill_eff + we_aux
    We_total = We_thermal_eq + We_elec

    return {
        "SRD_scaled": srd_scaled,
        "SRD_base": tech["SRD"],
        "srd_scale_pct": (srd_scaled / tech["SRD"] - 1) * 100,
        "srd_capture_factor": srd_capture_factor,
        "srd_capture_pct": (srd_capture_factor - 1) * 100,
        "We_comp_scale_pct": (we_comp_scaled / tech["We_comp"] - 1) * 100 if tech["We_comp"] > 0 else 0,
        "We_thermal_eq": We_thermal_eq,
        "We_pump": we_pump,
        "We_comp": we_comp_eff,
        "We_chill": we_chill_eff,
        "We_aux": we_aux,
        "We_elec": We_elec,
        "We_total": We_total,
    }


def calc_SPECCA(srd: float, we_elec: float, capture: float) -> float:
    if capture <= 0:
        return float("nan")
    return (srd * SRD_TO_SPECCA + we_elec * WE_TO_SPECCA) / capture


def scale_capex_per_t(capex_per_t: float, capture_t_yr: float,
                       ref_t_yr: float = REF_CAPTURE_MT_YR * 1e6,
                       n: float = CAPEX_SCALE_EXPONENT) -> float:
    """
    CAPEX 규모 효과 (IEAGHG 2007, NETL QGESS — CCS 표준 n=0.65).
    CAPEX_per_t = CAPEX_ref × (ref / actual)^(1-n)
    큰 플랜트일수록 단위 톤당 CAPEX 감소.
    """
    if capture_t_yr <= 0:
        return capex_per_t
    return capex_per_t * (ref_t_yr / capture_t_yr) ** (1 - n)


def scale_srd(srd_ref: float, capture_t_yr: float,
              ref_t_yr: float = REF_CAPTURE_MT_YR * 1e6) -> float:
    """
    SRD 규모 효과 (IEAGHG 2013/04 Solvent R&D Priorities).
    파일럿(idealized) → 상용 이행 시 SRD ↑ (실운영 비효율).
      log10(scale/ref) × 10% per decade
      0.1× ref(파일럿) → SRD -10% (idealized)
      1× ref           → SRD ref
      10× ref(메가)    → SRD +10% (real-world penalty)
    """
    if capture_t_yr <= 0 or srd_ref <= 0:
        return srd_ref
    log_ratio = np.log10(capture_t_yr / ref_t_yr)
    factor = 1 + SRD_SCALE_PER_DECADE * log_ratio
    factor = max(SRD_CLIP[0], min(factor, SRD_CLIP[1]))
    return srd_ref * factor


def scale_we_comp(we_comp_ref: float, capture_t_yr: float,
                  ref_t_yr: float = REF_CAPTURE_MT_YR * 1e6) -> float:
    """
    압축기 We 규모 효과 (NETL Rev4, IEAGHG 2014).
    소형(왕복식 η~75%) → 대형(다단 원심 η~85%).
      log10(ref/scale) × 6% per decade
      0.1× ref → +6% (낮은 효율)
      1× ref   → ref
      10× ref  → -6% (높은 효율)
    """
    if capture_t_yr <= 0 or we_comp_ref <= 0:
        return we_comp_ref
    log_ratio = np.log10(ref_t_yr / capture_t_yr)
    factor = 1 + WE_COMP_SCALE_PER_DECADE * log_ratio
    factor = max(WE_COMP_CLIP[0], min(factor, WE_COMP_CLIP[1]))
    return we_comp_ref * factor


def capture_rate_factor(capture_eff: float, coef: float) -> float:
    """
    포집율(capture rate) 효과 (IEAGHG 2019, NETL "Beyond 90% capture").
      factor = 1 + coef × log10((1-0.9) / (1-η))
      90% capture → 1.0 (baseline)
      99% capture → 1 + coef × 1.0 (큰 폭 증가)
      70% capture → 1 + coef × log10(0.1/0.3) ≈ 1 - 0.48×coef
    포집율 → 100% 접근 시 평형 driving force 감소로 SRD·CAPEX ↑
    """
    if capture_eff <= 0 or capture_eff >= 1:
        return 1.0
    if abs(capture_eff - REF_CAPTURE_EFF) < 1e-6:
        return 1.0
    log_ratio = np.log10((1 - REF_CAPTURE_EFF) / (1 - capture_eff))
    factor = 1 + coef * log_ratio
    return max(CAPTURE_FACTOR_CLIP[0], min(factor, CAPTURE_FACTOR_CLIP[1]))


def calc_COCA(
    capex_per_t, opex_solvent, opex_other, we_elec, capture_t_yr,
    lifetime_yr=25, discount=0.08, elec_price_usd_mwh=USD_PER_MWH_GRID,
    capex_mult=1.0, ccu_share=0.0, project_multiplier=1.0,
    capture_eff=REF_CAPTURE_EFF,
) -> dict:
    """
    CAPEX 적용 순서:
      1) LIT base × project_multiplier (retrofit/greenfield 시나리오)
      2) × 포집율 효과 (90% 기준, 99% → +10%, 70% → -5%)
      3) 규모의 경제 (Lang's n=0.65)
      4) CCU 정제 등급 CAPEX adder
    """
    # 1) 프로젝트 시나리오 보정 (retrofit/greenfield/industrial)
    project_capex_per_t = capex_per_t * project_multiplier
    # 2) 포집율 효과 — 90% baseline, 99% 접근 시 column 크기 ↑
    capture_factor = capture_rate_factor(capture_eff, CAPEX_VS_CAPTURE_COEF)
    project_capex_per_t = project_capex_per_t * capture_factor
    # 3) 규모의 경제 적용 (NETL B12C 3.7 Mt/yr 대비)
    scaled_capex_per_t = scale_capex_per_t(project_capex_per_t, capture_t_yr)
    # 4) CCU 정제 등급 CAPEX adder
    eff_capex_per_t = scaled_capex_per_t * (1 + ccu_share * (capex_mult - 1))

    crf = (discount * (1 + discount) ** lifetime_yr) / ((1 + discount) ** lifetime_yr - 1)
    annual_capex_usd_per_t = eff_capex_per_t * crf
    elec_cost = we_elec * 277.78 / 1000 * elec_price_usd_mwh
    opex_total = opex_solvent + opex_other + elec_cost
    coca = annual_capex_usd_per_t + opex_total

    scale_factor = scaled_capex_per_t / project_capex_per_t if project_capex_per_t > 0 else 1.0

    return {
        "base_capex_per_t":     capex_per_t,            # LIT 원본
        "project_capex_per_t":  project_capex_per_t,    # × project × capture rate
        "scaled_capex_per_t":   scaled_capex_per_t,     # × 규모 보정
        "eff_capex_per_t":      eff_capex_per_t,        # + CCU adder
        "project_multiplier":   project_multiplier,
        "capex_capture_factor": capture_factor,         # 포집율 효과 (CAPEX)
        "scale_factor":         scale_factor,
        "capex_adder":          eff_capex_per_t - scaled_capex_per_t,
        "annual_capex":         annual_capex_usd_per_t,
        "opex_solvent":         opex_solvent,
        "opex_other":           opex_other,
        "elec_cost":            elec_cost,
        "opex_total":           opex_total,
        "COCA":                 coca,
        "annual_total_usd":     coca * capture_t_yr,
    }


def calc_financial_metrics(annual_cf_usd: float, capex_total_usd: float,
                             lifetime_yr: int = 25, discount: float = 0.08) -> dict:
    """
    프로젝트 금융 지표 — NPV / IRR / Payback / Profitability Index.

    annual_cf_usd: 연간 net cash flow (revenue - opex - tax 등 — 본 모델에선 annual_profit_usd)
    capex_total_usd: 초기 자본 투자 총액 (USD)
    lifetime_yr: 프로젝트 수명
    discount: 할인율 (decimal)

    Returns:
      npv: 순현재가치
      irr: 내부수익률 (decimal, 음수면 IRR < 0 또는 N/A)
      payback_yr: 단순 회수 기간 (None면 회수 불가)
      payback_disc_yr: 할인 회수 기간
      pi: Profitability Index (1 초과면 양호)
    """
    # Cash flows: t=0 -capex, t=1..N annual_cf
    cfs = [-capex_total_usd] + [annual_cf_usd] * lifetime_yr

    # NPV
    npv = sum(cf / (1 + discount) ** t for t, cf in enumerate(cfs))

    # IRR (bisection)
    if annual_cf_usd <= 0 or capex_total_usd <= 0:
        irr = None
    else:
        low, high = -0.50, 5.0
        irr = None
        for _ in range(80):
            mid = (low + high) / 2
            try:
                npv_mid = sum(cf / (1 + mid) ** t for t, cf in enumerate(cfs))
            except (ValueError, ZeroDivisionError, OverflowError):
                break
            if abs(npv_mid) < capex_total_usd * 1e-5:
                irr = mid
                break
            if npv_mid > 0:
                low = mid
            else:
                high = mid
        else:
            irr = mid
        # 음수 NPV로 끝나면 IRR이 매우 낮음을 의미
        if npv < -capex_total_usd * 0.9 and irr is None:
            irr = None  # 회수 불가능 수준

    # Simple payback
    cum = 0
    payback_yr = None
    for t in range(1, lifetime_yr + 1):
        cum += annual_cf_usd
        if cum >= capex_total_usd:
            payback_yr = t - 1 + (capex_total_usd - (cum - annual_cf_usd)) / annual_cf_usd if annual_cf_usd > 0 else None
            break

    # Discounted payback
    cum_disc = 0
    payback_disc_yr = None
    for t in range(1, lifetime_yr + 1):
        disc_cf = annual_cf_usd / (1 + discount) ** t
        cum_disc += disc_cf
        if cum_disc >= capex_total_usd:
            payback_disc_yr = t
            break

    # Profitability Index (PV of inflows / PV of outflows)
    pv_inflows = sum(annual_cf_usd / (1 + discount) ** t for t in range(1, lifetime_yr + 1)) if annual_cf_usd > 0 else 0
    pi = pv_inflows / capex_total_usd if capex_total_usd > 0 else 0

    return {
        "npv": npv,
        "irr": irr,
        "payback_yr": payback_yr,
        "payback_disc_yr": payback_disc_yr,
        "profitability_index": pi,
        "annual_cf": annual_cf_usd,
        "capex_total": capex_total_usd,
    }


def calc_lca_emissions(srd_GJ_t, we_elec_GJe_t, loss_kg_t,
                        heat_factor_kgCO2_GJ, grid_factor_gCO2_kWh,
                        solvent_factor_kgCO2_kg,
                        capex_per_t_USD, lifetime_yr=25,
                        include_embodied=True) -> dict:
    """
    Lifecycle CO2 emissions per ton CO2 captured (Scope 1+2+3).
    출처: IEAGHG 2010-09, NETL 2021 LCA, ISO 14067, Singh 2011, Pour 2018

    e_heat:     SRD × heat factor [tCO2 emitted / tCO2 captured]
    e_elec:     We_elec × kWh/GJ × grid factor
    e_solvent:  loss × emission factor (Scope 3 — 흡수제 makeup 생산)
    e_embodied: CAPEX × emission factor / lifetime (Scope 3 — equipment 제조)
    """
    # 전기 히트펌프 케이스: grid factor × 3.6 / COP=3
    if heat_factor_kgCO2_GJ < 0:  # 동적 계산 마커
        heat_factor_kgCO2_GJ = grid_factor_gCO2_kWh * 3.6 / 3.0  # COP=3 가정

    e_heat = srd_GJ_t * heat_factor_kgCO2_GJ / 1000      # tCO2 / tCO2
    e_elec = we_elec_GJe_t * 277.78 * grid_factor_gCO2_kWh / 1e6
    e_solvent = loss_kg_t * solvent_factor_kgCO2_kg / 1000

    if include_embodied and lifetime_yr > 0:
        # CAPEX 1$ → 0.2 kg embodied CO2, lifetime 동안 amortize
        # 단, capex_per_t_USD는 [USD/(t/yr)]이므로 톤당 lifetime 총 capex는 동일
        e_embodied = capex_per_t_USD * EMBODIED_CO2_PER_USD_CAPEX / lifetime_yr / 1000
    else:
        e_embodied = 0.0

    e_total = e_heat + e_elec + e_solvent + e_embodied

    return {
        "e_heat":      e_heat,
        "e_elec":      e_elec,
        "e_solvent":   e_solvent,
        "e_embodied":  e_embodied,
        "e_total":     e_total,
        "lca_efficiency_pct": (1 - e_total) * 100,  # 100% = perfect, 75% = 25% leak
    }


def calc_revenue(capture_t_yr, ccs_share, ccs_yield, ccu_share, ccu_yield,
                 ccu_price_krw_t,
                 carbon_market_usd_t,    # 배출권 시장 (compliance trading)
                 subsidy_usd_t,          # 정부 보조금 (45Q, SDE++ 등)
                 extra_revenue_usd_t,    # LCFS / voluntary / 기타
                 fx_krw_per_usd) -> dict:
    """
    매출 통합 계산 — 다중 인센티브 stacking 지원.

    실제 글로벌 CCS 프로젝트는 다음 조합을 모두 받음 (중복지원 아님):
      1) CCU 액화탄산 매출 (CCU 모드)
      2) 배출권 시장 매출 (compliance trading: K-ETS, CA-CAT 등) — 격리량 기준
      3) 정부 보조금 (45Q, SDE++ 등) — 격리량 또는 활용량
      4) LCFS / voluntary 추가 매출 — 격리량 기준 (DAC 등)
    """
    stored_t = capture_t_yr * ccs_share * ccs_yield
    sold_lco2_t = capture_t_yr * ccu_share * ccu_yield
    qualifying_t = stored_t + sold_lco2_t

    # 1) CCU 액화탄산 매출
    ccu_revenue_usd = sold_lco2_t * ccu_price_krw_t / fx_krw_per_usd

    # 2) 배출권 시장 (compliance) — CCS 격리량만 (gross stored)
    #    K-ETS CCU 차감은 직접 매출 아님 (조건부 가치 — 탭 ⑨ 별도 표시)
    market_revenue_usd = stored_t * carbon_market_usd_t

    # 3) 정부 보조금 (45Q-CCS, 45Q-EOR, NL SDE++, UK CfD 등) — 직접 매출
    #    격리량 또는 활용량 양쪽 가능 (정책에 따라)
    subsidy_usd = qualifying_t * subsidy_usd_t

    # 4) LCFS / voluntary credits — 직접 매출 (격리량 또는 출하량)
    extra_revenue_usd = qualifying_t * extra_revenue_usd_t

    total_revenue_usd = ccu_revenue_usd + market_revenue_usd + subsidy_usd + extra_revenue_usd
    revenue_per_capture = total_revenue_usd / capture_t_yr if capture_t_yr > 0 else 0
    return {
        "stored_t":         stored_t,
        "sold_lco2_t":      sold_lco2_t,
        "qualifying_t":     qualifying_t,
        "ccu_revenue":      ccu_revenue_usd,
        "market_revenue":   market_revenue_usd,
        "subsidy":          subsidy_usd,
        "extra_revenue":    extra_revenue_usd,
        "total_revenue":    total_revenue_usd,
        "rev_per_capture":  revenue_per_capture,
    }


# ======================================================================
# 사이드바
# ======================================================================
with st.sidebar:
    # ──────────────────────────────────────────────
    # 🚀 시나리오 프리셋 (Quick Start)
    # ──────────────────────────────────────────────
    st.markdown("### 🚀 빠른 시작 — 시나리오 프리셋")
    preset_options = ["custom"] + list(PRESETS.keys())
    st.selectbox(
        "프리셋 선택 (자동 설정)",
        options=preset_options,
        format_func=lambda k: ("✏️ Custom (직접 설정)" if k == "custom"
                                else PRESETS[k]["label"]),
        on_change=apply_preset,
        key="preset_select",
        help="대표 시나리오를 선택하면 모든 입력이 자동으로 채워집니다",
    )
    _selected_preset = st.session_state.get("preset_select", "custom")
    if _selected_preset != "custom":
        st.caption(f"📌 {PRESETS[_selected_preset]['description']}")

    # ──────────────────────────────────────────────
    # 💱 통화 표시 toggle (전역)
    # ──────────────────────────────────────────────
    st.markdown("### 💱 표시 통화")
    display_currency = st.radio(
        "통화 표시 방식",
        options=["Both", "USD", "KRW"],
        format_func=lambda x: {"Both": "USD + KRW", "USD": "USD만", "KRW": "KRW만"}[x],
        horizontal=True,
        index=0,
        key="display_currency",
    )

    st.markdown("---")
    st.markdown("### ⚙️ 입력 파라미터")

    # TRL 필터 (낮은 TRL일수록 데이터가 idealized 경향 — 주의)
    trl_filter = st.multiselect(
        "🏷️ TRL 필터 (기술 성숙도)",
        options=["🟢 TRL 9 (상용)", "🟡 TRL 7-8 (Demo)", "🟠 TRL ≤6 (Pilot/연구)"],
        default=["🟢 TRL 9 (상용)", "🟡 TRL 7-8 (Demo)", "🟠 TRL ≤6 (Pilot/연구)"],
        help=(
            "TRL = Technology Readiness Level (1~9). NASA·EU·IEA 표준.\n"
            "⚠️ 낮은 TRL은 파일럿 idealized 데이터 경향 → 상용 스케일에서 +10~20% 페널티."
        ),
        key="trl_filter",
    )

    # TRL 필터 적용한 기술 옵션 풀
    _filtered_keys = [k for k in TECH_KEYS if trl_group(LIT[k].get("TRL", 7)) in trl_filter]

    selected = st.multiselect(
        "비교할 기술 선택",
        options=_filtered_keys,
        default=[k for k in ["MEA_baseline", "MHI_KS21", "Cansolv_DC103", "Aker_S26",
                              "CAP_B12C", "TSA_Solid", "CaL"] if k in _filtered_keys],
        format_func=lambda k: f"{trl_group(LIT[k].get('TRL', 7)).split()[0]} {LIT[k]['name']}",
        key="selected_techs",
    )

    st.caption("⌨️ 모든 입력은 직접 숫자 입력 가능 (미입력시 default 사용)")

    capture_mt_yr = st.number_input(
        "연간 CO₂ 포집량 [MtCO₂/yr]",
        min_value=0.1, max_value=20.0, value=3.7, step=0.1,
        format="%.2f",
        help=(
            "NETL B12C/B12B 기준값 ≈ 3.7 Mt/yr · default: 3.7\n"
            "규모 효과 적용 (CCS specific):\n"
            "• CAPEX: IEAGHG/NETL n=0.65\n"
            "• SRD: ±10%/decade (IEAGHG 2013/04)\n"
            "• We_comp: ±6%/decade (NETL Rev4)"
        ),
        key="capture_mt_yr",
    )
    capture_t_yr = capture_mt_yr * 1e6

    # 규모 효과 안내 (CAPEX, SRD, We_comp 모두)
    _capex_pct = ((REF_CAPTURE_MT_YR / capture_mt_yr) ** (1 - CAPEX_SCALE_EXPONENT) - 1) * 100
    _log_r = np.log10(capture_mt_yr / REF_CAPTURE_MT_YR)
    _srd_pct = max(min(SRD_SCALE_PER_DECADE * _log_r * 100, (SRD_CLIP[1]-1)*100), (SRD_CLIP[0]-1)*100)
    _wec_pct = max(min(-WE_COMP_SCALE_PER_DECADE * _log_r * 100, (WE_COMP_CLIP[1]-1)*100), (WE_COMP_CLIP[0]-1)*100)

    def _arr(v):
        if v > 0.5: return "↑"
        if v < -0.5: return "↓"
        return "≈"
    st.caption(
        f"→ 규모 보정 ({REF_CAPTURE_MT_YR} Mt 대비):  "
        f"CAPEX {_arr(_capex_pct)}{abs(_capex_pct):.0f}% · "
        f"SRD {_arr(_srd_pct)}{abs(_srd_pct):.1f}% · "
        f"We_comp {_arr(_wec_pct)}{abs(_wec_pct):.1f}%"
    )

    # Capacity range 경고 — 부적합 규모 시뮬 방지
    _selected_now = st.session_state.get("selected_techs", [])
    _out_of_range = []
    for k in _selected_now:
        rng = CAPACITY_RANGE.get(k, (0.01, 100))
        if capture_mt_yr < rng[0] * 0.5:
            _out_of_range.append(
                f"**{LIT[k]['name']}**: 적정 {rng[0]:.2g}~{rng[1]:.0f} Mt/yr "
                f"(현재 {capture_mt_yr} → 너무 작음)"
            )
        elif capture_mt_yr > rng[1] * 2:
            _out_of_range.append(
                f"**{LIT[k]['name']}**: 적정 {rng[0]:.2g}~{rng[1]:.0f} Mt/yr "
                f"(현재 {capture_mt_yr} → 너무 큼)"
            )
    if _out_of_range:
        st.warning("⚠️ 일부 기술이 적정 capacity 범위 밖:\n\n" + "\n\n".join(_out_of_range))

    capture_eff_pct = st.number_input(
        "포집율 [%]",
        min_value=50, max_value=99, value=90, step=1,
        help=(
            "default: 90 (NETL baseline, 비용 최적점)\n"
            "포집율 효과 (IEAGHG 2019):\n"
            "• SRD: 90%→99% +18% (평형 한계)\n"
            "• CAPEX: 90%→99% +10% (column 크기 ↑)"
        ),
    )
    capture_eff = capture_eff_pct / 100.0
    # 포집율 효과 자동 표시
    _srd_capt_pct = (capture_rate_factor(capture_eff, SRD_VS_CAPTURE_COEF) - 1) * 100
    _capex_capt_pct = (capture_rate_factor(capture_eff, CAPEX_VS_CAPTURE_COEF) - 1) * 100
    if abs(_srd_capt_pct) > 0.5 or abs(_capex_capt_pct) > 0.5:
        _arr_s = "↑" if _srd_capt_pct > 0 else "↓"
        _arr_c = "↑" if _capex_capt_pct > 0 else "↓"
        st.caption(
            f"→ 포집율 보정 (90% 기준): SRD **{_arr_s}{abs(_srd_capt_pct):.1f}%** · "
            f"CAPEX **{_arr_c}{abs(_capex_capt_pct):.1f}%**"
        )

    T_cool_C = st.number_input(
        "냉각수 온도 [°C]",
        min_value=0, max_value=50, value=25, step=1,
        help="default: 25",
    )

    p_final_bar = st.number_input(
        "CO₂ 최종 압력 [bar]",
        min_value=5, max_value=300, value=152, step=1,
        help=(
            "용도별:\n"
            "• 식품 액화탄산: 15~20 bar\n"
            "• 산업용: 5~25 bar\n"
            "• 파이프라인: 100~150 bar\n"
            "• EOR/저장: 150~200 bar\n"
            "default: 152"
        ),
    )

    if p_final_bar < 30:
        _use_label = "🧊 액화탄산 (식품·산업용)"
    elif p_final_bar < 80:
        _use_label = "💨 가스 수송"
    elif p_final_bar < 120:
        _use_label = "🚰 파이프라인"
    else:
        _use_label = "⛏️ EOR / 지중저장"
    st.caption(f"→ 추정 용도: **{_use_label}**")

    st.markdown("---")
    st.markdown("### 🏗️ 프로젝트 시나리오")
    st.caption("Retrofit/Greenfield/산업별 CAPEX 차이 반영 (IEAGHG 2011/02, NETL QGESS)")

    project_scenario_key = st.selectbox(
        "프로젝트 유형",
        options=list(PROJECT_SCENARIOS.keys()),
        format_func=lambda k: PROJECT_SCENARIOS[k]["label"],
        index=0,  # retrofit_power default
        help="LIT CAPEX는 발전소 retrofit 기준(1.0×). 다른 유형은 multiplier 적용.",
        key="project_scenario",
    )
    project = PROJECT_SCENARIOS[project_scenario_key]
    project_multiplier = project["multiplier"]

    # 시나리오 카드 표시
    st.markdown(
        f"<div style='background:#1E2128; border-left:3px solid {project['color']}; "
        f"padding:8px 10px; border-radius:4px; margin:4px 0;'>"
        f"<b style='color:{project['color']};'>CAPEX 배수: ×{project['multiplier']:.2f}</b>"
        f"<span style='color:#8b95a7; font-size:0.78rem;'> "
        f"(예: MEA $950 × {project['multiplier']:.2f} = ${950*project['multiplier']:,.0f}/(t/yr))</span><br>"
        f"<span style='font-size:0.75rem; color:#B0BEC5;'><b>적용 범위</b>: {project['scope']}</span><br>"
        f"<span style='font-size:0.72rem; color:#8b95a7;'><b>실제 사례</b>: {project['examples']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("### 💰 경제성 가정")

    lifetime = st.number_input("플랜트 수명 [년]", 10, 50, 25, 1, help="default: 25")
    discount_pct = st.number_input("할인율 [%]", 2.0, 15.0, 8.0, 0.5, format="%.1f", help="default: 8.0")
    discount = discount_pct / 100.0
    elec_price = st.number_input("전기 가격 [USD/MWh]", 20, 300, 80, 5, help="default: 80")

    fx_krw_per_usd = st.number_input(
        "💱 환율 [KRW/USD]",
        min_value=800.0, max_value=2000.0, value=1400.0, step=10.0,
        format="%.0f",
        help="default: 1,400 (2026.4 기준)",
    )
    st.caption(f"→ 현재 환율: **{fx_krw_per_usd:,.0f} KRW/USD**")

    st.markdown("---")
    st.markdown("### ♻️ CCUS 시설 모드")
    st.caption("⚠️ 실제 시설은 CCS/CCU 중 하나로 commit")

    facility_mode = st.radio(
        "시설 처분 경로",
        options=["CCS", "CCU"],
        format_func=lambda x: "🏔️ CCS — 지중저장" if x == "CCS" else "🥤 CCU — 액화탄산 출하",
        horizontal=True,
        key="facility_mode",
    )

    # K-ETS CCU 차감 변수 default (CCS 모드에서도 정의되도록)
    apply_kets_ccu = False
    kets_ccu_price_info = 0.0

    if facility_mode == "CCS":
        ccs_share, ccu_share = 1.0, 0.0
    else:
        ccs_share, ccu_share = 0.0, 1.0

    # CCS / CCU 모드별 입력 (격리수율, CCU 등급/판매가)
    if facility_mode == "CCS":
        ccs_yield_pct = st.number_input(
            "CCS 격리 수율 [%]",
            min_value=80.0, max_value=99.0, value=92.0, step=0.5,
            format="%.1f",
            help="포집→탈수→압축→수송→주입 누적. default: 92%",
        )
        ccs_yield = ccs_yield_pct / 100.0
        ccu_grade_key = "food"
        ccu = CCU_GRADES[ccu_grade_key]
        ccu_price_krw = 0
    else:
        ccs_yield = 1.0
        ccu_grade_key = st.selectbox(
            "CCU 정제 등급",
            options=list(CCU_GRADES.keys()),
            format_func=lambda k: CCU_GRADES[k]["label"],
            index=0,
            help="순도↑ → 수율↓ + 정제 CAPEX↑",
            key="ccu_grade",
        )
        ccu = CCU_GRADES[ccu_grade_key]
        st.caption(
            f"→ 수율 **{ccu['yield']*100:.0f}%** · "
            f"표준가 **{ccu['price_krw_t']:,} KRW/t** · "
            f"CAPEX ×**{ccu['capex_mult']:.2f}**"
        )
        ccu_price_krw = st.number_input(
            "액화탄산 판매가 [KRW/t]",
            min_value=0, max_value=2_000_000, value=ccu["price_krw_t"], step=10_000,
            format="%d",
            help=f"default: {ccu['price_krw_t']:,}",
            key="ccu_price_krw",
        )
        st.caption(f"→ 입력값: **{ccu_price_krw:,} KRW/t**")

    # ──────────────────────────────────────────────
    # 다중 인센티브 stacking (옵션 B)
    # ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💚 인센티브 (다중 적용 — Stacking)")
    st.caption(
        "🇺🇸 미국 CCS는 **45Q + 주별 시장 + LCFS** 동시 적용 (정책 도구 다름 — 중복지원 ✗). "
        "🇪🇺 EU는 SDE++ 단독, 🇰🇷 한국은 K-ETS + K-CCUS stack 가능."
    )
    # 지역 색상 범례 (정적)
    st.markdown(
        "<div style='font-size:0.78rem; padding:6px 10px; background:#1E2128; "
        "border-radius:4px; margin:6px 0;'>"
        "<b>📍 지역 색상</b> &nbsp;"
        "🟦 미국 &nbsp; 🟨 유럽 &nbsp; 🟪 영국 &nbsp; 🟧 한국 &nbsp; ⚪ 없음/Custom<br>"
        "<span style='color:#8b95a7;'>같은 색끼리 stack 가능 · 다른 색은 지역 불일치</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    # 1️⃣ 배출권 시장 (compliance trading)
    credit_market_keys = (
        ["None"]
        + [k for k, v in CARBON_MARKETS.items() if v["type"] == "credit" and k != "Custom"]
        + ["Custom"]
    )

    if facility_mode == "CCS":
        st.markdown("##### 1️⃣ 배출권 시장 (compliance)")
        st.caption("CCS 격리량 기준 거래 (CCU는 격리 안 됨). 색깔로 지역 그룹 식별")

        def _fmt_market_static(k):
            if k == "None":
                return "⚪ 없음"
            if k == "Custom":
                return "⚪ ✏️ Custom 입력"
            return f"{region_icon(k)} {CARBON_MARKETS[k]['label']}"

        carbon_market_key = st.selectbox(
            "탄소시장 선택",
            options=credit_market_keys,
            format_func=_fmt_market_static,
            index=0,
            key="cm_select",
        )
        if carbon_market_key == "None":
            carbon_market_usd = 0.0
        elif carbon_market_key == "Custom":
            # 정적 label — 동적 값 변경 시에도 widget 재초기화 방지
            carbon_market_usd = st.number_input(
                "Custom 시장가 [USD/t]",
                min_value=0.0, max_value=500.0, value=30.0, step=1.0, format="%.1f",
                key="cm_custom",
            )
            st.caption("→ 사용자 정의 단가")
        else:
            mkt = CARBON_MARKETS[carbon_market_key]
            # 정적 label "탄소시장 단가 [USD/t]" 고정 — native 표시는 caption으로 분리
            carbon_market_usd = st.number_input(
                "탄소시장 단가 [USD/t]",
                min_value=0.0, max_value=500.0,
                value=float(mkt["price_usd_t"]), step=1.0, format="%.1f",
                key=f"cm_price_{carbon_market_key}",  # 시장별 별도 key → 충돌 방지
            )
            st.caption(f"→ 표준값: {mkt['native']}")
    else:
        # CCU 모드 — 한국 K-ETS CCU 차감 보고 (정보용, 매출 아님)
        st.markdown("##### 1️⃣ 배출권 시장 (CCU 모드)")
        st.caption(
            "🇰🇷 한국 할당대상업체는 CCU 출하량을 K-ETS 배출량에서 차감 가능. "
            "**단, 직접 매출 아님 — 배출권 수급 상황에 따라 조건부 가치**. "
            "탭 ⑨에서 톤수·조건부 가치 별도 분석."
        )
        apply_kets_ccu = st.checkbox(
            "🇰🇷 K-ETS CCU 차감 보고 (할당대상업체, 정보용)",
            value=False,
            help="체크 시: 탭 ⑨에서 배출량 차감 톤수 + 조건부 경제 가치 표시 "
                 "(매출 계산에는 미반영)",
            key="kets_ccu_deduction",
        )
        if apply_kets_ccu:
            kets_ccu_price_info = st.number_input(
                "K-ETS 단가 [USD/t] — 조건부 가치 산정용",
                min_value=0.0, max_value=100.0, value=7.0, step=0.5,
                format="%.1f",
                help="배출권 매입 회피 시나리오 산정용. **실제 매출 아님**.",
                key="kets_ccu_price",
            )
            st.caption(
                f"ℹ️ {kets_ccu_price_info:.1f}$/t × 출하량 = 조건부 가치 (탭 ⑨ 표시)"
            )
        else:
            kets_ccu_price_info = 0.0
        # CCU 모드는 carbon_market 매출 항상 0
        carbon_market_key = "None"
        carbon_market_usd = 0.0

    # 2️⃣ 정부 보조금 (federal/state subsidy)
    st.markdown("##### 2️⃣ 정부 보조금 (federal/state)")
    st.caption("위 1️⃣ 시장과 **같은 색** 보조금만 stack 현실적")
    subsidy_keys = (
        ["None"]
        + [k for k, v in CARBON_MARKETS.items() if v["type"] == "subsidy"]
        + ["Custom_subsidy"]
    )
    default_sub_idx = (subsidy_keys.index("45Q-CCS") if facility_mode == "CCS"
                       else subsidy_keys.index("45Q-EOR"))

    def _fmt_subsidy_static(k):
        if k == "None":
            return "⚪ 없음"
        if k == "Custom_subsidy":
            return "⚪ ✏️ Custom 입력"
        return f"{region_icon(k)} {CARBON_MARKETS[k]['label']}"

    subsidy_key = st.selectbox(
        "보조금 제도",
        options=subsidy_keys,
        format_func=_fmt_subsidy_static,
        index=default_sub_idx,
        key="sub_select",
    )
    if subsidy_key == "None":
        subsidy_usd = 0.0
    elif subsidy_key == "Custom_subsidy":
        subsidy_usd = st.number_input(
            "Custom 보조금 [USD/t]",
            min_value=0.0, max_value=500.0, value=50.0, step=1.0, format="%.1f",
            key="sub_custom",
        )
        st.caption("→ 사용자 정의 단가")
    else:
        sub = CARBON_MARKETS[subsidy_key]
        # 정적 label + 보조금별 별도 key → 보조금 변경 시에만 default값 적용, 같은 보조금 내 +/- 안전
        subsidy_usd = st.number_input(
            "보조금 단가 [USD/t]",
            min_value=0.0, max_value=500.0,
            value=float(sub["price_usd_t"]), step=1.0, format="%.1f",
            key=f"sub_price_{subsidy_key}",
        )
        st.caption(f"→ 표준값: {sub['native']}")

    # 3️⃣ LCFS / 자발적 크레딧 / 기타
    st.markdown("##### 3️⃣ LCFS / 자발적 / 기타")
    extra_revenue_usd = st.number_input(
        "추가 매출 [$/t]",
        0.0, 500.0, 0.0, 5.0, format="%.1f",
        help=(
            "California LCFS: ~$150/t (DAC pathway, biofuels)\n"
            "Voluntary credits (Stripe/Frontier): $200~600/t (DAC, removal)\n"
            "기타 직접 매출: 사용자 정의"
        ),
        key="extra_rev",
    )

    # 지역 호환성 경고
    incompat = []
    if carbon_market_key.startswith("K-") and subsidy_key.startswith("45Q"):
        incompat.append("K-ETS(KR) + 45Q(US)")
    if carbon_market_key == "EU-ETS" and subsidy_key.startswith("45Q"):
        incompat.append("EU ETS + 45Q(US)")
    if carbon_market_key in ("RGGI", "CA-CAT") and subsidy_key == "K-CCUS-est":
        incompat.append("US 시장 + K-CCUS(KR)")
    if carbon_market_key == "EU-ETS" and subsidy_key == "K-CCUS-est":
        incompat.append("EU ETS + K-CCUS(KR)")
    if incompat:
        st.warning(f"⚠️ 지역 불일치 가능: {', '.join(incompat)} — 동일 시설에 적용 어려움")

    # 합계 표시 카드
    total_incentive_usd = carbon_market_usd + subsidy_usd + extra_revenue_usd
    if total_incentive_usd > 0:
        st.markdown(
            f"<div style='background:#1E3A1E; border-left:3px solid #81C784; "
            f"padding:8px 10px; border-radius:4px; margin-top:6px;'>"
            f"<b style='color:#81C784;'>💰 총 인센티브 stack: "
            f"${total_incentive_usd:.1f}/t</b><br>"
            f"<span style='font-size:0.78rem; color:#B0BEC5;'>"
            f"≈ {total_incentive_usd*fx_krw_per_usd:,.0f} KRW/t<br>"
            f"시장 ${carbon_market_usd:.0f} + 보조금 ${subsidy_usd:.0f} + 추가 ${extra_revenue_usd:.0f}"
            f"</span></div>",
            unsafe_allow_html=True,
        )

    # 호환 변수 (기존 표시 코드용)
    market_label = (
        f"Stack (${total_incentive_usd:.0f}/t)" if total_incentive_usd > 0 else "없음"
    )
    market_price_usd = total_incentive_usd  # 표시용 합계
    market_type = "stack"
    market_key = subsidy_key if subsidy_usd > 0 else carbon_market_key

    # ──────────────────────────────────────────────
    # 🌱 LCA / Lifecycle Scope 1+2+3 (CRCF/ICVCM 기준)
    # ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🌱 Lifecycle / Net CO₂ (Scope 1+2+3)")
    st.caption(
        "포집된 CO₂ 1톤 중 lifecycle 배출 차감 후 **실제 줄어든 net CO₂** 계산. "
        "EU CRCF, ICVCM, voluntary buyer (Stripe Frontier 등) 기준."
    )

    # 1. 열원 선택
    heat_source_key = st.selectbox(
        "열원 (재생탑 steam)",
        options=list(HEAT_SOURCES.keys()),
        format_func=lambda k: HEAT_SOURCES[k]["label"],
        index=0,  # natural_gas default
        key="heat_source",
    )
    heat_info = HEAT_SOURCES[heat_source_key]
    if heat_source_key == "custom_heat":
        heat_factor = st.number_input(
            "열 배출계수 [kgCO₂/GJ]",
            min_value=0.0, max_value=200.0, value=55.0, step=5.0,
            key="heat_custom",
        )
    else:
        heat_factor = float(heat_info["kgCO2_GJ"])
        st.caption(f"→ 배출계수: **{heat_factor if heat_factor >= 0 else 'grid 의존':.0f}** kgCO₂/GJ · {heat_info['note']}"
                   if heat_factor >= 0 else f"→ {heat_info['note']}")

    # 2. 전력 grid 선택
    grid_key = st.selectbox(
        "전력 grid",
        options=list(GRID_FACTORS.keys()),
        format_func=lambda k: GRID_FACTORS[k]["label"],
        index=0,  # us_avg default
        key="grid_select",
    )
    if grid_key == "custom_grid":
        grid_factor = st.number_input(
            "grid 배출계수 [gCO₂/kWh]",
            min_value=0.0, max_value=1500.0, value=380.0, step=10.0,
            key="grid_custom",
        )
    else:
        grid_factor = float(GRID_FACTORS[grid_key]["gCO2_kWh"])
        st.caption(f"→ {grid_factor:.0f} gCO₂/kWh")

    # 3. Embodied CAPEX 포함 여부
    include_embodied = st.checkbox(
        "Embodied CAPEX 배출 포함 (CAPEX × 0.20 kgCO₂/$)",
        value=True,
        help="Equipment·구조물 제조 시 embodied carbon. lifetime amortized.",
        key="include_embodied",
    )

    st.markdown("---")
    st.caption(
        "**†** = 파일럿/실증 데이터.<br>"
        "데이터: NETL/IEAGHG/DOE/KIER/IRS 45Q",
        unsafe_allow_html=True,
    )

    # ──────────────────────────────────────────────
    # 🔗 자매 도구 — CBAM 계산기
    # ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        f"""
        <div style='background:linear-gradient(135deg, #1E3A5F 0%, #2A4A6F 100%);
                    border-left:3px solid #FFB74D; border-radius:6px;
                    padding:10px 12px; margin-top:6px;'>
            <div style='font-size:0.72rem; color:#B0BEC5; margin-bottom:3px;'>
                🔗 자매 도구
            </div>
            <a href='{CBAM_TOOL_URL}' target='_blank'
               style='color:#FFB74D; text-decoration:none; font-weight:700; font-size:0.88rem;'>
                🛡️ EU CBAM 계산기 →
            </a>
            <div style='font-size:0.7rem; color:#8b95a7; margin-top:3px;'>
                한국 산업 CBAM 영향 분석 (자매 프로젝트)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ──────────────────────────────────────────────
    # 👤 작성자 정보 (항상 사이드바 하단에 표시)
    # ──────────────────────────────────────────────
    st.markdown(
        """
        <div style='background:#1E2128; border-left:3px solid #4FC3F7;
                    border-radius:6px; padding:10px 12px; margin-top:8px;'>
            <div style='font-size:0.78rem; color:#8b95a7; margin-bottom:3px;'>
                👤 Built by
            </div>
            <div style='font-size:0.95rem; font-weight:700; color:#E8EAED;'>
                송봉관 / Song BK
            </div>
            <div style='font-size:0.72rem; color:#B0BEC5; margin:2px 0 6px 0;'>
                DAC & CCUS 기술사업화 전문가
            </div>
            <div style='font-size:0.72rem; line-height:1.7;'>
                🐙 <a href='https://github.com/cafeon90-oss' target='_blank'
                       style='color:#81C784; text-decoration:none;'>GitHub</a> &nbsp;
                💼 <a href='https://www.linkedin.com/in/bongkwan-song-95a0213ba/' target='_blank'
                       style='color:#81C784; text-decoration:none;'>LinkedIn</a><br>
                📝 <a href='https://cdrmaster.tistory.com/' target='_blank'
                       style='color:#81C784; text-decoration:none;'>Blog (Tistory)</a> &nbsp;
                📧 <a href='mailto:cafeon90@gmail.com'
                       style='color:#81C784; text-decoration:none;'>Email</a>
            </div>
            <div style='font-size:0.65rem; color:#6e7888; margin-top:6px;'>
                © 2026 Song BK · MIT License
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ======================================================================
# 헤더
# ======================================================================
st.title("🌫️ CO₂ 포집·CCUS 기술·경제성 벤치마크")
st.caption(
    "Advanced Amine (KS-21·DC-103·Aker S26) + 🇰🇷 **KIERSOL (KIER)** + "
    "비아민계 (CAP·DMX·TSA·CaL) 통합 비교 · "
    "NETL 2022 / IEAGHG / IRS 45Q / KIER 기반"
)

# ──────────────────────────────────────────────
# 🔗 자매 도구 — CBAM 계산기 (상단 배너)
# ──────────────────────────────────────────────
st.markdown(
    f"""
    <div style='background:linear-gradient(135deg, #1E3A5F 0%, #2A4A6F 100%);
                border-radius:8px; padding:10px 16px; margin: 8px 0;
                border-left: 4px solid #FFB74D;
                display:flex; justify-content:space-between; align-items:center;
                flex-wrap:wrap; gap:8px;'>
        <div>
            <span style='color:#B0BEC5; font-size:0.8rem;'>🔗 자매 도구</span>
            &nbsp;&nbsp;
            <a href='{CBAM_TOOL_URL}' target='_blank'
               style='color:#FFB74D; text-decoration:none; font-weight:700; font-size:1.0rem;'>
                🛡️ EU CBAM 계산기 (한국 산업 영향 분석)
            </a>
        </div>
        <span style='font-size:0.78rem; color:#8b95a7;'>
            CCS 도입 시 CBAM 회피 효과를 별도 시뮬레이션 →
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────
# 📖 사용자 매뉴얼 (Industry Expert Guide)
# ──────────────────────────────────────────────
with st.expander("📖 **사용자 매뉴얼** — 본 도구의 활용법 (업계 전문가·준전문가용)", expanded=False):
    st.markdown(f"""
## 🎯 도구 목적

CO₂ 포집·CCUS 기술의 **기술 성능·경제성·Lifecycle CO₂·정책 인센티브를 통합 비교**하여
사업 의사결정·정책 분석·R&D 우선순위 검토에 활용.

대상: CCUS 사업개발·EPC·정책분석·연구자

## 🚀 빠른 시작 (3-step)

1. **사이드바 맨 위 "🚀 빠른 시작 — 시나리오 프리셋"** 에서 6개 표준 케이스 중 선택
   (예: 🇺🇸 Petra Nova형, 🇰🇷 시멘트 retrofit, 🇪🇺 블루수소 등)
2. 입력 자동 채워짐 → 메인 화면에서 **자동 인사이트 박스** 확인
3. 필요 시 사이드바 입력 조정 (포집량·시나리오·인센티브 등)

## ⚙️ 입력 파라미터 가이드

### 기본 입력
- **포집량 [Mt/yr]**: 연간 CO₂ 포집 능력. NETL 기준 3.7 Mt = 550 MWe 발전소 retrofit
- **포집율 [%]**: 90% = NETL baseline (cost-optimal). 99%↑ 시 SRD/CAPEX 비선형 증가 (IEAGHG 2019)
- **냉각수 온도 [°C]**: 25°C 표준. 더운 지역(35°C+) → CAP의 냉동기 부하 ↑
- **CO₂ 최종 압력 [bar]**: 152 = NETL 초임계 표준. 액화탄산용 5~25, EOR 100~150
- **TRL 필터**: 기술 성숙도별 그룹화 (🟢 9 / 🟡 7-8 / 🟠 ≤6)

### 시설 모드
- **🏔️ CCS** (지중저장): 영구 격리, 배출권·45Q 수익
- **🥤 CCU** (액화탄산 출하): 직접 매출, K-ETS CCU 차감 옵션 (조건부)

### 프로젝트 시나리오 (CAPEX multiplier)
- Retrofit 발전소 (×1.0, default) — Boundary Dam, Petra Nova
- Greenfield 발전소 (×0.75) — 통합 설계
- Greenfield 산업 (×1.10) — Northern Lights, blue H₂
- Retrofit 산업 (×1.65) — Norcem Brevik, POSCO 시멘트·철강
- Brownfield (×0.90) — 부지 재활용

### 인센티브 (3-tier stacking)
1. **배출권 시장** (compliance): K-ETS, EU ETS, RGGI, CA-CAT
2. **정부 보조금**: 45Q ($85), NL SDE++ ($120), UK CfD ($180), K-CCUS Act
3. **LCFS / Voluntary**: California LCFS ($150), Stripe Frontier ($300+)

같은 색(🟦🟨🟪🟧)끼리만 stack 현실적 (지역 호환성).

### LCA / Lifecycle (탭 ③)
- **열원** (재생탑 steam): 가스보일러 default 55 kgCO₂/GJ
- **전력 grid**: 한국 470, 미국 380, 노르웨이 30 gCO₂/kWh
- **Embodied CAPEX** toggle

## 📊 결과 해석 가이드

### 핵심 KPI (탭 ①)
- **연 손익** [USD/yr 또는 억원/yr]: 메인 — 흑자 여부
- **SRD** [GJ/tCO₂]: 흡수제 재생열 (낮을수록 우수)
- **We** [GJe/tCO₂]: 전력등가 일 통합
- **SPECCA** [MJ/tCO₂]: 1차 에너지 페널티
- **COCA** [USD/tCO₂]: 단위 CO₂당 비용

### Net COCA = COCA − 매출/보조금
- **음수** = 흑자 (1톤 잡으면 돈을 받음)
- **양수** = 적자 (1톤 잡는데 돈 듦)

### NPV / IRR / Payback (탭 ② 경제성)
- **NPV > 0**: 사업성 있음
- **IRR > 할인율** (default 8%): 양호
- **Payback < 10년**: 빠른 회수 (CCUS 평균 12~18년)

### Net CO₂ Removed (탭 ③ Lifecycle)
- **A 등급 (>80%)**: voluntary credit 적합
- **B (60-80%)**: 일반 시장 수용
- **C (<60%)**: 추가 절감 필요

## 💡 의사결정 활용 시나리오

| 질문 | 활용 탭 |
|---|---|
| "이 CCS가 흑자 가능?" | 탭 ① 인사이트 + ② 경제성 |
| "어느 인센티브 stack이 best?" | 사이드바 인센티브 + 탭 ② |
| "voluntary credit으로 팔 수 있나?" | 탭 ③ Net CO₂ (등급 확인) |
| "Korean cement에 어떤 기술?" | 프리셋 🇰🇷 시멘트 + ② 경제성 |
| "CBAM 회피 효과는?" | 자매 도구 [CBAM 계산기]({CBAM_TOOL_URL}) |

## ⚠️ 한계점 & 주의사항

1. **TRL 낮은 기술의 데이터** (KIERSOL·DMX·TSA): idealized 파일럿 값 → 상용 시 +10~20% SRD/CAPEX 페널티 가능
2. **K-ETS CCU 차감**: 직접 매출 아님 (조건부 가치 — 회사 배출권 수급 상황 의존)
3. **45Q는 gross 기준**, voluntary credits는 **net removed 기준** (탭 ③ 매출 기준 표 참조)
4. **CAPEX**는 EPC turnkey owner-perspective. NETL "incremental" 대비 ~2× 높음 (탭 ⑦ 방법론)
5. **외부 EPC 견적·실증 데이터로 반드시 보정** 필요 (본 모델은 representative values)

## 🔗 자매 도구

- **🛡️ EU CBAM 계산기**: [{CBAM_TOOL_URL}]({CBAM_TOOL_URL})
  - 한국 산업의 EU 수출 시 CBAM 부담 계산
  - CCS 도입 시 회피 가능액 분석 (본 도구와 연계)

## 📚 자세한 방법론·출처

- **탭 ⑧ 방법론**: 13개 섹션 (지표 정의·규모 효과·LCA·K-ETS 등)
- **탭 ⑨ 참고문헌**: 71개 출처 (NETL/IEAGHG/IRS 45Q/IPCC/peer-reviewed)
""")

if not selected:
    st.warning("⚠️ 사이드바에서 비교할 기술을 1개 이상 선택해주세요.")
    st.stop()

pilot_techs = [LIT[k]["name"] for k in selected if LIT[k]["is_pilot"]]
if pilot_techs:
    st.markdown(
        f"<div class='pilot-warning'>⚠️ <strong>파일럿/실증 데이터 포함:</strong> "
        f"{', '.join(pilot_techs)} — 상용 스케일에서 수치가 변할 수 있습니다.</div>",
        unsafe_allow_html=True,
    )

# ======================================================================
# 결과 계산
# ======================================================================
results = []
for k in selected:
    t = LIT[k]
    we = calc_We(t, T_cool_C, p_final_bar,
                  capture_t_yr=capture_t_yr, capture_eff=capture_eff)
    # 규모·포집율 보정된 SRD를 SPECCA에 사용
    specca = calc_SPECCA(we["SRD_scaled"], we["We_elec"], capture_eff)
    cost = calc_COCA(
        t["CAPEX_per_t"], t["OPEX_solvent"], t["OPEX_other"],
        we["We_elec"], capture_t_yr, lifetime, discount, elec_price,
        capex_mult=ccu["capex_mult"], ccu_share=ccu_share,
        project_multiplier=project_multiplier,
        capture_eff=capture_eff,
    )
    rev = calc_revenue(
        capture_t_yr, ccs_share, ccs_yield,
        ccu_share, ccu["yield"], ccu_price_krw,
        carbon_market_usd, subsidy_usd, extra_revenue_usd,
        fx_krw_per_usd,
    )
    net_coca = cost["COCA"] - rev["rev_per_capture"]

    # 금융 지표 (NPV / IRR / Payback)
    capex_total_usd = cost["eff_capex_per_t"] * capture_t_yr
    fin = calc_financial_metrics(
        annual_cf_usd=annual_profit_usd,
        capex_total_usd=capex_total_usd,
        lifetime_yr=lifetime,
        discount=discount,
    )

    # LCA / Scope 1+2+3 계산
    solvent_factor = SOLVENT_EMISSION_FACTORS.get(k, 1.5)
    lca = calc_lca_emissions(
        srd_GJ_t=we["SRD_scaled"],
        we_elec_GJe_t=we["We_elec"],
        loss_kg_t=t["loss_kg_per_tCO2"],
        heat_factor_kgCO2_GJ=heat_factor,
        grid_factor_gCO2_kWh=grid_factor,
        solvent_factor_kgCO2_kg=solvent_factor,
        capex_per_t_USD=cost["eff_capex_per_t"],
        lifetime_yr=lifetime,
        include_embodied=include_embodied,
    )
    # Net removed = stored × (1 - lifecycle emissions)
    if facility_mode == "CCS":
        gross_per_t = rev["stored_t"] / capture_t_yr if capture_t_yr > 0 else 0  # = ccs_yield
    else:
        gross_per_t = rev["sold_lco2_t"] / capture_t_yr if capture_t_yr > 0 else 0  # = ccu_yield
    net_removed_per_t = gross_per_t - lca["e_total"]
    net_removed_per_t = max(net_removed_per_t, 0)  # 음수 방지 (이론상 가능하지만 표시)
    net_removed_t_yr = net_removed_per_t * capture_t_yr
    crcf_efficiency_pct = (net_removed_per_t / 1.0) * 100  # 1톤 captured → net removed의 %

    # 연간 손익 (annual profit)
    annual_cost_usd = cost["annual_total_usd"]                 # = COCA × capture_t_yr
    annual_revenue_usd = rev["total_revenue"]
    annual_profit_usd = annual_revenue_usd - annual_cost_usd   # 양수 = 흑자
    annual_profit_krw = annual_profit_usd * fx_krw_per_usd

    results.append({
        "key": k,
        "name": t["name"],
        "category": t["category"],
        "is_pilot": t["is_pilot"],
        "SRD": we["SRD_scaled"],     # 규모 보정 후 (display용)
        **we,
        "SPECCA": specca,
        **cost,
        **rev,
        "Net_COCA": net_coca,
        "annual_cost_usd":     annual_cost_usd,
        "annual_revenue_usd":  annual_revenue_usd,
        "annual_profit_usd":   annual_profit_usd,
        "annual_profit_krw":   annual_profit_krw,
        # 금융 지표 (NPV/IRR/Payback)
        "npv":              fin["npv"],
        "irr":              fin["irr"],
        "payback_yr":       fin["payback_yr"],
        "payback_disc_yr":  fin["payback_disc_yr"],
        "profitability_idx": fin["profitability_index"],
        "capex_total":      fin["capex_total"],
        "TRL":              t.get("TRL", 7),
        # LCA / Net CO2 (CRCF/ICVCM)
        **{f"lca_{k_}": v_ for k_, v_ in lca.items()},
        "gross_per_t":         gross_per_t,
        "net_removed_per_t":   net_removed_per_t,
        "net_removed_t_yr":    net_removed_t_yr,
        "crcf_efficiency_pct": crcf_efficiency_pct,
        "solvent_emission_factor": solvent_factor,
        "loss_kg_per_tCO2": t["loss_kg_per_tCO2"],
        "loss_mech": t["loss_mech"],
        "T_regen": t["T_regen"],
        "T_abs": t["T_abs"],
        "source": t["source"],
        "notes": t["notes"],
    })

df = pd.DataFrame(results)

# ======================================================================
# 탭
# ======================================================================
(tab_overall, tab_econ, tab_lca, tab_energy, tab_loss,
 tab_trend, tab_custom, tab_method, tab_refs) = st.tabs([
    "① 종합 비교",
    "② 경제성",
    "③ Lifecycle / Net CO₂",
    "④ 에너지 페널티",
    "⑤ 흡수제/흡착제 손실",
    "⑥ 트렌드",
    "⑦ Custom 입력",
    "⑧ 방법론",
    "⑨ 참고문헌",
])

# ---------- ① 종합 비교 ----------
with tab_overall:
    # ──────────────────────────────────────────────
    # 🎯 자동 인사이트 박스 (메인 상단 - 사용자가 처음 보는 것)
    # ──────────────────────────────────────────────
    if results:
        # 핵심 통계 계산
        min_coca_r = min(results, key=lambda r: r['COCA'])
        min_net_coca_r = min(results, key=lambda r: r['Net_COCA'])
        max_profit_r = max(results, key=lambda r: r['annual_profit_usd'])
        profit_count = sum(1 for r in results if r['annual_profit_usd'] > 0)
        n = len(results)

        # 흑자/적자 판정
        if profit_count == n:
            status_icon, status_text, status_color = "✅", f"전체 {n}/{n} 흑자", "#81C784"
        elif profit_count == 0:
            status_icon, status_text, status_color = "⚠️", f"전체 {n}/{n} 적자 — 인센티브 부족", "#E57373"
        else:
            status_icon, status_text, status_color = "⚖️", f"{profit_count}/{n} 흑자", "#FFB74D"

        # 평균 + 최고 손익
        avg_profit_usd = sum(r['annual_profit_usd'] for r in results) / n
        best_profit_usd = max_profit_r['annual_profit_usd']
        # LCA / Net 효율
        avg_net_pct = sum(r['crcf_efficiency_pct'] for r in results) / n
        best_net_r = max(results, key=lambda r: r['crcf_efficiency_pct'])

        # 자동 인사이트 텍스트
        recommendations = []
        if avg_net_pct < 50:
            recommendations.append(f"⚠️ 평균 Net 효율 {avg_net_pct:.0f}% — 열원·grid 검토 필요 (탭 ⑨)")
        elif avg_net_pct >= 75:
            recommendations.append(f"✅ 평균 Net 효율 {avg_net_pct:.0f}% — voluntary credit 등급 양호")
        if facility_mode == "CCS" and profit_count == 0:
            recommendations.append("💡 인센티브 stack 부족 — 45Q-CCS + 주별 시장 + LCFS 검토")
        if facility_mode == "CCS" and capture_mt_yr < 5 and profit_count < n / 2:
            recommendations.append("💡 소규모 CCS는 적자 valley — 10 Mt 이상 또는 CCU 전환 검토")
        if facility_mode == "CCU" and ccu_grade_key == "food":
            recommendations.append("💡 식품급 CCU는 안정 흑자 모델 — 규모 확장에 비례 수익 증가")
        if not recommendations:
            recommendations.append(f"💡 {min_coca_r['name']}이(가) 가장 효율적 (COCA ${min_coca_r['COCA']:.1f}/t)")

        st.markdown(
            f"""
            <div style='background:linear-gradient(135deg, #1E2128 0%, #2A2F3A 100%);
                        border-left: 4px solid {status_color};
                        border-radius: 6px; padding: 12px 16px; margin-bottom: 12px;'>
                <div style='font-size:0.85rem; color:#8b95a7; margin-bottom: 4px;'>
                    🎯 시뮬레이션 결과 요약
                    <span style='color:{status_color}; font-weight:600;'>
                        · {status_icon} {status_text}
                    </span>
                </div>
                <div style='display:flex; flex-wrap:wrap; gap:18px; margin-top:6px;'>
                    <div>
                        <span style='font-size:0.7rem; color:#8b95a7;'>최저 COCA</span><br>
                        <b style='color:#4FC3F7; font-size:0.95rem;'>{min_coca_r['name']}</b>
                        <span style='color:#E8EAED;'>${min_coca_r['COCA']:.1f}/t</span>
                    </div>
                    <div>
                        <span style='font-size:0.7rem; color:#8b95a7;'>최고 흑자 기술</span><br>
                        <b style='color:#81C784; font-size:0.95rem;'>{max_profit_r['name']}</b>
                        <span style='color:#E8EAED;'>{fmt_money(best_profit_usd, fx_krw_per_usd, display_currency)}/yr</span>
                    </div>
                    <div>
                        <span style='font-size:0.7rem; color:#8b95a7;'>평균 연 손익</span><br>
                        <b style='color:{"#81C784" if avg_profit_usd > 0 else "#E57373"};
                                  font-size:0.95rem;'>
                            {fmt_money(avg_profit_usd, fx_krw_per_usd, display_currency)}/yr
                        </b>
                    </div>
                    <div>
                        <span style='font-size:0.7rem; color:#8b95a7;'>평균 Net 효율 (CRCF)</span><br>
                        <b style='color:{"#81C784" if avg_net_pct >= 75 else "#FFB74D" if avg_net_pct >= 50 else "#E57373"};
                                  font-size:0.95rem;'>
                            {avg_net_pct:.0f}% (Best: {best_net_r['crcf_efficiency_pct']:.0f}% — {SHORT_NAMES.get(best_net_r['key'], best_net_r['name'])})
                        </b>
                    </div>
                </div>
                <div style='margin-top:8px; font-size:0.78rem; color:#B0BEC5;'>
                    {' · '.join(recommendations)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ──────────────────────────────────────────────
    # 💰 연 손익 — 메인 KPI (4대 KPI보다 우선 표시)
    # ──────────────────────────────────────────────
    st.markdown(
        f"<h3 style='margin-top:0; margin-bottom:6px;'>"
        f"💰 {tip('Net COCA', '연 손익')} — 핵심 결과</h3>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"매출 − 비용 = 연 손익. 녹색 = 흑자 / 빨강 = 적자 · 환율 {fx_krw_per_usd:,.0f} KRW/USD",
        unsafe_allow_html=True,
    )
    profit_cards = st.columns(min(len(results), 6))
    sorted_profit = sorted(results, key=lambda r: -r['annual_profit_usd'])  # 흑자 순
    for i, r in enumerate(sorted_profit[:6]):
        with profit_cards[i]:
            profit_usd = r['annual_profit_usd']
            color = "#81C784" if profit_usd > 0 else "#E57373"
            sign_icon = "🟢" if profit_usd > 0 else "🔴"
            money_str = fmt_money(profit_usd, fx_krw_per_usd, display_currency)
            st.markdown(
                f"""
                <div style='background:#1E2128; border-top:3px solid {color};
                            border-radius:6px; padding:10px 12px; height:100px;'>
                    <div style='font-size:0.7rem; color:#8b95a7;'>
                        {sign_icon} {SHORT_NAMES.get(r['key'], r['name'])}
                    </div>
                    <div style='font-size:0.85rem; color:{color}; font-weight:700;
                                margin-top:4px; line-height:1.3;'>
                        {money_str}/yr
                    </div>
                    <div style='font-size:0.65rem; color:#8b95a7; margin-top:4px;'>
                        Net COCA {r['Net_COCA']:+,.1f} $/t
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    with st.expander("📖 **KPI 지표 정의** — 클릭해서 펼치기/접기", expanded=False):
        def_cols = st.columns(4)
        definitions = [
            {"title": "SRD", "full": "Specific Reboiler Duty",
             "unit": "GJ / tCO₂", "color": "#4FC3F7",
             "formula": "Q<sub>regen</sub> / m<sub>CO₂</sub>",
             "desc": "흡수제 재생에 필요한 단위 CO₂당 열량.",
             "hint": "↓ 낮을수록 열효율 우수"},
            {"title": "We", "full": "Equivalent Work (전력등가 일)",
             "unit": "GJe / tCO₂", "color": "#81C784",
             "formula": "We<sub>thermal</sub>(Carnot) + We<sub>elec</sub>",
             "desc": "재생열을 Carnot로 전기등가 환산 + 펌프·압축·냉동기·보조 전력 합.",
             "hint": "↓ 낮을수록 통합 에너지 효율 우수"},
            {"title": "SPECCA", "full": "Specific Primary Energy<br>Consumption for CO₂ Avoided",
             "unit": "MJ / tCO₂", "color": "#FFB74D",
             "formula": "(SRD × 500 + We<sub>elec</sub> × 2,500) / capture",
             "desc": "포집을 위해 추가로 소모하는 1차 에너지를 포집율로 정규화.",
             "hint": "↓ 낮을수록 1차 에너지 효율 우수"},
            {"title": "COCA", "full": "Cost Of CO₂ Avoided / Captured",
             "unit": "USD / tCO₂", "color": "#E57373",
             "formula": "(연환산 CAPEX + OPEX) / 연 포집량",
             "desc": "단위 CO₂당 종합 비용. CAPEX는 CRF로 연환산.",
             "hint": "↓ 낮을수록 경제성 우수"},
        ]
        for col, d in zip(def_cols, definitions):
            with col:
                st.markdown(
                    f"""
                    <div style='background:#1E2128; border-top:3px solid {d["color"]};
                                border-radius:6px; padding:10px 12px; height:230px;
                                display:flex; flex-direction:column;'>
                        <div style='font-size:1.1rem; font-weight:700; color:{d["color"]};
                                    margin-bottom:2px;'>{d["title"]}</div>
                        <div style='font-size:0.7rem; color:#8b95a7; margin-bottom:4px;
                                    line-height:1.2;'>{d["full"]}</div>
                        <div style='font-size:0.75rem; color:#E8EAED; margin-bottom:6px;'>
                            <b>단위</b>: {d["unit"]}
                        </div>
                        <div style='font-size:0.75rem; background:#0E1117; padding:4px 6px;
                                    border-radius:3px; font-family:monospace; color:#B0BEC5;
                                    margin-bottom:6px;'>{d["formula"]}</div>
                        <div style='font-size:0.72rem; color:#B0BEC5; line-height:1.4;
                                    flex:1;'>{d["desc"]}</div>
                        <div style='font-size:0.7rem; color:{d["color"]}; margin-top:4px;
                                    font-weight:600;'>{d["hint"]}</div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown(
            """
            <div style='font-size:0.72rem; color:#8b95a7; margin-top:10px;
                        padding:6px 10px; background:#1E2128; border-radius:4px;'>
            <b>📐 보조 개념</b> &nbsp;·&nbsp;
            <b>Carnot</b>: η<sub>C</sub> = (T<sub>regen</sub> − T<sub>cool</sub>) / T<sub>regen</sub> &nbsp;·&nbsp;
            실효 = η<sub>C</sub> × 0.55 &nbsp;·&nbsp;
            <b>CRF</b>: i(1+i)<sup>n</sup> / [(1+i)<sup>n</sup> − 1] &nbsp;·&nbsp;
            <b>CAP COP</b>: T<sub>abs</sub> / (T<sub>amb</sub> − T<sub>abs</sub>) × 0.55
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")
    st.markdown(
        f"<h3 style='margin-top:8px;'>4대 기술 지표 비교 — "
        f"{tip('SRD')} · {tip('We')} · {tip('SPECCA')} · {tip('COCA')}</h3>",
        unsafe_allow_html=True,
    )
    st.caption("KPI별 순위 정렬 · 🟢 최고 · 🔴 최악 (모든 지표 낮을수록 우수) · 약어에 마우스 올리면 정의")

    kpi_specs = [
        ("SRD", "SRD", "GJ/tCO₂", "{:,.2f}"),
        ("We_total", "We 총합", "GJe/tCO₂", "{:,.2f}"),
        ("SPECCA", "SPECCA", "MJ/tCO₂", "{:,.0f}"),
        ("COCA", "COCA", "USD/tCO₂", "{:,.1f}"),
    ]

    def render_kpi_chart(spec, container):
        key, label, unit, fmt = spec
        sorted_r = sorted(results, key=lambda r: r[key])
        n = len(sorted_r)
        names = [SHORT_NAMES.get(r["key"], r["name"]) for r in sorted_r]
        vals = [r[key] for r in sorted_r]
        colors = []
        for i in range(n):
            if i == 0:
                colors.append("#81C784")
            elif i == n - 1 and n > 1:
                colors.append("#E57373")
            else:
                colors.append("#4FC3F7")
        best = vals[0] if vals else 0
        text_labels = []
        for i, v in enumerate(vals):
            if i == 0:
                text_labels.append(f"★ {fmt.format(v)}")
            else:
                pct = (v - best) / best * 100 if best > 0 else 0
                text_labels.append(f"{fmt.format(v)}  (+{pct:.0f}%)")
        xmax = max(vals) * 1.35 if vals else 1
        f = go.Figure(go.Bar(
            x=vals, y=names, orientation="h",
            marker=dict(color=colors, line=dict(color="rgba(255,255,255,0.15)", width=1)),
            text=text_labels, textposition="outside",
            textfont=dict(size=15, color="#E8EAED"),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>" + label + ": %{x:,.2f}<extra></extra>",
        ))
        f.update_layout(
            title=dict(
                text=f"<b style='font-size:18px;'>{label}</b>  "
                     f"<span style='font-size:13px; color:#8b95a7;'>[{unit}]</span>",
                x=0.02,
            ),
            template="plotly_dark", height=340,
            margin=dict(l=10, r=30, t=55, b=30),
            xaxis=dict(showgrid=True, gridcolor="#2C313C", zeroline=False,
                       range=[0, xmax], tickfont=dict(size=12)),
            yaxis=dict(autorange="reversed", tickfont=dict(size=14, color="#E8EAED")),
            showlegend=False,
            uniformtext=dict(minsize=12, mode="show"),
        )
        container.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    row1 = st.columns(2)
    render_kpi_chart(kpi_specs[0], row1[0])
    render_kpi_chart(kpi_specs[1], row1[1])
    row2 = st.columns(2)
    render_kpi_chart(kpi_specs[2], row2[0])
    render_kpi_chart(kpi_specs[3], row2[1])

    st.markdown("---")
    st.markdown("### 데이터 테이블")
    df["material"] = df["key"].map(MATERIALS)
    show_df = df[["name", "material", "category", "SRD", "We_total", "We_elec",
                  "SPECCA", "COCA", "T_regen", "T_abs", "source"]].copy()
    show_df.columns = ["기술", "흡수제/소재", "분류", "SRD", "We_total", "We_elec",
                       "SPECCA", "COCA", "T_regen[°C]", "T_abs[°C]", "출처"]
    show_df["SRD"] = show_df["SRD"].map(lambda x: f"{x:,.2f}")
    show_df["We_total"] = show_df["We_total"].map(lambda x: f"{x:,.2f}")
    show_df["We_elec"] = show_df["We_elec"].map(lambda x: f"{x:,.2f}")
    show_df["SPECCA"] = show_df["SPECCA"].map(lambda x: f"{x:,.0f}")
    show_df["COCA"] = show_df["COCA"].map(lambda x: f"{x:,.1f}")
    st.dataframe(show_df, use_container_width=True, hide_index=True)

# ---------- ④ 에너지 페널티 ----------
with tab_energy:
    st.markdown("### 전력등가 일(We) 분해 — 스택 막대")
    st.caption("We_thermal: SRD를 Carnot 효율로 전기등가 환산 (참고). We_elec: 펌프·압축·냉동기·보조.")

    components = [
        ("We_pump", "펌프", "#7986CB"),
        ("We_comp", "CO₂ 압축", "#4DD0E1"),
        ("We_chill", "냉동기", "#BA68C8"),
        ("We_aux", "보조", "#A1887F"),
        ("We_thermal_eq", "열 (Carnot 환산)", "#FFB74D"),
    ]

    f = go.Figure()
    names_short = [SHORT_NAMES.get(r["key"], r["name"]) for r in results]
    for col, label, color in components:
        f.add_trace(go.Bar(
            name=label, x=names_short,
            y=[r[col] for r in results],
            marker_color=color,
            hovertemplate="%{x}<br>" + label + ": %{y:.3f} GJe/tCO₂<extra></extra>",
        ))
    f.update_layout(
        barmode="stack", template="plotly_dark",
        height=480, yaxis_title="We [GJe/tCO₂]",
        xaxis_tickangle=0, margin=CHART_MARGIN_STACK,
        legend=dict(orientation="h", y=-0.18),
    )
    st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("---")
    st.markdown("### CAP 냉동기 부하 — 냉각수 온도 민감도")
    st.caption("CAP의 We_chill은 냉각수 온도에 민감. Carnot COP × 0.55.")

    if any(r["category"] == "Chilled NH₃" for r in results):
        T_range = np.arange(5, 46, 2)
        cap_data = LIT["CAP_B12C"]
        # 현재 시나리오 (scale + capture rate)와 일관된 scaled SRD 사용
        cap_srd_scaled = scale_srd(cap_data["SRD"], capture_t_yr) * \
                         capture_rate_factor(capture_eff, SRD_VS_CAPTURE_COEF)
        Q_chill = cap_srd_scaled * 0.18
        chill_we = [chiller_We(Q_chill, cap_data["T_abs"], T) for T in T_range]
        f2 = go.Figure()
        f2.add_trace(go.Scatter(
            x=T_range, y=chill_we, mode="lines+markers",
            line=dict(color="#BA68C8", width=3), marker=dict(size=8),
        ))
        f2.add_vline(x=T_cool_C, line_dash="dash", line_color="#ffc107",
                     annotation_text=f"현재 {T_cool_C}°C")
        f2.update_layout(
            template="plotly_dark", height=350,
            xaxis_title="냉각수 온도 [°C]", yaxis_title="We_chill [GJe/tCO₂]",
        )
        st.plotly_chart(f2, use_container_width=True, config=PLOTLY_CONFIG)
    else:
        st.info("CAP을 선택하면 냉동기 민감도 그래프가 활성화됩니다.")

# ---------- ② 경제성 ----------
with tab_econ:
    st.markdown("### CAPEX (별도) + OPEX 스택 + COCA 요약")

    col1, col2 = st.columns([1, 1])
    names_short = [SHORT_NAMES.get(r["key"], r["name"]) for r in results]

    with col1:
        f = go.Figure()
        f.add_trace(go.Bar(
            x=names_short, y=[r["annual_capex"] for r in results],
            marker_color="#4FC3F7",
            text=[f"{r['annual_capex']:,.1f}" for r in results],
            textposition="outside",
        ))
        scale_pct_calc = ((REF_CAPTURE_MT_YR / capture_mt_yr) ** (1 - CAPEX_SCALE_EXPONENT) - 1) * 100
        scale_label = (f"규모 +{scale_pct_calc:.0f}%" if scale_pct_calc > 1
                       else f"규모 {scale_pct_calc:.0f}%" if scale_pct_calc < -1
                       else "규모 ≈ 0%")
        proj_label = f"{project['label'].split(' ', 1)[1] if ' ' in project['label'] else project['label']} ×{project_multiplier:.2f}"
        f.update_layout(
            title=(f"연환산 CAPEX [USD/tCO₂] · 수명 {lifetime}년 · 할인율 {discount*100:.1f}%"
                   f"<br><span style='font-size:11px; color:#8b95a7;'>"
                   f"포집 {capture_mt_yr:.1f} Mt/yr → {scale_label} · 시나리오: {proj_label}"
                   f"</span>"),
            template="plotly_dark", height=420,
            xaxis_tickangle=0, margin=dict(l=10, r=10, t=70, b=80),
        )
        st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    with col2:
        f = go.Figure()
        for col_, label, color in [
            ("opex_solvent", "용매/소재", "#81C784"),
            ("opex_other", "유틸·인건·정비", "#FFB74D"),
            ("elec_cost", "전력 비용", "#E57373"),
        ]:
            f.add_trace(go.Bar(
                name=label, x=names_short,
                y=[r[col_] for r in results], marker_color=color,
            ))
        f.update_layout(
            title="OPEX 분해 [USD/tCO₂]",
            barmode="stack", template="plotly_dark", height=400,
            xaxis_tickangle=0, margin=CHART_MARGIN_STACK,
            legend=dict(orientation="h", y=-0.20),
        )
        st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("---")
    st.markdown("### COCA 요약")

    f = go.Figure()
    f.add_trace(go.Bar(
        x=[SHORT_NAMES.get(r["key"], r["name"]) for r in results],
        y=[r["COCA"] for r in results],
        marker_color=["#FFD54F" if r["is_pilot"] else "#4DD0E1" for r in results],
        text=[f"{r['COCA']:,.1f}" for r in results],
        textposition="outside",
    ))
    f.update_layout(
        title=f"COCA [USD/tCO₂] (연간 {capture_mt_yr:.1f} Mt 기준)",
        template="plotly_dark", height=400,
        xaxis_tickangle=0, margin=CHART_MARGIN,
    )
    st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    cost_df = pd.DataFrame([{
        "기술": r["name"],
        "연환산 CAPEX": f"{r['annual_capex']:,.1f}",
        "OPEX 합": f"{r['opex_total']:,.1f}",
        "  └ 용매": f"{r['opex_solvent']:,.1f}",
        "  └ 기타": f"{r['opex_other']:,.1f}",
        "  └ 전력": f"{r['elec_cost']:,.1f}",
        "COCA": f"{r['COCA']:,.1f}",
        "연간 총비용 [M$]": f"{r['annual_total_usd']/1e6:,.1f}",
    } for r in results])
    st.dataframe(cost_df, use_container_width=True, hide_index=True)

    # ── 매출/보조금/Net COCA ──
    st.markdown("---")
    st.markdown(f"### 💰 매출·보조금 반영 — **Net COCA** ({facility_mode} 모드)")

    if facility_mode == "CCS":
        st.caption(
            f"🏔️ **CCS 모드** · 격리수율 **{ccs_yield*100:.0f}%** · "
            f"인센티브 stack: 시장 ${carbon_market_usd:.0f} + 보조금 ${subsidy_usd:.0f} "
            f"+ 추가 ${extra_revenue_usd:.0f} = **${total_incentive_usd:.1f}/t** · "
            f"환율 **{fx_krw_per_usd:,.0f} KRW/USD**"
        )
    else:
        st.caption(
            f"🥤 **CCU 모드** · {ccu['label']} · 수율 **{ccu['yield']*100:.0f}%** · "
            f"판매가 **{ccu_price_krw:,} KRW/t** + 보조금 ${subsidy_usd:.0f} "
            f"+ 추가 ${extra_revenue_usd:.0f} · "
            f"CAPEX adder **+{(ccu['capex_mult']-1)*100:.0f}%** · "
            f"환율 **{fx_krw_per_usd:,.0f} KRW/USD**"
        )

    short_x = [SHORT_NAMES.get(r["key"], r["name"]) for r in results]

    f_net = go.Figure()
    f_net.add_trace(go.Bar(
        name="COCA (비용)",
        x=short_x, y=[r["COCA"] for r in results],
        marker_color="#E57373",
        text=[f"{r['COCA']:,.1f}" for r in results], textposition="inside",
        textfont=dict(size=13, color="white"),
    ))
    f_net.add_trace(go.Bar(
        name="− 매출/보조금",
        x=short_x, y=[-r["rev_per_capture"] for r in results],
        marker_color="#81C784",
        text=[f"−{r['rev_per_capture']:,.1f}" for r in results], textposition="inside",
        textfont=dict(size=13, color="white"),
    ))
    # Net COCA — 큰 노란 다이아몬드 + 흰 테두리 + 검은 외곽
    f_net.add_trace(go.Scatter(
        name="◆ Net COCA",
        x=short_x, y=[r["Net_COCA"] for r in results],
        mode="markers+text",
        marker=dict(
            size=26, color="#FFEB3B", symbol="diamond",
            line=dict(color="#212121", width=3),
        ),
        text=[f"<b>{r['Net_COCA']:+,.1f}</b>" for r in results],
        textposition="top center",
        textfont=dict(size=17, color="#FFEB3B"),
        hovertemplate="<b>%{x}</b><br>Net COCA: %{y:,.1f} USD/t<extra></extra>",
    ))
    # Net COCA 라벨 위에 검은 박스 그림자 효과 (가독성)
    for r in results:
        x = SHORT_NAMES.get(r["key"], r["name"])
        f_net.add_annotation(
            x=x, y=r["Net_COCA"],
            text=f"<b>Net: {r['Net_COCA']:+,.1f}</b>",
            showarrow=False,
            yshift=28,
            font=dict(size=14, color="#FFEB3B"),
            bgcolor="rgba(0,0,0,0.75)",
            bordercolor="#FFEB3B",
            borderwidth=1,
            borderpad=4,
        )

    f_net.add_hline(y=0, line_color="white", line_width=1.5, line_dash="dot")
    f_net.update_layout(
        title="COCA vs Net COCA [USD/tCO₂포집] — Net 음수 = 흑자",
        template="plotly_dark", height=520, barmode="relative",
        margin=dict(l=10, r=10, t=60, b=80),
        legend=dict(orientation="h", y=-0.12),
        xaxis_tickangle=0,
    )
    # Net COCA 막대 아래에 텍스트가 안잘리도록 우측 여유
    st.plotly_chart(f_net, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("##### 매출/보조금 상세")
    rev_rows = []
    for r in results:
        rev_rows.append({
            "기술": r["name"],
            "포집량 [kt/yr]": f"{capture_t_yr/1000:,.1f}",
            "격리량 [kt/yr]": f"{r['stored_t']/1000:,.1f}" if facility_mode == "CCS" else "—",
            "출하량 [kt/yr]": f"{r['sold_lco2_t']/1000:,.1f}" if facility_mode == "CCU" else "—",
            "배출권 [M$/yr]": f"{r['market_revenue']/1e6:,.2f}",
            "보조금 [M$/yr]": f"{r['subsidy']/1e6:,.2f}",
            "추가매출 [M$/yr]": f"{r.get('extra_revenue', 0)/1e6:,.2f}",
            "CCU 매출 [M$/yr]": f"{r['ccu_revenue']/1e6:,.2f}",
            "총 매출 [M$/yr]": f"{r['total_revenue']/1e6:,.2f}",
            "총 매출 (원)": fmt_krw_amt(r['total_revenue'] * fx_krw_per_usd),
            "COCA": f"{r['COCA']:,.1f}",
            "Net COCA": f"{r['Net_COCA']:+,.1f}",
        })
    st.dataframe(pd.DataFrame(rev_rows), use_container_width=True, hide_index=True)

    if facility_mode == "CCU" and ccu["capex_mult"] > 1.0:
        base_capex_estimate = results[0]['eff_capex_per_t'] - results[0]['capex_adder']
        st.info(
            f"💡 **CCU 정제 CAPEX adder**: 기본 CAPEX의 +{(ccu['capex_mult']-1)*100:.0f}% "
            f"(예: {results[0]['name']} → ${base_capex_estimate:,.0f}/(t/yr) "
            f"→ ${results[0]['eff_capex_per_t']:,.0f}/(t/yr), "
            f"adder ${results[0]['capex_adder']:,.0f}/(t/yr))"
        )

    # ─────────────────────────────────────────────
    # 연간 손익 (Annual Profit / Loss) — 사업 관점
    # ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🪙 연간 손익 분석 — 시설 단위 수익성")
    st.caption(
        f"연간 매출 − 연간 비용 = 연간 손익. "
        f"포집 {capture_mt_yr:.1f} Mt/yr · 환율 {fx_krw_per_usd:,.0f} KRW/USD"
    )

    # 손익 막대 차트 (USD)
    profits_usd = [r["annual_profit_usd"] / 1e6 for r in results]  # M$/yr
    profit_colors = ["#81C784" if p > 0 else "#E57373" for p in profits_usd]

    f_profit = go.Figure()
    f_profit.add_trace(go.Bar(
        x=short_x,
        y=profits_usd,
        marker_color=profit_colors,
        text=[
            f"<b>{p:+,.0f}</b> M$<br>"
            f"<span style='font-size:11px;'>"
            f"({fmt_krw_amt(p * 1e6 * fx_krw_per_usd, sign=True)})</span>"
            for p in profits_usd
        ],
        textposition="outside",
        textfont=dict(size=14),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>"
                      "연 손익: %{y:+,.0f} M$/yr<extra></extra>",
    ))
    f_profit.add_hline(y=0, line_color="white", line_width=1.5)
    ymin = min(profits_usd) * 1.3 if min(profits_usd) < 0 else min(profits_usd) - abs(min(profits_usd))*0.1
    ymax = max(profits_usd) * 1.4 if max(profits_usd) > 0 else max(profits_usd) + abs(max(profits_usd))*0.1
    f_profit.update_layout(
        title="연간 손익 [M$/yr] · 녹색=흑자 / 빨강=적자",
        template="plotly_dark", height=420,
        margin=dict(l=10, r=10, t=60, b=40),
        xaxis_tickangle=0,
        yaxis=dict(range=[ymin, ymax], zeroline=True, zerolinecolor="white",
                   zerolinewidth=2),
        showlegend=False,
    )
    st.plotly_chart(f_profit, use_container_width=True, config=PLOTLY_CONFIG)

    # 연간 손익 카드 (선택된 모든 기술)
    st.markdown("##### 💵 연간 손익 카드")
    profit_cols = st.columns(min(len(results), 6))
    for i, r in enumerate(results[:6]):
        with profit_cols[i]:
            profit_m_usd = r["annual_profit_usd"] / 1e6
            color = "#81C784" if profit_m_usd > 0 else "#E57373"
            sign_label = "흑자" if profit_m_usd > 0 else "적자"
            st.markdown(
                f"""
                <div style='background:#1E2128; border-top:3px solid {color};
                            border-radius:6px; padding:8px 10px;'>
                    <div style='font-size:0.75rem; color:#8b95a7;'>
                        {SHORT_NAMES.get(r['key'], r['name'])} — <b style='color:{color};'>{sign_label}</b>
                    </div>
                    <div style='font-size:1.0rem; color:{color}; font-weight:700;
                                margin-top:3px;'>
                        {profit_m_usd:+,.0f} M$/yr
                    </div>
                    <div style='font-size:0.85rem; color:#E8EAED;'>
                        {fmt_krw_amt(r['annual_profit_krw'], sign=True)}/yr
                    </div>
                    <div style='font-size:0.7rem; color:#8b95a7; margin-top:4px;'>
                        매출 ${r['annual_revenue_usd']/1e6:,.0f}M − 비용 ${r['annual_cost_usd']/1e6:,.0f}M
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 연간 손익 상세 테이블
    st.markdown("##### 손익 상세")
    profit_df = pd.DataFrame([{
        "기술": r["name"],
        "연 매출 [M$]":   f"{r['annual_revenue_usd']/1e6:,.1f}",
        "연 매출 (원)":   fmt_krw_amt(r['annual_revenue_usd'] * fx_krw_per_usd),
        "연 비용 [M$]":   f"{r['annual_cost_usd']/1e6:,.1f}",
        "연 비용 (원)":   fmt_krw_amt(r['annual_cost_usd'] * fx_krw_per_usd),
        "연 손익 [M$]":   f"{r['annual_profit_usd']/1e6:+,.1f}",
        "연 손익 (원)":   fmt_krw_amt(r['annual_profit_krw'], sign=True),
        "ROI [%]":        f"{r['annual_profit_usd']/r['annual_cost_usd']*100:+,.1f}" if r['annual_cost_usd'] > 0 else "—",
        "Net COCA [USD/t]": f"{r['Net_COCA']:+,.1f}",
    } for r in results])
    st.dataframe(profit_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown(f"##### 💴 단위 CO₂당 KRW 요약 (환율 {fx_krw_per_usd:,.0f} KRW/USD)")
    krw_cols = st.columns(min(len(results), 4))
    for i, r in enumerate(results[:4]):
        with krw_cols[i]:
            st.metric(
                f"{SHORT_NAMES.get(r['key'], r['name'])} Net COCA",
                f"{r['Net_COCA']*fx_krw_per_usd:+,.0f} 원/t",
                delta=f"COCA: {r['COCA']*fx_krw_per_usd:,.0f} 원/t",
                delta_color="off",
            )

    # ───────────────────────────────────────
    # 📈 NPV / IRR / Payback (사업성 지표)
    # ───────────────────────────────────────
    st.markdown("---")
    st.markdown(f"### 📈 사업성 지표 — {tip('NPV', 'NPV')} · "
                 f"IRR · Payback Period · Profitability Index",
                 unsafe_allow_html=True)
    st.caption(
        f"수명 {lifetime}년 · 할인율 {discount*100:.1f}% · 초기 CAPEX = 실효 CAPEX × 연 포집량 · "
        f"연 cash flow = 연 손익 (보조금·매출 stack 반영)"
    )

    # 카드: 각 기술별 NPV·IRR·Payback
    fin_cols = st.columns(min(len(results), 6))
    for i, r in enumerate(results[:6]):
        with fin_cols[i]:
            npv_color = "#81C784" if r["npv"] > 0 else "#E57373"
            irr_str = f"{r['irr']*100:.1f}%" if r["irr"] is not None else "N/A"
            irr_color = ("#81C784" if (r["irr"] is not None and r["irr"] > discount)
                         else "#E57373")
            pb_str = f"{r['payback_yr']:.1f}년" if r["payback_yr"] else "회수불가"
            pb_color = ("#81C784" if (r["payback_yr"] and r["payback_yr"] < 10)
                        else "#FFB74D" if (r["payback_yr"] and r["payback_yr"] < 20)
                        else "#E57373")
            st.markdown(
                f"""
                <div style='background:#1E2128; border-top:3px solid {npv_color};
                            border-radius:6px; padding:8px 10px;'>
                    <div style='font-size:0.7rem; color:#8b95a7;'>
                        {SHORT_NAMES.get(r['key'], r['name'])}
                    </div>
                    <div style='font-size:0.78rem; margin-top:6px;'>
                        <b style='color:{npv_color};'>NPV: {fmt_money(r['npv'], fx_krw_per_usd, display_currency)}</b>
                    </div>
                    <div style='font-size:0.75rem; color:#B0BEC5; margin-top:3px;'>
                        IRR: <b style='color:{irr_color};'>{irr_str}</b>
                    </div>
                    <div style='font-size:0.75rem; color:#B0BEC5; margin-top:3px;'>
                        회수: <b style='color:{pb_color};'>{pb_str}</b>
                    </div>
                    <div style='font-size:0.7rem; color:#8b95a7; margin-top:3px;'>
                        PI: {r['profitability_idx']:.2f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 종합 사업성 표
    st.markdown("##### 사업성 상세")
    fin_df = pd.DataFrame([{
        "기술":           r["name"],
        "TRL":            f"TRL {r['TRL']}",
        "초기 CAPEX":     fmt_money(r["capex_total"], fx_krw_per_usd, display_currency),
        "연 손익":        fmt_money(r["annual_profit_usd"], fx_krw_per_usd, display_currency),
        "NPV":            fmt_money(r["npv"], fx_krw_per_usd, display_currency),
        "IRR [%]":        f"{r['irr']*100:.1f}" if r["irr"] is not None else "N/A",
        "단순 회수 [yr]": f"{r['payback_yr']:.1f}" if r["payback_yr"] else "N/A",
        "할인 회수 [yr]": f"{r['payback_disc_yr']}" if r["payback_disc_yr"] else "N/A",
        "PI":             f"{r['profitability_idx']:.2f}",
    } for r in results])
    st.dataframe(fin_df, use_container_width=True, hide_index=True)

    st.info(
        f"💡 **해석 가이드**: "
        f"NPV > 0 → 사업성 있음 · IRR > {discount*100:.0f}% (할인율) → 양호 · "
        f"Payback < 10년 → 빠른 회수 · PI > 1.0 → 투자 회수 가능 · "
        f"PI > 1.5 → 매우 양호 (CCUS 평균 0.7~1.3 수준)"
    )

    # ───────────────────────────────────────
    # 🌪️ Tornado Sensitivity (어떤 변수가 가장 영향?)
    # ───────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🌪️ 민감도 분석 (Tornado) — Net COCA 영향도")
    st.caption(
        "각 입력 ±20% (포집율은 ±5%p) 변동 시 Net COCA 변화량. "
        "막대가 길수록 결과에 큰 영향 → 의사결정 시 핵심 검토 변수"
    )

    # 첫 번째 기술 기준으로 sensitivity 계산
    _r0 = results[0]
    base_net = _r0["Net_COCA"]

    # 분석적 근사 (numerical robust)
    sensitivities = {
        "💚 시장+보조금 인센티브": 0.20 * _r0["rev_per_capture"],
        "🏗️ CAPEX (project mult)": 0.20 * _r0["annual_capex"],
        "📉 포집량 (규모 효과)":     0.063 * _r0["annual_capex"],
        "🔥 포집율 (±5%p)":          0.05 * (_r0["annual_capex"] + _r0["elec_cost"]),
        "💰 할인율 (±2%p)":          0.15 * _r0["annual_capex"],
        "⚡ 전기 가격":              0.20 * _r0["elec_cost"],
    }
    # CCU 모드 추가
    if facility_mode == "CCU" and _r0.get("ccu_revenue", 0) > 0:
        sensitivities["🥤 액화탄산 판매가"] = 0.20 * _r0["ccu_revenue"] / capture_t_yr

    # 절대값 큰 순으로 정렬
    sorted_sens = sorted(sensitivities.items(), key=lambda x: -abs(x[1]))
    labels = [x[0] for x in sorted_sens]
    values = [x[1] for x in sorted_sens]

    f_tornado = go.Figure()
    f_tornado.add_trace(go.Bar(
        name="+ 변동",
        x=values,
        y=labels,
        orientation="h",
        marker_color="#E57373",
        text=[f"+{v:,.1f} $/t" for v in values],
        textposition="outside",
    ))
    f_tornado.add_trace(go.Bar(
        name="− 변동",
        x=[-v for v in values],
        y=labels,
        orientation="h",
        marker_color="#81C784",
        text=[f"−{v:,.1f} $/t" for v in values],
        textposition="outside",
    ))
    f_tornado.add_vline(x=0, line_color="white", line_width=1.5)
    f_tornado.update_layout(
        title=f"Tornado: {SHORT_NAMES.get(_r0['key'], _r0['name'])} 기준 · "
              f"Base Net COCA = {base_net:+,.1f} $/t",
        template="plotly_dark", height=400,
        margin=dict(l=10, r=80, t=60, b=40),
        barmode="overlay",
        xaxis_title="Net COCA 변동 [USD/t]",
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", y=-0.18),
    )
    st.plotly_chart(f_tornado, use_container_width=True, config=PLOTLY_CONFIG)

    st.caption(
        f"💡 **{labels[0]}** 가 가장 큰 영향 (±{abs(values[0]):,.1f} $/tCO₂). "
        f"의사결정 시 우선 정밀화 필요. (분석적 근사 — Tier B)"
    )

    # ───────────────────────────────────────
    # 🎯 CO₂ 가격 breakeven 자동 탐지
    # ───────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🎯 흑자 진입 인센티브 — CO₂ 가격 Breakeven")
    st.caption(
        "Net COCA = 0 (손익분기) 도달에 필요한 추가 인센티브 단가. "
        "현재 매출/보조금 stack에서 얼마나 더 받아야 흑자?"
    )

    # 각 기술별 breakeven 계산
    if facility_mode == "CCS":
        yield_label = "격리량 기준"
        yield_factor = ccs_yield
    else:
        yield_label = "출하량 기준"
        yield_factor = ccu["yield"]

    breakeven_rows = []
    for r in results:
        if r["Net_COCA"] <= 0:
            # 이미 흑자
            status = "✅ 이미 흑자"
            extra_needed_per_capture = 0.0
            extra_per_qualifying = 0.0
            margin = abs(r["Net_COCA"])
        else:
            # 적자 — 추가 인센티브 필요
            extra_needed_per_capture = r["Net_COCA"]    # USD/t captured
            # 격리/출하량 기준 단가 (실제 인센티브 가격)
            extra_per_qualifying = (extra_needed_per_capture / yield_factor
                                    if yield_factor > 0 else 0)
            status = "⚠️ 적자"
            margin = 0
        breakeven_rows.append({
            "기술": r["name"],
            "현재 Net COCA [$/t]":    f"{r['Net_COCA']:+,.1f}",
            "상태":                   status,
            f"필요 추가 인센티브 ({yield_label}) [$/t]":
                                      f"{extra_per_qualifying:,.1f}" if extra_per_qualifying > 0 else "0 (불필요)",
            "흑자 여유 [$/t]":        f"{margin:,.1f}" if margin > 0 else "—",
        })

    st.dataframe(pd.DataFrame(breakeven_rows), use_container_width=True, hide_index=True)

    # 시각화 — 각 기술의 breakeven gap
    short_x = [SHORT_NAMES.get(r["key"], r["name"]) for r in results]
    f_be = go.Figure()
    gap_values = []
    for r in results:
        if r["Net_COCA"] > 0:
            gap = r["Net_COCA"] / yield_factor if yield_factor > 0 else 0
            gap_values.append(gap)
        else:
            gap_values.append(0)
    colors_be = ["#E57373" if g > 0 else "#81C784" for g in gap_values]
    f_be.add_trace(go.Bar(
        x=short_x, y=gap_values,
        marker_color=colors_be,
        text=[f"+${g:,.1f}/t" if g > 0 else "흑자" for g in gap_values],
        textposition="outside",
    ))
    f_be.update_layout(
        title=f"흑자 진입 위해 추가로 필요한 인센티브 ({yield_label}, USD/t)",
        template="plotly_dark", height=380,
        margin=dict(l=10, r=10, t=60, b=40),
        yaxis_title=f"추가 인센티브 [USD/t {yield_label}]",
        showlegend=False,
    )
    st.plotly_chart(f_be, use_container_width=True, config=PLOTLY_CONFIG)

    # 정책 시사점
    avg_gap = sum(g for g in gap_values if g > 0) / max(1, sum(1 for g in gap_values if g > 0))
    n_breakeven = sum(1 for g in gap_values if g == 0)
    st.info(
        f"🏛️ **정책 시사점**: 선택된 {len(results)}개 기술 중 "
        f"**{n_breakeven}개가 현재 인센티브 stack으로 흑자 진입**. "
        f"나머지는 평균 **+${avg_gap:,.1f}/t** 추가 인센티브 필요. "
        f"\n\n"
        f"**참고**: 45Q-CCS $85/t = 미국 IRA 한도. NL SDE++ €110 ≈ $120, UK CfD £150 ≈ $180 — "
        f"이 수준 이상의 보조금이 있어야 mid-scale CCS 흑자 가능."
    )

# ---------- ⑤ 흡수제/흡착제 손실 ----------
with tab_loss:
    st.markdown("### 소재 손실 — 메커니즘별 비교")
    st.caption("습식: 분해/휘발 (kg/tCO₂). 고체: 사이클 열화/마모.")

    f = go.Figure()
    f.add_trace(go.Bar(
        x=[SHORT_NAMES.get(r["key"], r["name"]) for r in results],
        y=[r["loss_kg_per_tCO2"] for r in results],
        marker_color="#E57373",
        text=[f"{r['loss_kg_per_tCO2']:,.2f}" for r in results],
        textposition="outside",
        customdata=[r["name"] for r in results],
        hovertemplate="<b>%{customdata}</b><br>손실: %{y:,.2f} kg/tCO₂<extra></extra>",
    ))
    f.update_layout(
        title="소재 손실 [kg/tCO₂]",
        template="plotly_dark", height=400,
        xaxis_tickangle=0, margin=CHART_MARGIN,
        yaxis_type="log", yaxis_title="kg/tCO₂ (log scale)",
    )
    st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    loss_df = pd.DataFrame([{
        "기술": r["name"],
        "흡수제/소재": MATERIALS.get(r["key"], "—"),
        "분류": r["category"],
        "손실 [kg/tCO₂]": f"{r['loss_kg_per_tCO2']:,.2f}",
        "메커니즘": r["loss_mech"],
        "비고": LIT[r["key"]]["notes"],
    } for r in results])
    st.dataframe(loss_df, use_container_width=True, hide_index=True)

    st.info(
        "📌 **CaL의 30 kg/tCO₂**는 makeup limestone 다량 투입(저비용·다소비) 특성. "
        "**TSA의 2 kg/tCO₂**는 attrition + 사이클 열화 누적 환산값."
    )

# ---------- ⑥ 트렌드 ----------
with tab_trend:
    st.markdown("### SRD vs We 산포도 — 문헌 회귀")
    st.caption("선택된 기술 + LIT 전체 데이터의 회귀선.")

    all_pts = []
    for k, t in LIT.items():
        we = calc_We(t, T_cool_C, p_final_bar)
        all_pts.append({
            "name": t["name"],
            "short": SHORT_NAMES.get(k, t["name"]),
            "SRD": t["SRD"],
            "We_elec": we["We_elec"], "We_total": we["We_total"],
            "category": t["category"], "is_pilot": t["is_pilot"],
            "selected": k in selected,
        })
    pts_df = pd.DataFrame(all_pts)

    z = np.polyfit(pts_df["SRD"], pts_df["We_total"], 1)
    x_fit = np.linspace(pts_df["SRD"].min() * 0.9, pts_df["SRD"].max() * 1.1, 50)
    y_fit = np.polyval(z, x_fit)

    f = go.Figure()
    for cat in pts_df["category"].unique():
        sub = pts_df[pts_df["category"] == cat]
        f.add_trace(go.Scatter(
            x=sub["SRD"], y=sub["We_total"],
            mode="markers+text",
            text=sub["short"], textposition="top center",
            customdata=sub["name"],
            hovertemplate="<b>%{customdata}</b><br>SRD: %{x:.2f}<br>We: %{y:.2f}<extra></extra>",
            name=cat,
            marker=dict(
                size=[18 if s else 12 for s in sub["selected"]],
                line=dict(width=[3 if s else 1 for s in sub["selected"]],
                          color="white"),
                symbol=["diamond" if p else "circle" for p in sub["is_pilot"]],
            ),
        ))
    f.add_trace(go.Scatter(
        x=x_fit, y=y_fit, mode="lines",
        line=dict(color="#ffc107", dash="dash"),
        name=f"회귀: We = {z[0]:.3f}·SRD + {z[1]:.3f}",
    ))
    f.update_layout(
        template="plotly_dark", height=520,
        xaxis_title="SRD [GJ/tCO₂]", yaxis_title="We 총합 [GJe/tCO₂]",
    )
    st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("**해석:** 회귀선 아래에 위치하면 동일 SRD 대비 보조전력이 효율적인 기술입니다.")

# ---------- ⑦ Custom 입력 ----------
with tab_custom:
    st.markdown("### Custom 기술 입력")
    st.caption("실증 데이터·신규 흡수제를 직접 입력해 비교에 추가할 수 있습니다.")

    with st.form("custom_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("기술명", value="My Custom Solvent")
            category = st.selectbox("분류",
                ["Amine", "Hot Carbonate", "Chilled NH₃", "Biphasic",
                 "Solid Sorbent", "CaO/CaCO₃", "Other"])
            srd = st.number_input("SRD [GJ/tCO₂]", 1.0, 5.0, 2.5, 0.05)
            T_regen = st.number_input("재생 온도 [°C]", 80, 950, 120)
            T_abs = st.number_input("흡수 온도 [°C]", 0, 700, 40)
        with c2:
            we_pump = st.number_input("We_pump [GJe/tCO₂]", 0.0, 0.1, 0.015, 0.001, format="%.3f")
            we_comp = st.number_input("We_comp [GJe/tCO₂]", 0.05, 0.6, 0.40, 0.01)
            we_chill = st.number_input("We_chill [GJe/tCO₂]", 0.0, 0.5, 0.0, 0.01)
            we_aux = st.number_input("We_aux [GJe/tCO₂]", 0.0, 0.3, 0.05, 0.01)
        with c3:
            capex = st.number_input("CAPEX [USD/(t/yr)]", 500, 3000, 1100, 50, format="%d")
            opex_sol = st.number_input("OPEX 용매 [USD/tCO₂]", 0.0, 5.0, 1.5, 0.1)
            opex_oth = st.number_input("OPEX 기타 [USD/tCO₂]", 5.0, 25.0, 12.0, 0.5)
            loss = st.number_input("손실 [kg/tCO₂]", 0.0, 50.0, 1.0, 0.1)
            p_regen = st.number_input("재생 압력 [bar]", 1.0, 30.0, 1.8, 0.1)

        submit = st.form_submit_button("계산 ▶")

    if submit:
        custom = {
            "name": name, "category": category, "SRD": srd,
            "T_regen": T_regen, "T_abs": T_abs, "p_regen_bar": p_regen,
            "We_pump": we_pump, "We_comp": we_comp,
            "We_chill": we_chill, "We_aux": we_aux,
            "CAPEX_per_t": capex, "OPEX_solvent": opex_sol,
            "OPEX_other": opex_oth, "loss_kg_per_tCO2": loss,
            "loss_mech": "사용자 정의", "is_pilot": True,
        }
        # 메인 결과 루프와 동일한 파라미터 셋 사용 (포집율, 프로젝트 유형, CCU 등급 모두 반영)
        we = calc_We(custom, T_cool_C, p_final_bar,
                     capture_t_yr=capture_t_yr, capture_eff=capture_eff)
        specca = calc_SPECCA(we["SRD_scaled"], we["We_elec"], capture_eff)
        cost = calc_COCA(
            capex, opex_sol, opex_oth, we["We_elec"],
            capture_t_yr, lifetime, discount, elec_price,
            capex_mult=ccu["capex_mult"], ccu_share=ccu_share,
            project_multiplier=project_multiplier,
            capture_eff=capture_eff,
        )

        st.success(f"✅ **{name}** 계산 완료")
        c = st.columns(4)
        c[0].metric("SRD", f"{srd:,.2f} GJ/tCO₂")
        c[1].metric("We 총합", f"{we['We_total']:,.3f} GJe/tCO₂")
        c[2].metric("SPECCA", f"{specca:,.0f} MJ/tCO₂")
        c[3].metric("COCA", f"{cost['COCA']:,.1f} USD/tCO₂")

        comp_df = pd.DataFrame([
            {"기술": r["name"], "SRD": r["SRD"], "We_total": r["We_total"],
             "SPECCA": r["SPECCA"], "COCA": r["COCA"]}
            for r in results
        ] + [{"기술": f"⭐ {name} (Custom)", "SRD": srd,
              "We_total": we["We_total"], "SPECCA": specca, "COCA": cost["COCA"]}])
        for col_ in ["SRD", "We_total"]:
            comp_df[col_] = comp_df[col_].map(lambda x: f"{x:,.2f}")
        comp_df["SPECCA"] = comp_df["SPECCA"].map(lambda x: f"{x:,.0f}")
        comp_df["COCA"] = comp_df["COCA"].map(lambda x: f"{x:,.1f}")
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

# ---------- ⑨ 참고문헌 ----------
with tab_refs:
    st.markdown("### 📚 참고문헌 및 계산 근거 (Full Audit Trail)")
    st.caption(f"총 {len(REFS)}개 출처 — 각 LIT 수치, 계산식, 경제성 가정의 근거")

    cat_labels = {
        "report": "📄 정부·국제기구 보고서",
        "paper": "📑 학술 논문 (Peer-reviewed)",
        "methodology": "🔧 방법론 · 교과서 · 표준",
    }

    for cat_key, cat_label in cat_labels.items():
        st.markdown(f"#### {cat_label}")
        cat_refs = [(k, v) for k, v in REFS.items() if v["cat"] == cat_key]
        for k, r in cat_refs:
            url_md = f" 🔗 [link]({r['url']})" if r["url"] else ""
            st.markdown(
                f"<div style='background:#1E2128; padding:8px 12px; margin:6px 0; "
                f"border-left:3px solid #4FC3F7; border-radius:4px;'>"
                f"<b style='color:#4FC3F7;'>[{k}]</b>{url_md}<br>"
                f"<span style='font-size:0.85rem; color:#E8EAED;'>{r['cite']}</span><br>"
                f"<span style='font-size:0.78rem; color:#8b95a7;'>"
                f"<b>사용처:</b> {r['used_for']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.markdown("")

    st.markdown("---")
    st.markdown("### 🧪 기술별 LIT 수치의 출처 매핑")

    map_rows = []
    for k, t in LIT.items():
        ref_ids = LIT_REFS.get(k, [])
        ref_str = ", ".join(f"[{r}]" for r in ref_ids) if ref_ids else "—"
        map_rows.append({
            "기술": t["name"],
            "SRD [GJ/tCO₂]": f"{t['SRD']:,.2f}",
            "CAPEX [USD/(t/yr)]": f"{t['CAPEX_per_t']:,}",
            "손실 [kg/tCO₂]": f"{t['loss_kg_per_tCO2']:,.1f}",
            "출처 ID": ref_str,
        })
    st.dataframe(pd.DataFrame(map_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 🧮 계산식 ↔ 출처 매핑")

    formula_rows = []
    for formula, ref_ids in FORMULA_REFS.items():
        formula_rows.append({
            "수식 / 가정": formula,
            "출처": ", ".join(f"[{r}]" for r in ref_ids),
        })
    st.dataframe(pd.DataFrame(formula_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 📐 지표 정의 (수식 정리)")
    st.code("""
[열역학 1차]
  Carnot η = (T_h - T_c) / T_h          [Bejan2016]
  실효 η   = Carnot η × 0.55             [Kotas1985]

[전력등가 일]
  We_thermal_eq = SRD × Carnot η × 0.55
  We_pump   = LIT 고정값
  We_comp   = LIT × log(p_final / p_regen) / log(152 / 1.8)   [Aspen_NETL, Romeo2008]
  We_chill  = Q_chill / COP_eff (CAP만 동적)                    [ASHRAE_HVAC]
  We_total  = We_thermal_eq + We_pump + We_comp + We_chill + We_aux

[2차 지표]
  SPECCA = (SRD × 500 + We_elec × 2,500) / capture              [Manzolini2015 변형]

[경제성]
  CRF      = i(1+i)^n / [(1+i)^n - 1]                          [NETL_QGESS]
  연환산 CAPEX = CAPEX × CRF
  COCA     = 연환산 CAPEX + OPEX

[CAP 냉동기]
  COP_Carnot = T_abs / (T_amb - T_abs)                          [ASHRAE_HVAC]
  COP_eff    = COP_Carnot × 0.55
  Q_chill    = SRD × 0.18                                        [NETL_Rev4a]
""", language="python")

    st.markdown("---")
    st.markdown("### 🎯 데이터 신뢰도 (Quality Tier)")

    tier_data = pd.DataFrame([
        {"기술": LIT["MEA_baseline"]["name"], "Tier": "A — 상용 (참고)",
         "기준": "1세대 표준, 다수 상용 플랜트", "불확실성": "± 5%"},
        {"기술": LIT["MHI_KS21"]["name"], "Tier": "A — 상용",
         "기준": "Petra Nova (1.4 Mt/yr) + 다수 일본 적용", "불확실성": "± 5%"},
        {"기술": LIT["Cansolv_DC103"]["name"], "Tier": "A — 상용",
         "기준": "Boundary Dam (1 Mt/yr 운영) + NETL 2022 baseline", "불확실성": "± 5%"},
        {"기술": LIT["Aker_S26"]["name"], "Tier": "A — 상용",
         "기준": "Norcem Brevik (시멘트, 0.4 Mt/yr 2024 가동), Twence", "불확실성": "± 8%"},
        {"기술": LIT["CAP_B12C"]["name"], "Tier": "A — Demo",
         "기준": "AEP Mountaineer demo + NETL B12C 공식 케이스", "불확실성": "± 10%"},
        {"기술": LIT["CaL"]["name"], "Tier": "B — Demo",
         "기준": "1.7 MWe La Pereda 파일럿 + IEAGHG", "불확실성": "± 15%"},
        {"기술": LIT["TSA_Solid"]["name"], "Tier": "B — Demo",
         "기준": "DOE 0.5~1 MWe 파일럿 (RTI, SRI)", "불확실성": "± 20%"},
        {"기술": LIT["K2CO3_KIERSOL"]["name"] + " †", "Tier": "C — Pilot",
         "기준": "KIER 0.5 MWe 파일럿", "불확실성": "± 25%"},
        {"기술": LIT["Biphasic_DMX"]["name"] + " †", "Tier": "C — Pilot",
         "기준": "Dunkirk 0.5 t/h 파일럿 (3D Project)", "불확실성": "± 25%"},
    ])
    st.dataframe(tier_data, use_container_width=True, hide_index=True)

    st.warning(
        "⚠️ 본 툴의 수치는 공개 보고서 기반 *representative values*. "
        "Tier C(파일럿 †) 데이터는 ±25% 이상 변동 가능. "
        "실제 프로젝트는 EPC 견적·실증 데이터로 보정 필요."
    )

# ---------- ⑧ 방법론 ----------
with tab_method:
    st.markdown("### 🔬 방법론 / 추정 근거 (Methodology)")
    st.caption("본 툴의 모든 수치·수식·가정의 근거. 자료 신뢰도 검증·peer review용.")

    # ── 1. 기준 ──
    with st.expander("📌 **1. 기준 플랜트 & Data Base**", expanded=True):
        st.markdown("""
**기준 플랜트** (Reference Case)
- **Source**: NETL Rev4a Case B12C / NETL 2022 Baseline B12B
- **Plant Type**: 555 MWe net Subcritical PC + Post-Combustion Capture
- **Coal**: Illinois No. 6 Bituminous
- **Capture rate**: 90%
- **Annual capture**: ~3.7 MtCO₂/yr (capacity factor 85%)
- **Cost basis year**: 2018~2022 USD (no inflation adjustment)
- **Location**: US Midwest (NETL standard)

**LIT 데이터 hierarchy**

| 기술 | 1차 출처 | 보조 출처 | Tier |
|---|---|---|---|
| MEA | NETL Rev4a B12B (3.6 GJ/t) | Bui 2018, Rochelle 2009 | A — 상용 (±5%) |
| K₂CO₃/KIERSOL | KIER 파일럿 보고서 | Yoo 2013, Cullinane 2004 | C — Pilot (±25%) |
| CAP | NETL Rev4a B12C | Darde 2010, Telikapalli 2011 | A — Demo (±10%) |
| Biphasic DMX | 3D Project (TotalEnergies) | Raynal 2011 | C — Pilot (±25%) |
| TSA | DOE NETL Sorbent Program | Sjostrom & Krutka 2010 | B — Demo (±20%) |
| CaL | IEAGHG 2013/19 + Hanak 2015 | Abanades 2002, Grasa 2006 | B — Demo (±15%) |

**왜 NETL B12C가 기준?**
NETL Cost & Performance Baseline은 미 정부가 30년+ 유지·검증해온 표준 reference case로,
- 모든 case의 가정·전제가 동일하게 정규화됨 → 기술 간 직접 비교 가능
- 공식 cost methodology (QGESS) 적용
- 외부 peer review 거침
- 후속 연구에서 가장 빈번히 인용
        """)

    # ── 2. KPI별 ──
    with st.expander("🎯 **2. 4대 KPI 계산 근거 (SRD · We · SPECCA · COCA)**"):
        st.markdown(r"""
**SRD (Specific Reboiler Duty)**
- **정의**: 흡수제 재생탑 reboiler가 단위 CO₂당 공급해야 하는 열에너지
- **단위**: GJ thermal / tCO₂
- **출처값**: NETL B12B (Cansolv DC-103, 3.56 GJ/t) ≈ MEA 30% 기준 3.6 (compatible)
- **물리적 분해**:
  - Heat of desorption: ~1.8 GJ/t (열역학 limit)
  - Sensible heat (rich solvent → 재생): ~0.9 GJ/t
  - Stripping vapor: ~0.9 GJ/t
  - **합계 ≈ 3.6 GJ/t** (이론 + 실제 손실)

**We (Equivalent Work)**
- **정의**: 모든 에너지 입력을 전기 등가로 환산 [GJe / tCO₂]
- **분해**:
  - `We_thermal_eq` = SRD × Carnot × 0.55  (Bejan 2016, Kotas 1985)
  - `We_pump`      : LIT 고정값 (rich solvent pumping)
  - `We_comp`      : LIT × log(p_final/p_regen) / log(152/1.8)  (Aspen/NETL)
  - `We_chill`     : Q_chill / COP_eff (CAP만 동적, ASHRAE)
  - `We_aux`       : LIT 고정값 (보조)

**SPECCA (Specific Primary Energy Consumption for CO₂ Avoided)**
- **사용자 정의식**: SPECCA = (SRD × 500 + We_elec × 2,500) / capture
- 출처: Manzolini 2015 변형 (원본은 reference plant heat rate 차이로 산출)
- 가중치 500/2500: 기존 아민툴과 호환 위해 유지 (비교 일관성 ↑)

**COCA (Cost Of CO₂ Captured)**
- **공식**: COCA = (연환산 CAPEX + OPEX) / 연 포집량
- **연환산 CAPEX** = CAPEX × CRF, where CRF = i(1+i)ⁿ / [(1+i)ⁿ−1]
- **default**: i=8%, n=25 → CRF = 0.0937
- **OPEX**: 용매·기타·전력 합산
        """)

    # ── 3. 규모 효과 ──
    with st.expander("📐 **3. 규모 효과 — CCS 특화 스케일링** ⭐ 핵심"):
        st.markdown(rf"""
**왜 CCS 특화 스케일이 필요한가**
일반 화공의 Lang's six-tenths rule (n=0.6~0.7)은 광범위한 화공 평균값입니다.
CCS는 다음 특성으로 별도의 calibration이 필요:
- 거대 absorber/stripper column 비중 ↑ (n ≈ 0.65)
- 다단 압축기 비중 ↑ (n ≈ 0.67)
- Power island 통합 효과 (n ≈ 0.7)
- Composite total: **n ≈ 0.65** (IEAGHG 2007, NETL QGESS)

**CAPEX 스케일링 (n = 0.65)**
$$\text{{CAPEX/t}}_\text{{actual}} = \text{{CAPEX/t}}_\text{{ref}} \times \left(\frac{{3.7}}{{\text{{actual}}\ \text{{[Mt/yr]}}}}\right)^{{0.35}}$$
- 출처: IEAGHG 2007 (CCS plant scaling), NETL QGESS 2019
- 0.5 Mt → +85% / 1 Mt → +48% / 3.7 Mt → 0% / 10 Mt → −29% / 20 Mt → −45%

**SRD 스케일링 (±10%/decade)**
$$\text{{SRD}}(\text{{scale}}) = \text{{SRD}}_\text{{ref}} \times \left[1 + 0.10 \times \log_{{10}}\left(\frac{{\text{{scale}}}}{{3.7}}\right)\right]$$
clip to ±15%
- 출처: **IEAGHG 2013/06 Solvent R&D Priorities**
- 메커니즘: 파일럿(idealized) → 상용 +10~15%
  - 큰 stripper → 압력 강하 ↑
  - 큰 reboiler → LMTD 손실 ↑
  - Startup/shutdown inefficiencies
  - Heat integration 한계 (real plant heat exchanger network)

**We_comp 스케일링 (±6%/decade, 반대 방향)**
$$\text{{We}}_\text{{comp}}(\text{{scale}}) = \text{{We}}_\text{{comp,ref}} \times \left[1 + 0.06 \times \log_{{10}}\left(\frac{{3.7}}{{\text{{scale}}}}\right)\right]$$
- 출처: **NETL Rev3/4** (Aspen Plus 압축기 모델), **GPSA Engineering Data Book** (효율 표준), **IEAGHG 2014/TR4**
- 메커니즘: 소형(왕복식 η~75%) → 대형(다단 원심+intercool η~85%)
- 1 Mt → +3.4% / 3.7 Mt → 0 / 10 Mt → −2.6%

**현재 운전 조건 보정 요약**: 사이드바 포집량 입력 아래에 자동 표시
        """)

    # ── 4. CCU 정제 ──
    with st.expander("🥤 **4. CCU 정제 등급별 (수율·가격·CAPEX) 추정**"):
        st.markdown(r"""
**3단계 등급 (CGA G-6.2 + SEMI C3 표준)**

| 등급 | 순도 | 수율 | 판매가 (KRW/t) | CAPEX adder | 공정 |
|---|---|---|---|---|---|
| 식품·음료급 | 99.9% | **88%** | 250k~400k (default 300k) | +5% | 활성탄 흡착 + 분자체 |
| 고순도 | 99.99% | **82%** | 350k~550k (default 450k) | +25% | + 증류 컬럼 1단 |
| 초고순도 | 99.999% | **75%** | 600k~800k (default 700k) | +65% | + 극저온 증류 |

**수율 감소 메커니즘**: 정제 순도 ↑ → off-gas vent 비율 ↑
- 99.9%: 약 12% 손실 (light gas + 미량 불순물)
- 99.99%: 추가 6% 손실 (high-boiling impurities)
- 99.999%: 추가 7% 손실 (cryogenic distillation tails)

**CAPEX adder 모델**
$$\text{{CAPEX}}_\text{{eff}} = \text{{CAPEX}}_\text{{base}} \times [1 + \text{{ccu\_share}} \times (\text{{capex\_mult}} - 1)]$$
- 출처: Linde / Air Liquide industrial gas plant sizing, CGA standards

**가격 source**: Linde Industrial Gas Korea, Air Liquide Korea, 한국가스공사 액화탄산 시장 (2020~2023)
        """)

    # ── 5. CCS 격리 수율 ──
    with st.expander("🏔️ **5. CCS 격리 수율 92% 분해 근거**"):
        st.markdown(r"""
**포집 → 격리 chain의 단계별 손실 (default 92% 누적 수율)**

| 단계 | 손실률 | 누적 수율 | 출처 |
|---|---|---|---|
| 흡수제 재생 (포집점) | base 100% | 100% | reference |
| Dehydration (TEG/molecular sieve) | -0.5% | 99.5% | IPCC SRCCS Ch5 |
| 다단 압축 (5~7단) | -1.0% | 98.5% | NETL Aspen, GPSA |
| 파이프라인 수송 (50~200km) | -1.5% | 97.0% | IPCC SRCCS Ch5 |
| Wellhead 주입 (시동 vent) | -1.0% | 96.0% | Global CCS Inst. 2023 |
| Long-term leakage rate | -4% (보수적) | **92.0%** | IPCC AR6 WG3 |

**default 92% 선정 근거**: NETL/Global CCS Institute 운영 데이터 평균 (Boundary Dam, Quest, Petra Nova 등)

**조정 가능 범위**: 80~99% (사용자 입력)
- 80%: pilot scale 또는 노후 인프라
- 92%: 표준 commercial (default)
- 98%: 최신 dedicated injection (saline aquifer)

출처: **IPCC SRCCS Ch5**, **IPCC AR6 WG3**, **Global CCS Institute Status 2023**
        """)

    # ── 6. 경제성 가정 ──
    with st.expander("💰 **6. 경제성 가정 (CRF, 할인율, 전기·배출권 가격)**"):
        st.markdown(rf"""
**CRF (Capital Recovery Factor)**
$$\text{{CRF}} = \frac{{i(1+i)^n}}{{(1+i)^n - 1}}$$
- default i = 8%, n = 25 → CRF = 0.0937 (9.37%/yr)
- 출처: **NETL QGESS 2019** Standard

**전기 가격 (default $80/MWh)**
- US 산업 평균: 75~95 USD/MWh (EIA AEO 2024)
- 한국 산업: ≈ 110~130 USD/MWh (한전 산업용)
- EU: ≈ 100~150 USD/MWh
- 출처: **EIA AEO 2024**, **IEA Energy Prices 2023**

**탄소시장 가격 (모든 default, 2024 평균)**

| 시장 | Default ($USD/t) | 환산 | 변동성 | 출처 |
|---|---|---|---|---|
| K-ETS | 7 | 10,000 KRW/t | 高 (5~15) | KRX 2024 |
| EU ETS | 80 | €75 | 中 (60~100) | ICE 2024 |
| RGGI (US east) | 20 | — | 低 | RGGI Inc. 2024 |
| CA Cap-Trade | 30 | — | 低 | CARB 2024 |

**보조금 (정부 인센티브)**

| 제도 | Default | 조건 | 출처 |
|---|---|---|---|
| US 45Q-CCS | $85/t | 12yr, 75%+ capture | IRS Notice 2022-38 (IRA) |
| US 45Q-EOR | $60/t | 12yr | IRS Notice 2022-38 |
| US 45Q-DAC | $180/t | 12yr | IRS Notice 2022-38 |
| NL SDE++ | $120/t (€110) | CfD 12~15yr | RVO Netherlands 2024 |
| UK CCUS CfD | $180/t (£150) | Track 1/2 cluster | UK BEIS 2023 |
| K-CCUS Act | $21/t (placeholder) | 시행령 미정 | 산업부 2024 |

**환율**: default 1,400 KRW/USD (2026.4 기준, 사용자 조정 가능)
        """)

    # ── 7. CAP 냉동기 ──
    with st.expander("🧊 **7. CAP 냉동기 (Carnot COP × 0.55) 모델**"):
        st.markdown(r"""
**왜 CAP만 냉동기 모델이 동적인가**
다른 기술은 흡수탑이 상온 운전 (40~70°C)이라 외기/냉각수로 충분.
**CAP은 0~10°C 흡수**로 냉동 사이클 (NH₃ slip 방지) 필수.

**모델**
1. 냉각 부하 추정: $Q_\text{chill} = \text{SRD} \times 0.18$
   - 출처: **NETL Rev4a B12C 보조전력 분석** (실제 측정값에서 SRD 대비 0.16~0.20 fraction)
   - 휴리스틱이지만 NETL 공식 케이스에 직접 부합

2. 역카르노 COP 계산:
   $$\text{COP}_\text{Carnot} = \frac{T_\text{abs}}{T_\text{amb} - T_\text{abs}}$$
   - 응축기 ΔT 마진 +10°C 가정 (실 운영 표준)

3. 실효 COP = COP_Carnot × 0.55 (second-law factor)
   - 출처: **ASHRAE Handbook (2020)**, real chiller efficiency 0.5~0.6 of Carnot

4. We_chill = Q_chill / COP_eff

**검증**: 냉각수 25°C일 때 We_chill ≈ 0.18 GJe/tCO₂ → NETL B12C 보조전력 분해와 일치
        """)

    # ── 8. 압축 ──
    with st.expander("⚙️ **8. CO₂ 압축 일 — Log-pressure 모델**"):
        st.markdown(r"""
**모델**
$$\text{We}_\text{comp}(\text{p}) = \text{We}_\text{comp,LIT} \times \frac{\log(p_\text{final}/p_\text{regen})}{\log(152/1.8)}$$
floor 0.3 (부분 압축 시에도 최소 손실)

**근거**:
- 5단 압축 + 4단 intercooling 가정 (NETL Aspen 표준)
- 단단 등엔트로픽 일: $W = \frac{\gamma}{\gamma-1} R T_\text{in} [(p_\text{out}/p_\text{in})^{(\gamma-1)/\gamma} - 1]$
- 다단 + intercooling 시 ≈ $n \cdot \log(p_\text{out}/p_\text{in})$ 비례 (이론)
- 압축기 효율: 소형(왕복) 75% / 대형(원심) 85% (GPSA Section 13)

**최종 압력별 사용 시나리오**:

| 압력 | 용도 | We_comp 배율 |
|---|---|---|
| 5 bar | 액화탄산 (식품) | × 0.3 (floor) |
| 25 bar | 액화탄산 (산업) | × 0.59 |
| 100 bar | 파이프라인 | × 0.91 |
| 152 bar | EOR (NETL 표준) | × 1.00 |
| 200 bar | 지중저장 (deep saline) | × 1.06 |

출처: **NETL Aspen Plus 압축 모델**, **Romeo et al. 2008**, **GPSA 2017**
        """)

    # ── 9. 손실 ──
    with st.expander("📉 **9. 흡수제·흡착제 손실 추정**"):
        st.markdown("""
| 기술 | 손실 (kg/tCO₂) | 메커니즘 | 출처 |
|---|---|---|---|
| MEA 30% | 1.5 | 산화·열분해, evaporation | Lepaumier 2009, IEAGHG 2014 Reclaimer Sludge |
| K₂CO₃/KIERSOL | 0.5 | 활성화제 (PZ) 열화 미량 | KIER reports, Cullinane 2004 |
| CAP (NH₃) | 0.3 | NH₃ slip (water wash 회수 후 미회수분) | Darde 2010, Telikapalli 2011 |
| Biphasic DMX | 1.0 | 용매 분해, 휘발 (mid-range vs MEA) | Raynal 2011 |
| TSA solid | 2.0 | Cycle attrition (마모) + thermal degradation | DOE NETL Sorbent Program, Sjostrom & Krutka 2010 |
| CaL | 30 | CaO sintering → makeup limestone (저비용 다소비) | Grasa 2006, Hanak 2015 |

**주의**: TSA의 2 kg/t는 cycle 수에 따라 환산값. 실제 sorbent attrition은 0.5~5%/cycle 범위 (DOE NETL R&D).
**CaL의 30 kg/t**는 다른 기술과 비교 시 단순 정량 비교 부적절 — 재료 비용도 별도 고려.
        """)

    # ── 10. Walk-through ──
    with st.expander("✅ **10. 검증 — MEA 단일 케이스 계산 walk-through**"):
        st.markdown(r"""
**조건**: MEA 30 wt%, 1 MtCO₂/yr, 25°C 냉각수, 152 bar 출력, CCS 모드, 92% yield, 45Q-CCS

**Step 1**: 규모 보정
- log_ratio = log10(1.0 / 3.7) = −0.568
- SRD: 3.60 × (1 + 0.10 × (−0.568)) = 3.60 × 0.943 = **3.40 GJ/t**
- We_comp: 0.40 × (1 + 0.06 × 0.568) = 0.40 × 1.034 = **0.414 GJe/t**

**Step 2**: We 분해
- η_Carnot = (120 − 25) / (120 + 273.15) = 0.242
- η_eff = 0.242 × 0.55 = 0.133
- We_thermal_eq = 3.40 × 0.133 = **0.452 GJe/t**
- p_factor = log(152/1.8) / log(152/1.8) = 1.0
- We_comp_eff = 0.414 × 1.0 = 0.414
- We_chill = 0 (MEA)
- We_pump = 0.012, We_aux = 0.05
- **We_elec = 0.012 + 0.414 + 0 + 0.05 = 0.476 GJe/t**
- **We_total = 0.452 + 0.476 = 0.928 GJe/t**

**Step 3**: SPECCA
- (3.40 × 500 + 0.476 × 2,500) / 0.90 = (1,700 + 1,190) / 0.90 = **3,211 MJ/t**

**Step 4**: COCA
- CAPEX/t scaled: 950 × (3.7/1)^0.35 = 950 × 1.55 = **1,470 USD/(t/yr)**
- 연환산 CAPEX = 1,470 × 0.0937 = **137.7 USD/t**
- 전력비 = 0.476 × 277.78/1000 × 80 = **10.6 USD/t**
- OPEX_solvent = 1.5, OPEX_other = 12.0
- **COCA = 137.7 + 1.5 + 12.0 + 10.6 = 161.8 USD/t**

**Step 5**: 매출/Net COCA (45Q-CCS $85/t)
- stored_t = 1.0 × 1.0 × 0.92 = 0.92 Mt
- subsidy = 0.92e6 × 85 = $78.2M/yr
- rev/capture = $78.2M / 1.0Mt = $78.2/t
- **Net COCA = 161.8 − 78.2 = $83.6/t**

**Step 6**: 연간 손익
- 연 비용 = 161.8 × 1.0e6 = $161.8M/yr
- 연 매출 = $78.2M/yr (보조금만)
- **연 손익 = +$78.2M − $161.8M = −$83.6M/yr** (적자, 약 −1,170억원/yr)

→ MEA를 1 Mt 작은 플랜트로 짓고 45Q-CCS만 받으면 적자. 더 큰 플랜트(scale ↑) 또는 더 강한 인센티브 필요.
        """)

    # ── 11. LCA / Net CO₂ ──
    with st.expander("🌱 **11. LCA / Net CO₂ — Lifecycle Scope 1+2+3**"):
        st.markdown(r"""
**왜 LCA가 중요한가**
포집된 CO₂ 1톤 ≠ 실제 줄어든 CO₂ 1톤. 다음 lifecycle 배출 차감 후 진짜 net 효과 계산:
- Scope 1: 시설 직접 배출 (현 모델 미고려, 보통 zero)
- Scope 2: 운영 에너지 (열·전력 grid 의존 emissions)
- Scope 3: 흡수제 makeup 생산, embodied CAPEX (제조), 폐기

**계산식**
```
e_heat     = SRD × heat_factor / 1000               [tCO₂/tCO₂]
e_elec     = We_elec × 277.78 × grid_factor / 1e6
e_solvent  = loss_kg × solvent_factor / 1000
e_embodied = CAPEX × 0.20 / lifetime / 1000

Net Removed [%] = (Gross stored/sold - Σ e_i) × 100
```

**Default 값 출처**:
- 열 배출계수: NETL/IEAGHG 표준 (가스 55, 석탄 100, 폐열 5 kgCO₂/GJ)
- Grid 배출계수: IEA Electricity Maps 2024 (US 380, 한국 470, EU 230 gCO₂/kWh)
- 흡수제 배출계수: Singh 2011, Pour 2018, Strazza 2020 (MEA 1.4, MOF 3.5 등)
- Embodied CAPEX: NETL 2021 LCA (0.20 kgCO₂/$ industrial CAPEX)

**왜 voluntary 시장에서 net removed가 중요한가**:
- EU CRCF (2024): net removed 기준 의무화
- ICVCM Core Carbon Principles: high-integrity credit 평가 시 LCA 필수
- Stripe Frontier·Microsoft 등 대형 buyer: net 효율 70% 이하면 deal 거절 사례 多

**시장별 적용**:
| 시장 | 기준 | 비고 |
|---|---|---|
| 컴플라이언스 (45Q, ETS, K-ETS, SDE++, CfD) | Gross | 본 모델 OK |
| Voluntary (Verra, ICVCM) | **Net removed** | LCA 필수 |
| EU CRCF (2024~) | **Net removed** | 의무 |
| LCFS (CA) | Pathway 기반 lifecycle | 별도 계산 |
""")

    # ── 12. 한국 K-ETS CCU 차감 ──
    with st.expander("🇰🇷 **12. 한국 K-ETS CCU 차감 제도** (직접 매출 아님 — 조건부 가치)"):
        st.markdown("""
**제도 근거**
- 「온실가스 배출권의 할당 및 거래에 관한 법률」 Art. 14 (배출량 산정·보고)
- 환경부 고시 「배출량 보고·검증 지침」 (Phase 4, 2024~)

**제도 본질** ⚠️
K-ETS CCU 차감은 **"배출량 보고 시 출하량만큼 차감"**일 뿐, 직접 현금 매출이 아닙니다.
실제 경제 가치는 회사의 배출권 수급 상황에 따라 결정:

| 상황 | 차감 효과 | 실효 경제 가치 |
|---|---|---|
| 🟢 **할당 부족 (short)** | 부족분 감소 | **= 출하량 × K-ETS 가격** (배출권 매입 회피) |
| 🟡 **할당 균형 (balance)** | 잉여 발생 | **시장 매도 가능분만큼** (유동성 의존) |
| 🔴 **할당 잉여 (long)** | 잉여 더 증가 | **즉시 가치 ≈ 0** (차기 이월 가능) |

**적용 조건 (차감 인정)**
- 할당대상업체 (Phase 4: ~700개사)
- CO₂ 포집 후 외부 판매 (CCU)
- buyer 측에서 배출 책임 (또는 영구 incorporation, 예: 시멘트 mineralization)
- MRV (Measurement, Reporting, Verification) 체계 충족

**본 모델 처리 방식**:
- **매출 계산에 미포함** — calc_revenue의 market_revenue는 CCS 격리량만
- **탭 ⑨에서 별도 표시** — 보고 차감 톤수 + 조건부 가치 시나리오
- **사이드바 toggle**: K-ETS CCU 차감 보고 ON 시 정보용 가격 입력

**예시** (K-ETS $7/t, CCU 0.3 Mt/yr 출하):
- Gross 출하량 = 264 kt (yield 88%)
- Net 감축량 (LCA 반영) ≈ 200 kt
- 조건부 가치 (시나리오 1, short인 경우) = 264k × $7 = **$1.85M/yr (≈ 26억원)**
- 위는 **실제 매출에 더하지 않고**, 의사결정 시 별도 검토 사항

**미인정 사례 (case-by-case)**:
- Beverage/식품용 단기 재배출 CCU → 일부 미인정
- 산업용 중간 판매·보관 시 buyer 명확치 않으면 차감 인정 어려움
- 화학 합성·중간재로 단기 사용 → MRV 검증 필요
        """)

    # ── 13. 한계 ──
    with st.expander("⚠️ **13. 모델의 한계 & 미반영 항목**"):
        st.markdown("""
**모델이 다루지 않는 것**

| 항목 | 영향 | 보완 방법 |
|---|---|---|
| Variable load operation | ±5~10% efficiency | 현장 dispatch 모델 필요 |
| Power island integration (steam extraction) | ±5% net efficiency | NETL Aspen full plant model |
| Site-specific costs (지반, 인프라) | ±20% CAPEX | EPC 견적 |
| Inflation / 환율 변동 | 시간 의존 | 매년 업데이트 |
| Permitting & regulation costs | ±5~15% CAPEX | 지역별 별도 |
| Carbon storage long-term liability | 미정량화 | 보험 + monitoring |
| CCU 시장 saturation effects | 가격 ↓ at scale | 시장 모델 |
| Solvent reclaiming costs (MEA only) | OPEX +1~3% | reclaimer 운영비 |
| Heat integration with host plant | ±10% SRD | site-specific |

**불확실성 등급 (재정리)**

| Tier | 기준 | 권장 사용 |
|---|---|---|
| **A (±5~10%)** | 다수 상용 운영 데이터 | EPC 견적 input, board materials |
| **B (±15~20%)** | Demo / 1+ MWe pilot | Concept screening, R&D priority |
| **C (±25%+)** | Pilot < 1 MWe | Trend analysis only, 단독 결정 不可 |

**📌 핵심 권고**:
- Tier A 데이터로 1차 screening
- Tier C 결과는 반드시 ±25% sensitivity 검토
- 최종 투자 결정 시 site-specific EPC 견적 필수
        """)

    st.markdown("---")
    st.info(
        "📖 **References**: 모든 출처는 탭 ⑦ 참고문헌 (총 36개) 참조. "
        "본 방법론 섹션은 자료 신뢰도 검증 (peer review) 및 sensitivity 분석 input 작성용."
    )

# ---------- ③ Lifecycle / Net CO₂ ----------
with tab_lca:
    st.markdown("### 🌱 Lifecycle / Net CO₂ Removed")
    st.caption(
        "포집된 1톤 중 lifecycle 배출 (열·전기·흡수제·embodied) 차감 후 "
        "**실제 줄어든 net CO₂**. EU CRCF (2024), ICVCM Core Carbon Principles, "
        "voluntary buyer (Stripe Frontier, Microsoft 등) 평가 기준."
    )

    # 현재 LCA 가정 표시
    _heat_lab = HEAT_SOURCES[heat_source_key]['label']
    _grid_lab = GRID_FACTORS[grid_key]['label']
    _heat_str = f"grid 의존 (heat pump)" if heat_factor < 0 else f"{heat_factor:.0f} kgCO₂/GJ"
    st.markdown(
        f"<div style='background:#1E2128; border-left:3px solid #81C784; "
        f"padding:8px 12px; border-radius:4px; margin-bottom:10px;'>"
        f"<b>📋 현재 LCA 가정</b><br>"
        f"<span style='font-size:0.85rem;'>"
        f"열원: <b>{_heat_lab}</b> ({_heat_str}) · "
        f"전력 grid: <b>{_grid_lab}</b> ({grid_factor:.0f} gCO₂/kWh) · "
        f"Embodied CAPEX: {'포함' if include_embodied else '제외'}"
        f"</span></div>",
        unsafe_allow_html=True,
    )

    # ── 1. Net CO₂ 효율 막대 차트 (per ton) ──
    short_x = [SHORT_NAMES.get(r["key"], r["name"]) for r in results]

    f_lca = go.Figure()
    f_lca.add_trace(go.Bar(
        name="Gross 격리/출하", x=short_x,
        y=[r["gross_per_t"] for r in results],
        marker_color="#4FC3F7",
        text=[f"{r['gross_per_t']*100:.0f}%" for r in results],
        textposition="inside",
    ))
    f_lca.add_trace(go.Bar(
        name="− 열 emissions", x=short_x,
        y=[-r["lca_e_heat"] for r in results],
        marker_color="#FF8A65",
    ))
    f_lca.add_trace(go.Bar(
        name="− 전력 emissions", x=short_x,
        y=[-r["lca_e_elec"] for r in results],
        marker_color="#FFB74D",
    ))
    f_lca.add_trace(go.Bar(
        name="− 흡수제 makeup", x=short_x,
        y=[-r["lca_e_solvent"] for r in results],
        marker_color="#BA68C8",
    ))
    if include_embodied:
        f_lca.add_trace(go.Bar(
            name="− Embodied CAPEX", x=short_x,
            y=[-r["lca_e_embodied"] for r in results],
            marker_color="#A1887F",
        ))
    # Net Removed marker
    f_lca.add_trace(go.Scatter(
        name="◆ Net Removed",
        x=short_x,
        y=[r["net_removed_per_t"] for r in results],
        mode="markers+text",
        marker=dict(size=24, color="#FFEB3B", symbol="diamond",
                    line=dict(color="#212121", width=3)),
        text=[f"<b>{r['crcf_efficiency_pct']:.0f}%</b>" for r in results],
        textposition="top center",
        textfont=dict(size=14, color="#FFEB3B"),
    ))
    f_lca.add_hline(y=0, line_color="white", line_width=1, line_dash="dot")
    f_lca.update_layout(
        title="단위 톤당 Net CO₂ — 1톤 captured 중 실제 격리/감축된 비율",
        template="plotly_dark", height=480, barmode="relative",
        margin=dict(l=10, r=10, t=60, b=80),
        legend=dict(orientation="h", y=-0.18),
        yaxis_title="tCO₂ / tCO₂ captured",
    )
    st.plotly_chart(f_lca, use_container_width=True, config=PLOTLY_CONFIG)

    # ── 2. CRCF Efficiency Tier 분류 ──
    st.markdown("##### 📊 CRCF / ICVCM 등급")
    st.caption(
        "voluntary credit market 등급: A (>80%) · B (60-80%) · C (40-60%) · D (<40%)"
    )

    def crcf_tier(pct):
        if pct >= 80: return "🟢 A — High Integrity"
        if pct >= 60: return "🟡 B — Acceptable"
        if pct >= 40: return "🟠 C — Marginal"
        return "🔴 D — Below threshold"

    tier_rows = []
    for r in results:
        pct = r["crcf_efficiency_pct"]
        tier_rows.append({
            "기술": r["name"],
            "Gross [%]":          f"{r['gross_per_t']*100:.1f}",
            "− 열":               f"{r['lca_e_heat']*100:.2f}",
            "− 전력":             f"{r['lca_e_elec']*100:.2f}",
            "− 흡수제":           f"{r['lca_e_solvent']*100:.3f}",
            "− Embodied":         f"{r['lca_e_embodied']*100:.3f}" if include_embodied else "—",
            "Net Removed [%]":    f"{pct:.1f}",
            "연 Net 감축 [kt/yr]": f"{r['net_removed_t_yr']/1000:,.1f}",
            "CRCF 등급":          crcf_tier(pct),
        })
    st.dataframe(pd.DataFrame(tier_rows), use_container_width=True, hide_index=True)

    # ── 3. 시나리오 비교 인사이트 ──
    avg_net = sum(r["crcf_efficiency_pct"] for r in results) / len(results)
    best_net_r = max(results, key=lambda r: r["crcf_efficiency_pct"])
    worst_net_r = min(results, key=lambda r: r["crcf_efficiency_pct"])

    st.markdown(f"""
##### 💡 분석 인사이트

- **평균 Net 효율**: {avg_net:.1f}% (1톤 잡으면 평균 {avg_net/100:.2f}톤 실제 감축)
- **최고 효율**: {best_net_r['name']} ({best_net_r['crcf_efficiency_pct']:.1f}%) — voluntary credit 발행에 가장 적합
- **최저 효율**: {worst_net_r['name']} ({worst_net_r['crcf_efficiency_pct']:.1f}%) — 열원/grid 변경 검토 필요
- **현재 가정에서 dominant emission**: {('열' if results[0]['lca_e_heat'] >= max(results[0]['lca_e_elec'], results[0]['lca_e_solvent']) else '전력' if results[0]['lca_e_elec'] >= results[0]['lca_e_solvent'] else '흡수제')} ({max(results[0]['lca_e_heat'], results[0]['lca_e_elec'], results[0]['lca_e_solvent'])*100:.1f}% of captured)
""")

    # ── NEW: 🇰🇷 한국 K-ETS CCU 차감 분석 (CCU 모드 + toggle ON 시만 표시) ──
    if facility_mode == "CCU" and apply_kets_ccu:
        st.markdown("---")
        st.markdown("### 🇰🇷 한국 K-ETS CCU 차감 효과 (할당대상업체 보고용)")
        st.warning(
            "⚠️ **K-ETS 차감 기준 = Gross 출하량** (물리적 MRV 측정량). "
            "Net (LCA 반영)이 아닙니다. 환경부는 lifecycle 배출은 차감 산정에서 묻지 않음. "
            "Net 감축량은 환경 효과 참고용 (실제 정책 차감 기준 아님)."
        )

        # ── PRIMARY: Gross 기준 (실제 K-ETS 차감) ──
        st.markdown("##### 🎯 K-ETS 보고 차감 (Gross 출하량 기준)")
        kets_primary_rows = []
        for r in results:
            sold = r['sold_lco2_t']  # gross 출하량 = 실제 차감 톤수
            implicit_usd = sold * kets_ccu_price_info
            kets_primary_rows.append({
                "기술": r['name'],
                "Gross 출하량 [kt/yr]":     f"{sold/1000:,.1f}",
                "K-ETS 차감 보고량 [kt/yr]": f"{sold/1000:,.1f}",  # 동일 (gross = 차감 기준)
                f"조건부 가치 (× ${kets_ccu_price_info:.1f}/t)":
                                              fmt_money(implicit_usd, fx_krw_per_usd, display_currency),
            })
        st.dataframe(pd.DataFrame(kets_primary_rows), use_container_width=True, hide_index=True)
        st.caption(
            "→ K-ETS 차감 톤수 = **MRV로 측정한 실제 출하 CO₂ 톤수** "
            "(환경부 배출량 보고·검증 지침)"
        )

        # ── SECONDARY: Net (LCA) — 환경 효과 참고용 ──
        st.markdown("##### 🌱 환경 효과 참고 — LCA 반영 Net 감축 (정책 차감 기준 아님)")
        kets_secondary_rows = []
        for r in results:
            sold = r['sold_lco2_t']
            net_t = r['net_removed_t_yr']
            net_pct = (net_t / sold * 100) if sold > 0 else 0
            kets_secondary_rows.append({
                "기술": r['name'],
                "Gross 출하 [kt/yr]":      f"{sold/1000:,.1f}",
                "Net 감축 (LCA) [kt/yr]":  f"{net_t/1000:,.1f}",
                "실제 환경 효율 [%]":       f"{net_pct:.1f}",
            })
        st.dataframe(pd.DataFrame(kets_secondary_rows), use_container_width=True, hide_index=True)
        st.caption(
            "ℹ️ Net 감축량은 voluntary credit·EU CRCF 등 **lifecycle 평가 시장**에서 의미. "
            "K-ETS 차감과는 별개."
        )

        # 조건부 시나리오 안내
        st.info(f"""
**💡 K-ETS CCU 차감의 실제 경제 가치 — 회사 상황별 시나리오**

🟢 **시나리오 1: 할당량 < 실제 배출량** (할당 부족, short)
→ CCU 차감으로 부족분 감소 → 배출권 매입 회피
→ **실효 가치 ≈ Gross 출하량 × K-ETS 가격** (위 표의 '조건부 가치'와 일치)

🟡 **시나리오 2: 할당량 ≈ 실제 배출량** (균형, balance)
→ CCU 차감으로 잉여 발생 → 배출권 시장에 매도 가능
→ **실효 가치 = 잉여 매도 가능분만큼만** (시장 유동성 의존, 보통 90% 이상 회수)

🔴 **시나리오 3: 할당량 > 실제 배출량** (잉여, long)
→ CCU 차감으로 잉여 더 증가 → 차기 의무이월 가능 but 즉시 현금화 어려움
→ **즉시 가치 ≈ 0**, 장기 가치 = 차기 가격 × 차감량 (불확실)

⚠️ **본 모델의 매출 계산에는 K-ETS 차감 가치 미포함** (조건부이므로).
의사결정 시 자체 판단 필요.

📚 **출처**: 「온실가스 배출권의 할당 및 거래에 관한 법률」 Art.14 + 환경부 고시 「배출량 보고·검증 지침」
""")

    # ── 4. 시장별 매출 기준 (gross vs net) ──
    st.markdown("---")
    st.markdown("##### 📋 시장별 매출 기준 (gross vs net)")
    st.markdown("""
| 시장/제도 | 기준 | 본 모델 | 출처 |
|---|---|---|---|
| 🇺🇸 **45Q (CCS/EOR/DAC)** | 격리·이용량 (**gross**) | ✅ 정확 | IRS Section 45Q (IRA 2022) |
| 🇪🇺 **EU ETS** | 격리량 (**gross**) | ✅ 정확 | EU Directive Art. 49 |
| 🇰🇷 **K-ETS (CCS)** | 격리량 (**gross**) | ✅ 정확 | 「온실가스 배출권법」 Art.14 |
| 🇰🇷 **K-ETS CCU 차감** | 출하량 (**gross**) | ✅ **사이드바 toggle 추가됨** | 환경부 고시 |
| 🇳🇱 NL SDE++ / 🇬🇧 UK CfD | 격리량 (gross) | ✅ 정확 | RVO/BEIS CfD strike |
| 🇺🇸 **CA LCFS** | Pathway 기반 (full lifecycle) | ⚠️ 사용자가 net 입력 권장 | CA-GREET 모델 |
| 🟢 **Voluntary credits (Stripe Frontier 등)** | **Net removed** | ⚠️ Gross로 과대 추정 | ICVCM CCP |
| 🟢 **EU CRCF (2024)** | **Net removed** | ⚠️ 동일 | EU CRCF Reg. Art.4 |
""")
    st.warning(
        "**컴플라이언스 시장 (45Q, K-ETS, EU ETS, NL SDE++, UK CfD)** 는 모두 gross 기준 → 본 모델 매출 계산 OK.\n\n"
        "**Voluntary 시장 / EU CRCF (2024)** 는 net removed 기준. 예: gross 1 Mt 신청해도 net 70%면 "
        "**700 ktCO₂ × 단가만 인정**. 사이드바 '추가 매출 [$/t]'에 입력 시 net 기준 단가로 직접 입력 권장."
    )

    # ── 5. 출처 표시 ──
    with st.expander("📚 LCA 계산 근거 (출처)"):
        st.markdown("""
**열원 배출계수 (kgCO₂/GJ)**:
- 천연가스 보일러 55, 석탄 100, 폐열 5, 재생E 8 — IPCC AR6 WG3 Annex II

**Grid 배출계수 (gCO₂/kWh, 2024)**:
- US 380, 한국 470, EU 230, 노르웨이 30 — IEA Electricity Maps 2024

**흡수제 배출계수 (kgCO₂/kg solvent)**:
- MEA 1.4 (Singh et al. 2011, Energy Procedia)
- Hindered amine 2.2 (Pour et al. 2018, Applied Energy)
- NH₃ 2.2 (ecoinvent 3.x DB)
- MOF/zeolite 3.5 (Strazza et al. 2020)

**Embodied CAPEX**: 0.20 kgCO₂/$ industrial CAPEX (NETL 2021 LCA)

**기준 framework**:
- EU Carbon Removal Certification Framework (CRCF) Regulation 2024
- ICVCM Core Carbon Principles (2023)
- ISO 14064 / 14067
- IEAGHG 2010-09 LCA Guidelines for CCS
""")


# ======================================================================
# 푸터 — 작성자 정보 풀 버전 (스크롤 다운 시 강한 인상)
# ======================================================================
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align:center; padding:20px 0;
                background:linear-gradient(135deg, #1E2128 0%, #2A2F3A 100%);
                border-radius:8px; margin-top:20px;'>
        <div style='font-size:1.0rem; color:#E8EAED; font-weight:700; margin-bottom:6px;'>
            🌫️ CO₂ 포집·CCUS 기술·경제성 벤치마크 v1.3
        </div>
        <div style='font-size:0.78rem; color:#8b95a7; margin-bottom:14px;'>
            Advanced Amine (KS-21 · DC-103 · Aker S26) + 🇰🇷 KIERSOL (KIER) +
            비아민계 (CAP · DMX · TSA · CaL) · 9종 통합 비교 ·
            LCA/Net CO₂ (CRCF·ICVCM) · 71개 출처 audit trail
        </div>
        <div style='font-size:0.85rem; color:#B0BEC5; margin-bottom:4px;'>
            👤 Built by
            <b style='color:#4FC3F7; font-size:1.0rem;'>송봉관 / Song BK</b>
        </div>
        <div style='font-size:0.78rem; color:#8b95a7; margin-bottom:10px;'>
            DAC & CCUS 기술사업화 전문가
        </div>
        <div style='font-size:0.85rem; margin-bottom:10px;'>
            🐙 <a href='https://github.com/cafeon90-oss' target='_blank'
                  style='color:#81C784; text-decoration:none; font-weight:600;'>GitHub</a>
            &nbsp;·&nbsp;
            💼 <a href='https://www.linkedin.com/in/bongkwan-song-95a0213ba/' target='_blank'
                  style='color:#81C784; text-decoration:none; font-weight:600;'>LinkedIn</a>
            &nbsp;·&nbsp;
            📝 <a href='https://cdrmaster.tistory.com/' target='_blank'
                  style='color:#81C784; text-decoration:none; font-weight:600;'>Blog</a>
            &nbsp;·&nbsp;
            📧 <a href='mailto:cafeon90@gmail.com'
                  style='color:#81C784; text-decoration:none; font-weight:600;'>cafeon90@gmail.com</a>
        </div>
        <div style='font-size:0.82rem; margin: 8px 0; padding: 6px 12px;
                    background:rgba(255,183,77,0.1); border-left:2px solid #FFB74D;
                    border-radius:4px; display:inline-block;'>
            🔗 자매 도구:
            <a href='{CBAM_TOOL_URL}' target='_blank'
               style='color:#FFB74D; text-decoration:none; font-weight:700;'>
                🛡️ EU CBAM 계산기
            </a>
            <span style='color:#8b95a7; font-size:0.75rem;'>
                — 한국 산업 영향 분석
            </span>
        </div>
        <div style='font-size:0.7rem; color:#6e7888; margin-top:10px;
                    border-top:1px solid #3a3f4a; padding-top:8px;'>
            © 2026 Song BK · MIT License · 자유롭게 사용/배포 가능 (저작자 표기 필수)<br>
            Data: NETL Rev4a/2022 · IEAGHG · IRS 45Q · KIER · MHI · Shell Cansolv · Aker CC · KRX
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
