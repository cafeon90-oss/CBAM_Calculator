"""핵심 계산 함수 단위 테스트.

기준값은 손으로 검산 가능한 입력(EUA €80 고정)을 쓴다 — data/eua_price.json이
매주 바뀌어도 테스트가 흔들리지 않도록.
"""
import pytest

# POSCO 프리셋 (app.py PRESETS["kr_posco_BF"], LIT["steel_BF_BOF"])
POSCO_SEE = 2.127
BF_BOF_BENCHMARK = 1.370
POSCO_EXPORT_T = 75.0 * 1e6 * 0.05   # 75 Mt × EU 수출 5% = 3.75 Mt
EUA = 80.0


# ── phase_in: 현행법(Reg. 2023/956) 스케줄 고정 ──────────────────────
# 개편안 수치로 덮어쓰면 여기서 깨진다. 개편안은 별도 시나리오로 추가할 것.
CURRENT_LAW_SCHEDULE = {
    2026: 0.025, 2027: 0.05, 2028: 0.10, 2029: 0.225, 2030: 0.485,
    2031: 0.61, 2032: 0.735, 2033: 0.86, 2034: 1.00,
}


@pytest.mark.parametrize("year, factor", CURRENT_LAW_SCHEDULE.items())
def test_phase_in_matches_current_law(calc, year, factor):
    assert calc.phase_in(year) == pytest.approx(factor)


def test_phase_in_is_zero_before_2026_and_full_after_2034(calc):
    assert calc.phase_in(2020) == 0.0
    assert calc.phase_in(2025) == 0.0
    assert calc.phase_in(2035) == 1.0
    assert calc.phase_in(2050) == 1.0


def test_phase_in_never_decreases(calc):
    factors = [calc.phase_in(y) for y in range(2023, 2041)]
    assert factors == sorted(factors)


# ── get_markup: IR 2025/2621 ─────────────────────────────────────────
@pytest.mark.parametrize("sector, year, expected", [
    ("steel", 2026, 10.0), ("steel", 2027, 10.0), ("steel", 2028, 30.0),
    ("cement", 2030, 30.0), ("aluminum", 2027, 10.0),
    ("fertilizer", 2026, 1.0), ("fertilizer", 2030, 1.0),
    ("hydrogen", 2030, 0.0), ("electricity", 2030, 0.0),
])
def test_get_markup_schedule(calc, sector, year, expected):
    assert calc.get_markup(sector, year) == expected


# ── calc_unit_cbam ───────────────────────────────────────────────────
def test_posco_unit_cost_full_phase_in(calc):
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034)
    assert r["gap"] == pytest.approx(0.757)
    assert r["unit_cost_eur"] == pytest.approx(60.56)       # 0.757 × 1.0 × 80
    assert r["below_benchmark"] is False


def test_posco_unit_cost_2026(calc):
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2026)
    assert r["phase_in"] == pytest.approx(0.025)
    assert r["unit_cost_eur"] == pytest.approx(1.514)       # 0.757 × 0.025 × 80


def test_markup_scales_the_gap(calc):
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034, mark_up_pct=30.0)
    assert r["effective_SEE"] == pytest.approx(0.757 * 1.3)
    assert r["unit_cost_eur"] == pytest.approx(0.757 * 1.3 * 80)


@pytest.mark.parametrize("see", [0.5, 1.0, BF_BOF_BENCHMARK])
def test_at_or_below_benchmark_costs_nothing(calc, see):
    r = calc.calc_unit_cbam(see, BF_BOF_BENCHMARK, EUA, 2034, mark_up_pct=30.0)
    assert r["gap"] == 0.0
    assert r["unit_cost_eur"] == 0.0
    assert r["below_benchmark"] is True


# ── K-ETS 차감 ───────────────────────────────────────────────────────
def test_kets_credit_is_subtracted_from_gross(calc):
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034, k_ets_credit_eur=10.0)
    assert r["gross_unit_cost_eur"] == pytest.approx(60.56)
    assert r["unit_cost_eur"] == pytest.approx(50.56)


def test_kets_credit_never_makes_cost_negative(calc):
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2026, k_ets_credit_eur=10.0)
    assert r["gross_unit_cost_eur"] == pytest.approx(1.514)
    assert r["unit_cost_eur"] == 0.0


def test_kets_credit_amount(calc):
    # 2.127 t × ₩8,000 ÷ (1.08 × 1,400 ₩/€) × 50% ≈ €5.627/t
    assert calc.calc_kets_credit(POSCO_SEE, 8000, 1.08 * 1400, 50.0) == pytest.approx(5.627, abs=1e-3)
    assert calc.calc_kets_credit(POSCO_SEE, 8000, 1.08 * 1400, 0.0) == 0.0


# ── calc_total_cbam ──────────────────────────────────────────────────
def test_posco_annual_total_2026(calc):
    r = calc.calc_total_cbam(75.0, 5.0, POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2026)
    assert r["eu_export_t"] == pytest.approx(POSCO_EXPORT_T)
    assert r["annual_cost_eur"] == pytest.approx(1.514 * POSCO_EXPORT_T)   # ≈ €5.68M


def test_annual_total_splits_gross_and_kets(calc):
    r = calc.calc_total_cbam(75.0, 5.0, POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034,
                             k_ets_credit_eur=10.0)
    assert r["annual_gross_cost_eur"] == pytest.approx(60.56 * POSCO_EXPORT_T)
    assert r["annual_kets_credit_eur"] == pytest.approx(10.0 * POSCO_EXPORT_T)
    assert r["annual_cost_eur"] == pytest.approx(
        r["annual_gross_cost_eur"] - r["annual_kets_credit_eur"])


# ── required_SEE_reduction ───────────────────────────────────────────
def test_required_reduction_to_reach_benchmark(calc):
    r = calc.required_SEE_reduction(POSCO_SEE, BF_BOF_BENCHMARK)
    assert r["required"] == pytest.approx(0.757)
    assert r["required_pct"] == pytest.approx(0.757 / 2.127 * 100)   # ≈ 35.6%
    assert r["already_zero"] is False
    assert calc.required_SEE_reduction(1.0, BF_BOF_BENCHMARK)["already_zero"] is True


# ── ccs_avoided_cbam ─────────────────────────────────────────────────
def test_ccs_90_removes_whole_cbam_for_posco(calc):
    # 2.127 × (1 − 0.9) = 0.213 < 1.370 → CCS 후 CBAM 0, 회피액 = 기존 부담 전체
    r = calc.ccs_avoided_cbam(POSCO_SEE, BF_BOF_BENCHMARK, 0.90, EUA, 2034, POSCO_EXPORT_T)
    assert r["new_unit_cost"] == 0.0
    assert r["avoided_unit"] == pytest.approx(60.56)
    assert r["avoided_annual_eur"] == pytest.approx(60.56 * POSCO_EXPORT_T)
    assert r["captured_co2_t"] == pytest.approx(POSCO_SEE * 0.90 * POSCO_EXPORT_T)


def test_partial_ccs_avoids_only_the_reduced_gap(calc):
    r = calc.ccs_avoided_cbam(POSCO_SEE, BF_BOF_BENCHMARK, 0.20, EUA, 2034, POSCO_EXPORT_T)
    new_see = POSCO_SEE * 0.8                                   # 1.7016 — 여전히 benchmark 초과
    assert r["new_unit_cost"] == pytest.approx((new_see - BF_BOF_BENCHMARK) * EUA)
    assert r["avoided_unit"] == pytest.approx(POSCO_SEE * 0.20 * EUA)


# ── ccs_npv_analysis ─────────────────────────────────────────────────
def _npv(calc, **overrides):
    params = dict(
        SEE=POSCO_SEE, benchmark=BF_BOF_BENCHMARK, capture_rate=0.90,
        eua_price_eur=EUA, eu_export_t=POSCO_EXPORT_T,
        ccs_capex_usd_per_tpy=500.0, ccs_opex_usd_per_tco2=60.0, fx_eur_usd=1.08,
        start_year=2026, ccs_online_year=2030, ccs_lifetime_yr=20,
        discount_rate=0.08, mark_up_pct=0.0,
    )
    params.update(overrides)
    return calc.ccs_npv_analysis(**params)


def test_npv_timeline_and_capex_timing(calc):
    r = _npv(calc)
    assert [row["year"] for row in r["yearly"]] == list(range(2026, 2051))   # 2030 + 수명 20년
    before = [row for row in r["yearly"] if row["year"] < 2030]
    assert all(row["avoided_eur"] == 0 and row["cost_eur"] == 0 for row in before)
    online = next(row for row in r["yearly"] if row["year"] == 2030)
    assert online["cost_eur"] > r["capex_total_eur"]          # CAPEX 일시 집중 + 첫해 OPEX
    assert r["yearly"][0]["df"] == 1.0


def test_npv_capex_scales_with_capture_capacity(calc):
    r = _npv(calc)
    assert r["capex_total_eur"] == pytest.approx(500.0 * POSCO_SEE * 0.90 * POSCO_EXPORT_T / 1.08)


def test_npv_net_is_avoided_minus_cost(calc):
    r = _npv(calc)
    assert r["npv_net_eur"] == pytest.approx(r["npv_avoided_eur"] - r["npv_cost_eur"])


def test_bep_found_when_avoided_exceeds_cost(calc):
    # CAPEX $50/tpy, OPEX $10/t → 누적 회피액이 2033년에 누적 비용을 넘는다
    r = _npv(calc, ccs_capex_usd_per_tpy=50.0, ccs_opex_usd_per_tco2=10.0)
    assert r["bep_year"] == 2033


def test_bep_none_when_costs_never_recovered(calc):
    r = _npv(calc, ccs_capex_usd_per_tpy=5000.0, ccs_opex_usd_per_tco2=500.0)
    assert r["bep_year"] is None


@pytest.mark.xfail(strict=True,
                   reason="알려진 한계: BEP 조건이 `year > ccs_online_year`라 가동 첫해 BEP를 못 잡음")
def test_bep_can_be_the_online_year(calc):
    r = _npv(calc, ccs_capex_usd_per_tpy=0.0, ccs_opex_usd_per_tco2=0.0)
    assert r["bep_year"] == 2030
