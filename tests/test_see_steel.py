"""철강 SEE 산정 모듈 — 집행위 가이던스 No.5d 계산 예시와 대조."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import see_steel as ss   # noqa: E402


def _rows(example):
    return [{"material": k, "qty": q, "factor": f, "bio": b} for k, q, f, b in example["materials"]]


def _bubble_from_example(route, **over):
    ex = ss.EXAMPLES[route]
    kw = dict(product="7208", route=route, al=ex["al"], year=2026, materials=_rows(ex),
              precursors=[], wg_exported_gj=ex.get("wg_exported_gj", 0.0),
              sinter_mwh=ex.get("sinter_mwh", 0.0), grid_ef=ex.get("grid_ef", ss.KR_GRID_EF),
              own=ex["own"])
    kw.update(over)
    return ss.calc_bubble(**kw)


# ── 가이던스 5d 예시 1 (고로-전로, 한국 소재 가상 제철소) ─────────────────────
def test_guidance_bf_mass_balance_total():
    # 표 4-1: 설치 직접배출 7,866,044 t (폐플라스틱 바이오 16% 제외 — 예시 표는 반올림 차 약 90 t)
    total, _ = ss.mass_balance(_rows(ss.EXAMPLES["C"]))
    assert total == pytest.approx(7_866_044, rel=2e-5)


def test_guidance_waste_gas_deduction():
    # 표 4-3: 발전용 폐가스 12,800 TJ × 56.1 × 0.667 = 478,959 t
    _, exp = ss.waste_gas_correction(exported_gj=12_800_000)
    assert exp == pytest.approx(-478_959, abs=1)


def test_guidance_bf_bubble_see():
    # 표 4-5: 직접 1.539, 소결 간접 포함 1.567 t CO₂/t
    r = _bubble_from_example("C")
    assert r["see_direct"] == pytest.approx(1.539, abs=5e-4)
    assert r["sinter_indirect"] == pytest.approx(132_797, abs=1)
    assert r["see"] == pytest.approx(1.567, abs=5e-4)


def test_guidance_bf_sefa_sheets():
    # 표 4-6: 열연(sheets) SEFA 기준 1.248 (Column B 1.370보다 작음)
    r = _bubble_from_example("C")
    assert r["sefa_basis"] == pytest.approx(1.248, abs=5e-4)
    assert r["sefa_basis"] < ss.COLUMN_B_PRODUCT["7208"]["C"]


def test_column_a_chain_with_column_b_ratios_matches_column_b():
    # 공정 사이 원단위 약 0.972, 소결 1.4 → Column B 1.370과 같아진다
    al, r = 1.0, 0.9715
    own = {"crude": r, "pig_iron": r * r, "sinter": r * r * 1.4}
    assert ss.sefa_basis("7208", "C", al, own, []) == pytest.approx(1.370, abs=2e-3)


# ── 가이던스 5d 예시 2 (전기로, 표 4-9): SEE = (AttrEm + Σ M·SEE) / AL ─────────
def test_guidance_eaf_slab_see_complex():
    see = ss.see_complex(171_005, 2_816_238, 2_234_000)
    assert see == pytest.approx(1.337, abs=5e-4)


# ── 계산 규칙 ────────────────────────────────────────────────────────────────
def test_attributed_emissions_floor_at_zero():
    a = ss.attributed_emissions(100.0, wg_exported_gj=10_000_000)
    assert a["attr_em"] == 0.0


def test_output_materials_subtract_and_bio_applies_to_inputs_only():
    total, _ = ss.mass_balance([
        {"material": "coke", "qty": 10, "factor": None, "bio": 0},
        {"material": "plastic_waste", "qty": 10, "factor": 2.0, "bio": 50},
        {"material": "steel_out", "qty": 100, "factor": 0.04, "bio": 50},
    ])
    assert total == pytest.approx(10 * 107.0 * 28.2 / 1000 + 10 * 2.0 * 0.5 - 100 * 0.04)


@pytest.mark.parametrize("year, mu", [(2026, 10), (2027, 20), (2028, 30), (2034, 30)])
def test_precursor_default_markup(year, mu):
    p = ss.precursor_lines([{"item": "slab", "origin": "중국", "qty": 100}], year)[0]
    assert p["see"] == pytest.approx(3.169 * (1 + mu / 100))
    assert p["sefa"] == pytest.approx(1.364)   # 검증값 없는 구매 전구체 → Column B


def test_precursor_dash_falls_back_to_other_countries_and_unknown_to_annex_iv():
    dri_kr = ss.precursor_lines([{"item": "dri", "origin": "한국", "qty": 1}], 2026)[0]
    assert dri_kr["see"] == pytest.approx(1.325 * 1.1)     # 한국 '-' → 기타국가
    pi_unknown = ss.precursor_lines([{"item": "pig_iron", "origin": "원산지 불명", "qty": 1}], 2026)[0]
    assert pi_unknown["see"] == pytest.approx(7.92 * 1.1)  # Annex IV 최고값


def test_precursor_actual_and_eu_origin():
    act = ss.precursor_lines([{"item": "pig_iron", "origin": "브라질", "qty": 1,
                               "see": 1.3, "sefa": 1.1}], 2026)[0]
    assert (act["see"], act["sefa"]) == (1.3, 1.1)
    eu = ss.precursor_lines([{"item": "slab", "origin": "EU", "qty": 1}], 2026)[0]
    assert (eu["see"], eu["sefa"]) == (0.0, 0.0)


def test_ferroalloy_column_b_is_year_dependent():
    assert ss.column_b("femn", 2027) == 1.361
    assert ss.column_b("femn", 2028) == 1.277


def test_purchased_slab_rerolling():
    # 중국 슬래브 1.03 t로 열연 1 t (2026): 직접배출 가열로 천연가스 1.2 GJ
    r = ss.calc_bubble(product="7208", route="C", al=1.0, year=2026,
                       materials=[{"material": "natural_gas", "qty": 1.2},
                                  {"material": "steel_out", "qty": 1.0}],
                       precursors=[{"item": "slab", "origin": "중국", "qty": 1.03}])
    direct = 1.2 * 0.0561 - 0.04 + 1.03 * 0.04            # 슬래브 탄소도 물질수지 투입
    assert r["see"] == pytest.approx(direct + 1.03 * 3.169 * 1.1)
    assert r["sefa_basis"] == pytest.approx(0.044 + 1.03 * 1.364)


def test_eaf_example_is_direct_only_and_small():
    r = _bubble_from_example("E")
    assert r["see"] == pytest.approx(0.1598, abs=5e-4)
    assert r["sinter_indirect"] == 0.0


def test_al_must_be_positive():
    with pytest.raises(ValueError):
        ss.see_complex(1.0, 0.0, 0.0)


# ── 가이던스 5d 예시 2·3 (2026-10-25 값 검증에서 추가) ─────────────────────────
def test_guidance_eaf_mass_balance_total():
    # 표 4-7: 전기로 설치 직접배출 573,251 t (천연가스는 EF × NCV를 반올림 없이)
    c = ss.C_TO_CO2
    rows = [("steel_scrap", 1_345_000, 0.0008 * c), ("natural_gas_t", 163_806, None),
            ("electrode", 4_468, 0.819 * c), ("other_in", 89_360, 0.45),
            ("other_in", 80_540, 0.0015 * c), ("other_in", 346_773, 0.015 * c),
            ("other_in", 331_213, 0.052 * c), ("other_in", 60_595, 0.028 * c),
            ("steel_out", 2_140_000, 0.0018 * c), ("slag_out", 107_232, 0.0003 * c)]
    total, _ = ss.mass_balance([{"material": k, "qty": q, "factor": f} for k, q, f in rows])
    assert total == pytest.approx(573_251, abs=2)


@pytest.mark.parametrize("item, see", [("femn", 2.028), ("fecr", 2.820), ("feni", 4.176)])
def test_guidance_us_ferroalloy_defaults_2027(item, see):
    # 표 4-9: 미국 기본값 × 1.2 (2027 mark-up). 표의 FeCr '2,280'은 오기 (934,021 / 331,213 = 2.820)
    p = ss.precursor_lines([{"item": item, "origin": "미국", "qty": 1}], 2027)[0]
    assert p["see"] == pytest.approx(see)


def test_guidance_purchased_precursor_with_actual_data():
    # 예시 3 (표 4-12·4-13): 실측 SEE 1.567 탄소강 20,000 t → 제품 17,000 t, 천연가스 3.5 GJ/t
    # 가이던스 2.039는 m = 1.176으로 반올림한 값 (정확히는 20,000 / 17,000 = 1.1765)
    r = ss.calc_bubble(product="7208", route="C", al=17_000, year=2026,
                       materials=[{"material": "natural_gas", "qty": 3.5 * 17_000},
                                  {"material": "steel_out", "qty": 17_000},
                                  {"material": "scrap_out", "qty": 3_000}],
                       precursors=[{"item": "hrc", "origin": "한국", "qty": 20_000,
                                    "see": 1.567, "sefa": 1.242}])
    assert r["see"] == pytest.approx(3.5 * 0.0561 + 20_000 / 17_000 * 1.567)
    assert r["see"] == pytest.approx(2.039, abs=1.5e-3)
