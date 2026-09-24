"""app.py의 계산 함수 호출부 정적 점검.

2026-05 버그 #2: 탭마다 K-ETS 차감·mark-up 전달이 달라 같은 입력에 다른 값이
나왔다. 규제 시나리오처럼 새 인자를 추가할 때도 같은 함정이 생기므로, 모든
호출부가 필수 인자를 명시하는지 AST로 확인한다.
"""
import ast

import pytest

# calc_unit_cbam은 scenario만 필수 — 탭 ① 개요는 sector별 한국 평균 비교라
# 기업별 K-ETS 차감을 의도적으로 넣지 않는다.
# scenario(규제 시나리오)는 기본값이 현행법이라 빠뜨려도 에러가 안 나므로 반드시 여기서 잡는다.
REQUIRED_ARGS = {
    "calc_total_cbam": ("mark_up_pct", "k_ets_credit_eur", "scenario"),
    "ccs_avoided_cbam": ("mark_up_pct", "k_ets_credit_eur", "scenario"),
    "ccs_npv_analysis": ("mark_up_pct", "k_ets_credit_eur", "scenario"),
    "calc_unit_cbam": ("scenario",),
    "required_SEE_reduction": ("scenario",),
}


def _param_index(app_tree, func_name):
    for node in app_tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return {a.arg: i for i, a in enumerate(node.args.args)}
    raise AssertionError(f"{func_name} 정의를 찾지 못함")


def _calls(app_tree, func_name):
    return [n for n in ast.walk(app_tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == func_name]


@pytest.mark.parametrize("func_name", REQUIRED_ARGS)
def test_every_call_passes_required_args(app_tree, func_name):
    index = _param_index(app_tree, func_name)
    calls = _calls(app_tree, func_name)
    assert calls, f"{func_name} 호출부가 없음"
    missing = []
    for call in calls:
        keywords = {kw.arg for kw in call.keywords}
        for arg in REQUIRED_ARGS[func_name]:
            if arg not in keywords and len(call.args) <= index[arg]:
                missing.append(f"L{call.lineno}: {arg}")
    assert not missing, f"{func_name} 호출부 인자 누락 → {missing}"
