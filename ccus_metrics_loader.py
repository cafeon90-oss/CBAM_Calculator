"""
ccus_metrics_loader.py
======================

자매 도구 (CBAM 계산기)에서 사용할 fetch 함수.
CCUS Benchmark의 GitHub raw URL에서 ccus_metrics.json을 읽어와
CBAM 도구에서 동일한 9개 기술 데이터를 사용할 수 있게 함.

Single Source of Truth 패턴:
  - CCUS Benchmark repo: data/ccus_metrics.json (master)
  - CBAM Calculator repo: 이 loader가 fetch
  - 한 곳만 수정 → 양쪽 자동 반영 (24h 캐시 만료 후)

사용법 (CBAM 도구의 app.py 상단에):

    from ccus_metrics_loader import load_ccus_metrics
    CCUS_METRICS = load_ccus_metrics()
    # CCUS_METRICS["technologies"]["MEA_baseline"]["economics"]["CAPEX_USD_per_tCO2_yr"]
"""

import json
import streamlit as st
from typing import Dict, Any
import urllib.request


# ======================================================================
# Single Source of Truth — CCUS Benchmark repo의 raw JSON URL
# ======================================================================
CCUS_METRICS_URL = (
    "https://raw.githubusercontent.com/cafeon90-oss/"
    "ccus_benchmark/main/data/ccus_metrics.json"
)

# Fallback 데이터 (네트워크 실패 시) — 최소 stub
_FALLBACK_METRICS: Dict[str, Any] = {
    "schema_version": "1.0-fallback",
    "last_updated": "2026-04-30",
    "metadata": {"reference_capture_mt_yr": 3.7},
    "technologies": {
        "MEA_baseline": {
            "name": "MEA 30 wt% (참고)",
            "short_name": "MEA",
            "category": "Amine (ref)",
            "TRL": 9,
            "performance": {"SRD_GJ_per_tCO2": 3.60, "capture_rate_default": 0.90},
            "economics": {
                "CAPEX_USD_per_tCO2_yr": 950,
                "OPEX_solvent_USD_per_tCO2": 1.5,
                "OPEX_other_USD_per_tCO2": 12.0,
            },
            "operations": {"capacity_range_mt_yr": [0.1, 10.0]},
        },
    },
    "_fallback_warning": "GitHub raw fetch 실패 — 최소 fallback 데이터 사용중",
}


@st.cache_data(ttl=86400)  # 24시간 캐시 (하루 1번 fetch)
def load_ccus_metrics(url: str = CCUS_METRICS_URL,
                       use_fallback_on_error: bool = True) -> Dict[str, Any]:
    """
    자매 도구의 ccus_metrics.json을 fetch.

    Returns:
        dict — schema_version, metadata, technologies, references_used 포함
    """
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data
    except Exception as e:
        if use_fallback_on_error:
            st.warning(
                f"⚠️ CCUS metrics JSON fetch 실패: {e}. "
                f"Fallback stub 데이터 사용. "
                f"네트워크 또는 GitHub raw URL 확인 필요."
            )
            return _FALLBACK_METRICS
        raise


def get_tech_data(metrics: Dict[str, Any], tech_key: str) -> Dict[str, Any]:
    """
    특정 기술의 데이터 추출 (안전한 .get 방식).

    Args:
        metrics: load_ccus_metrics() 결과
        tech_key: 'MEA_baseline', 'MHI_KS21' 등

    Returns:
        해당 기술의 dict (없으면 빈 dict)
    """
    return metrics.get("technologies", {}).get(tech_key, {})


def get_tech_coca(metrics: Dict[str, Any], tech_key: str,
                   discount: float = 0.08, lifetime: int = 25,
                   elec_price: float = 80.0) -> float:
    """
    특정 기술의 COCA [USD/tCO₂] 계산.
    CBAM 도구에서 빠른 비교용.

    Args:
        metrics: load_ccus_metrics() 결과
        tech_key: 기술 키
        discount, lifetime, elec_price: 경제성 가정

    Returns:
        COCA [USD/tCO₂]
    """
    tech = get_tech_data(metrics, tech_key)
    if not tech:
        return 0.0

    econ = tech.get("economics", {})
    energy = tech.get("energy_components_GJe_per_tCO2", {})

    capex_per_t = econ.get("CAPEX_USD_per_tCO2_yr", 0)
    opex_solvent = econ.get("OPEX_solvent_USD_per_tCO2", 0)
    opex_other = econ.get("OPEX_other_USD_per_tCO2", 0)

    we_elec = (energy.get("We_pump", 0) + energy.get("We_comp", 0)
                + energy.get("We_chill", 0) + energy.get("We_aux", 0))

    # CRF
    crf = (discount * (1 + discount) ** lifetime) / ((1 + discount) ** lifetime - 1)
    annual_capex_per_t = capex_per_t * crf

    # 전력비 (USD/tCO₂)
    elec_cost = we_elec * 277.78 / 1000 * elec_price

    return annual_capex_per_t + opex_solvent + opex_other + elec_cost


def list_techs_by_trl(metrics: Dict[str, Any],
                       trl_range: tuple = (1, 9)) -> list:
    """
    TRL 범위로 기술 필터링.

    Args:
        trl_range: (min_trl, max_trl)

    Returns:
        기술 키 list
    """
    techs = metrics.get("technologies", {})
    return [
        k for k, v in techs.items()
        if trl_range[0] <= v.get("TRL", 0) <= trl_range[1]
    ]


def techs_for_capacity(metrics: Dict[str, Any],
                        capture_mt_yr: float) -> list:
    """
    주어진 capture 규모에 적합한 기술만 필터.

    Returns:
        기술 키 list (capacity range 내)
    """
    techs = metrics.get("technologies", {})
    suitable = []
    for k, v in techs.items():
        rng = v.get("operations", {}).get("capacity_range_mt_yr", [0.01, 100])
        if rng[0] <= capture_mt_yr <= rng[1]:
            suitable.append(k)
    return suitable


# ── 사용 예시 ──
if __name__ == "__main__":
    metrics = load_ccus_metrics()
    print(f"Schema version: {metrics.get('schema_version')}")
    print(f"Last updated: {metrics.get('last_updated')}")
    print(f"Total techs: {len(metrics.get('technologies', {}))}")

    # MEA의 COCA 계산
    coca_mea = get_tech_coca(metrics, "MEA_baseline")
    print(f"MEA COCA: ${coca_mea:.1f}/tCO₂")

    # TRL 9 (상용) 기술만
    commercial = list_techs_by_trl(metrics, (9, 9))
    print(f"Commercial (TRL 9): {commercial}")

    # 0.5 Mt/yr 적합 기술
    mid_scale = techs_for_capacity(metrics, 0.5)
    print(f"Suitable for 0.5 Mt/yr: {mid_scale}")
