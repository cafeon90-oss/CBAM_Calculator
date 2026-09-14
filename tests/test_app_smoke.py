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
TAB_COUNT = 11


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
    return _by_label(at.metric, "단위 제품당 CBAM").delta


@pytest.fixture(scope="module")
def app():
    return _new_app()


def test_default_run_renders_all_tabs(app):
    assert len(app.tabs) == TAB_COUNT


def test_default_kpi_matches_calc(app, calc):
    # 기본 화면 = POSCO 프리셋 · Verified SEE 2.127 · 2026년 · mark-up 0 · K-ETS 미적용
    expected = calc.calc_unit_cbam(2.127, 1.370, _eua_price(), 2026)["unit_cost_eur"]
    assert _unit_kpi(app) == f"€{expected:.2f}/t"


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
    default_see = 2.0   # LIT["steel_BF_BOF"]["default_SEE"]
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
    assert _unit_kpi(at) == f"€{expected:.2f}/t"


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
