"""핵심 계산 함수 단위 테스트.

기준값은 손으로 검산 가능한 입력(EUA €80 고정)을 쓴다 — data/eua_price.json이
매주 바뀌어도 테스트가 흔들리지 않도록.

CBAM 인증서 수 = SEE × (1 + mark-up) − benchmark × CBAM factor × CSCF  (음수면 0)
CBAM factor = 1 − phase-in  (IR 2025/2620, 집행위 CBAM Q&A 3.7–3.8)
인증서 가격 = 2026년분은 분기 평균(발표 Q1 €75.36·Q2 €75.28 + 미발표 분기는 EUA), 2027년~ EUA
"""
import pytest

# POSCO 프리셋 (app.py PRESETS["kr_posco_BF"], LIT["steel_BF_BOF"])
POSCO_SEE = 2.127
BF_BOF_BENCHMARK = 1.370
POSCO_EXPORT_T = 75.0 * 1e6 * 0.05   # 75 Mt × EU 수출 5% = 3.75 Mt
EUA = 80.0
PRICE_2026 = (75.36 + 75.28 + 2 * EUA) / 4   # €77.66 — 2026년분 인증서 가격

FREE_2026 = BF_BOF_BENCHMARK * 0.975   # 1.33575 — 2026년 무상할당 공제
FREE_2030 = BF_BOF_BENCHMARK * 0.515   # 0.70555


# ── phase_in / cbam_factor: 현행법(Reg. 2023/956) 스케줄 고정 ─────────
# 개편안 수치로 덮어쓰면 여기서 깨진다. 개편안은 scenario="reform_2040"으로만.
CURRENT_LAW_SCHEDULE = {
    2026: 0.025, 2027: 0.05, 2028: 0.10, 2029: 0.225, 2030: 0.485,
    2031: 0.61, 2032: 0.735, 2033: 0.86, 2034: 1.00,
}


@pytest.mark.parametrize("year, factor", CURRENT_LAW_SCHEDULE.items())
def test_phase_in_matches_current_law(calc, year, factor):
    assert calc.phase_in(year) == pytest.approx(factor)
    assert calc.cbam_factor(year) == pytest.approx(1 - factor)   # 무상할당 공제 비율


def test_phase_in_is_zero_before_2026_and_full_after_2034(calc):
    assert calc.phase_in(2020) == 0.0
    assert calc.phase_in(2025) == 0.0
    assert calc.phase_in(2035) == 1.0
    assert calc.cbam_factor(2050) == 0.0


@pytest.mark.parametrize("scenario", ["current", "reform_2040"])
def test_phase_in_never_decreases(calc, scenario):
    factors = [calc.phase_in(y, scenario) for y in range(2023, 2041)]
    assert factors == sorted(factors)


# ── 규제 시나리오: 2040 개편안 (COM(2026) 616, 제안) ─────────────────
REFORM_SCHEDULE = {
    2026: 0.025, 2027: 0.05, 2028: 0.085, 2029: 0.19, 2030: 0.41,
    2031: 0.52, 2032: 0.625, 2033: 0.73, 2034: 0.85, 2037: 0.85, 2038: 1.0,
}


@pytest.mark.parametrize("year, factor", REFORM_SCHEDULE.items())
def test_reform_scenario_schedule(calc, year, factor):
    # CBAM factor 91.5%(2028) … 15%(2034~2037) → 0%(2038)
    assert calc.phase_in(year, "reform_2040") == pytest.approx(factor)


def test_current_law_is_the_default_scenario(calc):
    assert calc.phase_in(2030) == calc.phase_in(2030, "current")
    default = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2030)
    explicit = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2030, scenario="current")
    assert default == explicit


def test_reform_leaves_15pct_allocation_in_2034(calc):
    current = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034)
    reform = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034, scenario="reform_2040")
    assert current["unit_cost_eur"] == pytest.approx(170.16)
    assert reform["free_allocation"] == pytest.approx(BF_BOF_BENCHMARK * 0.15)
    assert reform["unit_cost_eur"] == pytest.approx((POSCO_SEE - BF_BOF_BENCHMARK * 0.15) * EUA)   # €153.72
    target = calc.required_SEE_reduction(POSCO_SEE, BF_BOF_BENCHMARK, 2034, "reform_2040")["target"]
    assert target == pytest.approx(0.2055)


# ── CSCF · 인증서 가격 ───────────────────────────────────────────────
def test_cscf_is_one_for_2026_2030(calc):
    # 2026~2030은 교차부문 보정계수가 적용되지 않음 (COM(2026) 619)
    assert calc.CSCF == 1.0


def test_certificate_price_2026_blends_published_quarters(calc):
    assert calc.certificate_price(2026, EUA) == pytest.approx(PRICE_2026)   # €77.66
    assert calc.certificate_price(2027, EUA) == EUA
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2026)
    assert r["cert_price"] == pytest.approx(PRICE_2026)


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
def test_posco_unit_cost_2026(calc):
    # benchmark 초과분은 첫해부터 전액: (2.127 − 1.370 × 0.975) × 2026년분 인증서 가격
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2026)
    assert r["phase_in"] == pytest.approx(0.025)
    assert r["free_allocation"] == pytest.approx(FREE_2026)
    assert r["obligation"] == pytest.approx(POSCO_SEE - FREE_2026)   # 0.79125 t/t
    assert r["unit_cost_eur"] == pytest.approx(0.79125 * PRICE_2026)   # ≈ €61.45
    assert r["gap"] == pytest.approx(0.757)
    assert r["below_benchmark"] is False


def test_posco_unit_cost_2030(calc):
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2030)
    assert r["unit_cost_eur"] == pytest.approx((POSCO_SEE - FREE_2030) * EUA)   # €113.72


def test_full_phase_in_charges_all_embedded_emissions(calc):
    # 2034년: 공제 0 → 내재배출 전량
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034)
    assert r["free_allocation"] == 0.0
    assert r["unit_cost_eur"] == pytest.approx(170.16)   # 2.127 × 80


def test_matches_tti_korea_2026(calc):
    # TTI Korea 2026: POSCO 2026년 gross €73.1/t (확정 전 benchmark 1.30, EUA €85 단일 가격)
    r = calc.calc_unit_cbam(POSCO_SEE, 1.30, 85.0, 2026)
    assert r["obligation"] * 85.0 == pytest.approx(73.1, abs=0.05)


def test_markup_applies_to_embedded_emissions(calc):
    # default 값의 mark-up은 내재배출 자체에 붙는다
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034, mark_up_pct=30.0)
    assert r["effective_SEE"] == pytest.approx(POSCO_SEE * 1.3)
    assert r["unit_cost_eur"] == pytest.approx(POSCO_SEE * 1.3 * EUA)
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2026, mark_up_pct=10.0)
    assert r["unit_cost_eur"] == pytest.approx((POSCO_SEE * 1.1 - FREE_2026) * PRICE_2026)


@pytest.mark.parametrize("see", [0.5, 1.0, FREE_2026])
def test_at_or_below_free_allocation_costs_nothing(calc, see):
    r = calc.calc_unit_cbam(see, BF_BOF_BENCHMARK, EUA, 2026)
    assert r["obligation"] == 0.0
    assert r["unit_cost_eur"] == 0.0


def test_below_benchmark_still_pays_as_free_allocation_shrinks(calc):
    # benchmark 이하라도 공제가 줄면 부담이 생긴다
    assert calc.calc_unit_cbam(1.0, BF_BOF_BENCHMARK, EUA, 2026)["unit_cost_eur"] == 0.0
    r = calc.calc_unit_cbam(1.0, BF_BOF_BENCHMARK, EUA, 2030)
    assert r["below_benchmark"] is True
    assert r["unit_cost_eur"] == pytest.approx((1.0 - FREE_2030) * EUA)   # €23.56
    assert calc.calc_unit_cbam(1.0, BF_BOF_BENCHMARK, EUA, 2034)["unit_cost_eur"] == pytest.approx(80.0)


# ── K-ETS 차감 ───────────────────────────────────────────────────────
def test_kets_credit_is_subtracted_from_gross(calc):
    r = calc.calc_unit_cbam(POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034, k_ets_credit_eur=10.0)
    assert r["gross_unit_cost_eur"] == pytest.approx(170.16)
    assert r["unit_cost_eur"] == pytest.approx(160.16)


def test_kets_credit_never_makes_cost_negative(calc):
    r = calc.calc_unit_cbam(1.4, BF_BOF_BENCHMARK, EUA, 2026, k_ets_credit_eur=10.0)
    assert r["gross_unit_cost_eur"] == pytest.approx((1.4 - FREE_2026) * PRICE_2026)   # €4.99
    assert r["unit_cost_eur"] == 0.0


def test_kets_credit_amount(calc):
    # 2.127 t × ₩8,000 ÷ (1.08 × 1,400 ₩/€) × 50% ≈ €5.627/t
    assert calc.calc_kets_credit(POSCO_SEE, 8000, 1.08 * 1400, 50.0) == pytest.approx(5.627, abs=1e-3)
    assert calc.calc_kets_credit(POSCO_SEE, 8000, 1.08 * 1400, 0.0) == 0.0


# ── calc_total_cbam ──────────────────────────────────────────────────
def test_posco_annual_total_2026(calc):
    r = calc.calc_total_cbam(75.0, 5.0, POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2026)
    assert r["eu_export_t"] == pytest.approx(POSCO_EXPORT_T)
    assert r["annual_cost_eur"] == pytest.approx(0.79125 * PRICE_2026 * POSCO_EXPORT_T)   # ≈ €230M


def test_annual_total_splits_gross_and_kets(calc):
    r = calc.calc_total_cbam(75.0, 5.0, POSCO_SEE, BF_BOF_BENCHMARK, EUA, 2034,
                             k_ets_credit_eur=10.0)
    assert r["annual_gross_cost_eur"] == pytest.approx(170.16 * POSCO_EXPORT_T)
    assert r["annual_kets_credit_eur"] == pytest.approx(10.0 * POSCO_EXPORT_T)
    assert r["annual_cost_eur"] == pytest.approx(
        r["annual_gross_cost_eur"] - r["annual_kets_credit_eur"])


# ── required_SEE_reduction ───────────────────────────────────────────
def test_required_reduction_targets_free_allocation(calc):
    r = calc.required_SEE_reduction(POSCO_SEE, BF_BOF_BENCHMARK, 2026)
    assert r["target"] == pytest.approx(FREE_2026)
    assert r["required"] == pytest.approx(POSCO_SEE - FREE_2026)
    assert r["required_pct"] == pytest.approx((POSCO_SEE - FREE_2026) / POSCO_SEE * 100)   # ≈ 37.2%
    assert r["already_zero"] is False
    assert calc.required_SEE_reduction(1.0, BF_BOF_BENCHMARK, 2026)["already_zero"] is True


def test_required_reduction_is_total_in_2034(calc):
    r = calc.required_SEE_reduction(POSCO_SEE, BF_BOF_BENCHMARK, 2034)
    assert r["target"] == 0.0
    assert r["required_pct"] == pytest.approx(100.0)


# ── ccs_avoided_cbam ─────────────────────────────────────────────────
def test_ccs_90_in_2026_removes_whole_cbam_for_posco(calc):
    # 2.127 × (1 − 0.9) = 0.213 < 공제 1.336 → CCS 후 CBAM 0
    r = calc.ccs_avoided_cbam(POSCO_SEE, BF_BOF_BENCHMARK, 0.90, EUA, 2026, POSCO_EXPORT_T)
    assert r["new_unit_cost"] == 0.0
    assert r["avoided_unit"] == pytest.approx(0.79125 * PRICE_2026)
    assert r["captured_co2_t"] == pytest.approx(POSCO_SEE * 0.90 * POSCO_EXPORT_T)


def test_ccs_in_2034_avoids_full_price_per_captured_tonne(calc):
    # 공제 0이면 포집 1톤 = EUA 1톤 회피
    r = calc.ccs_avoided_cbam(POSCO_SEE, BF_BOF_BENCHMARK, 0.90, EUA, 2034, POSCO_EXPORT_T)
    assert r["new_unit_cost"] == pytest.approx(POSCO_SEE * 0.1 * EUA)
    assert r["avoided_unit"] == pytest.approx(POSCO_SEE * 0.9 * EUA)
    assert r["avoided_annual_eur"] == pytest.approx(POSCO_SEE * 0.9 * EUA * POSCO_EXPORT_T)


def test_partial_ccs_avoids_only_the_captured_share(calc):
    r = calc.ccs_avoided_cbam(POSCO_SEE, BF_BOF_BENCHMARK, 0.20, EUA, 2030, POSCO_EXPORT_T)
    new_see = POSCO_SEE * 0.8                                   # 1.7016 — 여전히 공제 초과
    assert r["new_unit_cost"] == pytest.approx((new_see - FREE_2030) * EUA)
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
    # CAPEX $300/tpy(≈ €1,994M), OPEX $10/t → 누적 회피액이 2034년에 누적 비용을 넘는다
    r = _npv(calc, ccs_capex_usd_per_tpy=300.0, ccs_opex_usd_per_tco2=10.0)
    assert r["bep_year"] == 2034


def test_reform_scenario_delays_npv_payback(calc):
    # 개편안은 2034~2037년 공제가 남아 회피액이 줄어든다
    current = _npv(calc)
    reform = _npv(calc, scenario="reform_2040")
    assert reform["npv_avoided_eur"] < current["npv_avoided_eur"]


def test_bep_none_when_costs_never_recovered(calc):
    r = _npv(calc, ccs_capex_usd_per_tpy=5000.0, ccs_opex_usd_per_tco2=500.0)
    assert r["bep_year"] is None


@pytest.mark.xfail(strict=True,
                   reason="알려진 한계: BEP 조건이 `year > ccs_online_year`라 가동 첫해 BEP를 못 잡음")
def test_bep_can_be_the_online_year(calc):
    r = _npv(calc, ccs_capex_usd_per_tpy=0.0, ccs_opex_usd_per_tco2=0.0)
    assert r["bep_year"] == 2030
