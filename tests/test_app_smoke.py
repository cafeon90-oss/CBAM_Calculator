"""앱 전체를 헤드리스로 실행해 예외 없이 그려지는지 확인 (Streamlit AppTest).

실행 중 자매 CCUS 도구의 JSON을 GitHub에서 받아오므로 네트워크가 필요하다
(받지 못해도 앱은 fallback 값으로 동작한다).
"""
import ast
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "app.py"
TIMEOUT = 180   # 첫 실행은 pandas·plotly import 포함 ~20초
TAB_COUNT = 9


def _preset_keys():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "PRESETS"):
            return [k.value for k in node.value.keys]
    raise AssertionError("PRESETS를 찾지 못함")


def _eua_price():
    data = json.loads((REPO / "data" / "eua_price.json").read_text(encoding="utf-8"))
    return float(data["price_eur_per_tco2"])


def _run(at):
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _new_app():
    return _run(AppTest.from_file(str(APP), default_timeout=TIMEOUT))


def _by_label(widgets, prefix):
    return next(w for w in widgets if w.label.startswith(prefix))


def _unit_kpi(at):
    return _by_label(at.metric, "단위 제품당 CBAM").value


def _krw_per_t(at, eur):
    # 기본 표시 통화 = 원화. 1유로 = (USD/EUR) × (KRW/USD) 원
    side = at.sidebar
    fx = _by_label(side.number_input, "환율 (USD/EUR)").value * _by_label(side.number_input, "환율 (KRW/USD)").value
    return f"{eur * fx:,.0f}원/t"


@pytest.fixture(scope="module")
def app():
    return _new_app()


def test_default_run_renders_all_tabs(app):
    assert len(app.tabs) == TAB_COUNT


def test_first_screen_uses_default_preset(app):
    # 첫 화면에서도 기본 프리셋(POSCO) 값이 채워져야 한다 ("Custom Company" 버그)
    assert app.text_input(key="company_name").value == "POSCO"
    box = next(m.value for m in app.markdown if "class='insight-box" in m.value)
    assert "POSCO" in box


def test_default_kpi_matches_calc(app, calc):
    # 기본 화면 = POSCO 프리셋 · Verified SEE 1.99 · 2026년 · mark-up 0 · K-ETS 미적용
    expected = calc.calc_unit_cbam(1.99, 1.370, _eua_price(), 2026)["unit_cost_eur"]
    assert _unit_kpi(app) == _krw_per_t(app, expected)


def test_eu_default_2034_with_kets_matches_calc(calc):
    # 사이드바 → 계산 연결 확인: EU Default(mark-up 자동) · 2034년 · K-ETS 차감
    at = _new_app()
    at.radio(key="see_mode_radio").set_value("EU Default 사용 (mark-up 적용)")
    _by_label(at.sidebar.selectbox, "분석 연도").select(2034)
    _by_label(at.sidebar.checkbox, "K-ETS 지불액 차감").check()
    _run(at)

    side = at.sidebar
    fx_eur_krw = (_by_label(side.number_input, "환율 (USD/EUR)").value
                  * _by_label(side.number_input, "환율 (KRW/USD)").value)
    default_see = 2.118   # LIT["steel_BF_BOF"]["default_SEE"] — 한국 7208 기본값
    credit = calc.calc_kets_credit(
        default_see,
        _by_label(side.number_input, "K-ETS 가격").value,
        fx_eur_krw,
        _by_label(side.slider, "Verified 차감 비율").value,
    )
    expected = calc.calc_unit_cbam(
        default_see, 1.370, _eua_price(), 2034,
        mark_up_pct=calc.get_markup("steel", 2034), k_ets_credit_eur=credit,
    )["unit_cost_eur"]
    assert _unit_kpi(at) == _krw_per_t(at, expected)


def test_eaf_default_uses_default_route_benchmark(calc):
    # 전기로라도 한국 기본값(경로 (C))을 쓰면 무상할당 공제는 경로 (C) benchmark 1.370
    at = _new_app()
    at.selectbox(key="sector_lit").set_value("steel_scrap_EAF")
    at.radio(key="see_mode_radio").set_value("EU Default 사용 (mark-up 적용)")
    _run(at)
    expected = calc.calc_unit_cbam(
        2.118, 1.370, _eua_price(), 2026, mark_up_pct=calc.get_markup("steel", 2026),
    )["unit_cost_eur"]
    assert _unit_kpi(at) == _krw_per_t(at, expected)


def test_reform_scenario_matches_calc(calc):
    # 규제 시나리오 전환이 계산까지 전달되는지 (개편안 2034년 = 공제 15% 잔존)
    at = _new_app()
    at.radio(key="reg_scenario").set_value("reform_2040")
    _by_label(at.sidebar.selectbox, "분석 연도").select(2034)
    _run(at)
    assert any("제안" in w.value for w in at.warning)
    expected = calc.calc_unit_cbam(1.99, 1.370, _eua_price(), 2034,
                                   scenario="reform_2040")["unit_cost_eur"]
    assert _unit_kpi(at) == _krw_per_t(at, expected)


def test_see_calc_apply_sets_sidebar_and_benchmark(calc):
    # 탭 ⑪ 기본 예시(가이던스 5d 고로 예시) → 적용 → 사이드바 Verified·SEE 1.567·실측 공제 1.248
    at = _new_app()
    assert any(m.label.startswith("산정 SEE") and m.value == "1.567" for m in at.metric)
    at.button(key="see_calc_apply").click()
    _run(at)
    assert at.radio(key="see_mode_radio").value == "Verified 자체 데이터"
    applied = at.session_state["see_calc_applied"]
    assert applied["see"] == pytest.approx(1.567, abs=5e-4)
    assert at.number_input(key="user_SEE").value == applied["see"]    # 반올림 없이 그대로
    assert applied["benchmark"] == pytest.approx(1.248, abs=5e-4)
    expected = calc.calc_unit_cbam(applied["see"], applied["benchmark"], _eua_price(), 2026)["unit_cost_eur"]
    tab_kpi = next(m.value for m in at.metric if m.label.startswith("산정값 단가"))
    assert tab_kpi == _krw_per_t(at, expected)                          # SEE 산정 탭 = 사이드바
    assert _unit_kpi(at) == _krw_per_t(at, expected)
    # 해제하면 Column B로 돌아간다
    at.button(key="see_calc_clear").click()
    _run(at)
    expected = calc.calc_unit_cbam(applied["see"], 1.370, _eua_price(), 2026)["unit_cost_eur"]
    assert _unit_kpi(at) == _krw_per_t(at, expected)


@pytest.mark.parametrize("route", ["D", "E"])
def test_see_calc_other_routes_render(route):
    at = _new_app()
    at.selectbox(key="see_route").set_value(route)
    _run(at)
    see = next(m.value for m in at.metric if m.label.startswith("산정 SEE"))
    assert 0.1 < float(see) < 1.0      # 가상 예시 — 직접배출만이라 1 미만


@pytest.mark.parametrize("cur, fmt", [
    ("USD", lambda eur, usd_eur, krw_usd: f"${eur * usd_eur:,.2f}/t"),
    ("EUR", lambda eur, usd_eur, krw_usd: f"€{eur:,.2f}/t"),
])
def test_display_currency_converts_eur_correctly(calc, cur, fmt):
    # 1유로 = (USD/EUR) 달러 — 나누면 안 된다 (2026-10-25 버그)
    at = _new_app()
    at.radio(key="display_currency").set_value(cur)
    _run(at)
    side = at.sidebar
    usd_eur = _by_label(side.number_input, "환율 (USD/EUR)").value
    krw_usd = _by_label(side.number_input, "환율 (KRW/USD)").value
    eur = calc.calc_unit_cbam(1.99, 1.370, _eua_price(), 2026)["unit_cost_eur"]
    assert _unit_kpi(at) == fmt(eur, usd_eur, krw_usd)


def test_switching_scenario_keeps_selected_year():
    # 시나리오를 바꿔도 연도 선택이 2026으로 초기화되면 안 된다
    at = _new_app()
    _by_label(at.sidebar.selectbox, "분석 연도").select(2034)
    _run(at)
    at.radio(key="reg_scenario").set_value("reform_2040")
    _run(at)
    assert _by_label(at.sidebar.selectbox, "분석 연도").value == 2034


@pytest.fixture(scope="module")
def preset_app():
    return _new_app()


@pytest.mark.parametrize("preset", _preset_keys())
def test_every_preset_renders(preset_app, preset):
    preset_app.selectbox(key="preset_select").select(preset)
    _run(preset_app)
    assert len(preset_app.tabs) == TAB_COUNT


def test_electricity_sector_renders(preset_app):
    # 프리셋이 없는 유일한 sector — GWh 단위 환산 경로(버그 #1)
    preset_app.selectbox(key="sector_lit").select("electricity")
    _run(preset_app)
    assert len(preset_app.tabs) == TAB_COUNT
