"""CCS 비용(ccs_unit_cost)이 자매 CCUS 벤치마크 앱과 같은 값을 내는지.

기대값은 CCUS 앱(2026-11-26, JSON CAPEX NOAK 보정 e7bf1d9 이후)을 AppTest로 돌려 읽은 LCOC.
기술 데이터는 그날의 ccus_metrics.json 값을 옮겨 둠 — 네트워크 없이 계산식만 검사.
"""
import pytest

MEA = {"economics": {"CAPEX_USD_per_tCO2_yr": 285, "OPEX_solvent_USD_per_tCO2": 1.5,
                     "OPEX_other_USD_per_tCO2": 12.0},
       "performance": {"SRD_GJ_per_tCO2": 3.6, "p_regen_bar": 1.8},
       "energy_components_GJe_per_tCO2": {"We_pump": 0.012, "We_comp": 0.4, "We_chill": 0.0, "We_aux": 0.05}}
DC103 = {"economics": {"CAPEX_USD_per_tCO2_yr": 260, "OPEX_solvent_USD_per_tCO2": 1.6,
                       "OPEX_other_USD_per_tCO2": 11.5},
         "performance": {"SRD_GJ_per_tCO2": 2.5, "p_regen_bar": 1.8},
         "energy_components_GJe_per_tCO2": {"We_pump": 0.012, "We_comp": 0.4, "We_chill": 0.0, "We_aux": 0.04}}
VPSA = {"economics": {"CAPEX_USD_per_tCO2_yr": 170, "OPEX_solvent_USD_per_tCO2": 0.5,
                      "OPEX_other_USD_per_tCO2": 10.0},
        "performance": {"SRD_GJ_per_tCO2": 0.0, "p_regen_bar": 1.0},
        "operations": {"max_train_mt_yr": 1.0},
        "energy_components_GJe_per_tCO2": {"We_pump": 0.0, "We_comp": 0.4, "We_chill": 0.0, "We_aux": 0.7}}

KR = {"elec_usd_mwh": 133.0, "steam_usd_gj": 19.1}   # CCUS 한국 기본값 (전기 133, 가스 15.8 → 증기 19.1)


def test_us_reference_plant_matches_ccus(calc):
    # CCUS 기본 화면: 미국·발전·3.7 Mt·NOAK → DC-103 $70.7/t
    r = calc.ccs_unit_cost(DC103, "power", 3.7e6, elec_usd_mwh=90.0, steam_usd_gj=5.8)
    assert r["lcoc"] == pytest.approx(70.7, abs=0.1)
    assert r["n_trains"] == 1


@pytest.mark.parametrize("sector, expected", [
    ("cement", 192.1), ("steel_BF_BOF", 193.1), ("hydrogen_SMR", 157.4), ("power", 164.3),
])
def test_korea_half_mt_matches_ccus(calc, sector, expected):
    # CCUS: 지역 한국 · 0.5 Mt/yr · retrofit(산업 1.20 / 발전 1.00) · 업종별 계수 → MEA LCOC
    r = calc.ccs_unit_cost(MEA, sector, 0.5e6, **KR)
    assert r["lcoc"] == pytest.approx(expected, abs=0.15)


def test_foak_doubles_capex_only(calc):
    noak = calc.ccs_unit_cost(MEA, "cement", 0.5e6, **KR)
    foak = calc.ccs_unit_cost(MEA, "cement", 0.5e6, foak_mult=2.0, **KR)
    assert foak["capex_per_tpy"] == pytest.approx(2 * noak["capex_per_tpy"])
    assert foak["opex"] == pytest.approx(noak["opex"])


def test_scale_and_multi_train(calc):
    small = calc.ccs_unit_cost(MEA, "cement", 0.1e6, **KR)["capex_per_tpy"]
    ref = calc.ccs_unit_cost(MEA, "cement", 3.7e6, **KR)["capex_per_tpy"]
    big = calc.ccs_unit_cost(MEA, "cement", 37e6, **KR)
    assert small == pytest.approx(ref * 37 ** 0.35)
    # 3.7 Mt 계열 10개 → 계열당 규모 효과 없음, 총비용 × 10^0.9
    assert big["n_trains"] == 10
    assert big["capex_per_tpy"] == pytest.approx(ref * 10 ** -0.1)
    # 규모 하한 1만 t — 아주 작은 수출량에서 비용이 끝없이 커지지 않음
    tiny = calc.ccs_unit_cost(MEA, "cement", 10.0, **KR)
    assert tiny["capex_per_tpy"] == pytest.approx(
        calc.ccs_unit_cost(MEA, "cement", 1e4, **KR)["capex_per_tpy"])


def test_vpsa_no_steam_and_one_mt_trains(calc):
    r = calc.ccs_unit_cost(VPSA, "hydrogen_SMR", 2.5e6, **KR)
    assert r["steam_cost"] == 0.0
    assert r["n_trains"] == 3


def test_steam_price_from_gas(calc):
    assert calc.ccs_steam_price_usd_gj(15.8) == pytest.approx(19.09, abs=0.01)
