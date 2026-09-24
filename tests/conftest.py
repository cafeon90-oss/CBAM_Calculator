"""테스트 공용 fixture.

app.py는 Streamlit 스크립트라 import하면 UI 전체가 실행된다. 핵심 계산 함수는
PHASE_IN_FACTORS·phase_in 외의 전역에 의존하지 않으므로, AST로 해당 정의만
뽑아 실행해 app.py를 고치지 않고 테스트한다. 계산 함수가 새 전역을 쓰게 되면
NameError로 드러나므로 그때 CALC_NAMES에 추가하면 된다.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

CALC_NAMES = (
    "PHASE_IN_FACTORS",
    "phase_in",
    "cbam_factor",
    "REFORM_CBAM_FACTORS",
    "CSCF",
    "CBAM_CERT_PRICE_2026",
    "certificate_price",
    "get_markup",
    "calc_unit_cbam",
    "calc_kets_credit",
    "calc_total_cbam",
    "required_SEE_reduction",
    "ccs_avoided_cbam",
    "ccs_npv_analysis",
)


def _top_level_name(node):
    if isinstance(node, ast.FunctionDef):
        return node.name
    if (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)):
        return node.targets[0].id
    return None


@pytest.fixture(scope="session")
def app_tree():
    return ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))


@pytest.fixture(scope="session")
def calc(app_tree):
    picked = [n for n in app_tree.body if _top_level_name(n) in CALC_NAMES]
    missing = set(CALC_NAMES) - {_top_level_name(n) for n in picked}
    assert not missing, f"app.py에서 찾지 못한 정의: {sorted(missing)}"
    ns = {}
    exec(compile(ast.Module(body=picked, type_ignores=[]), str(APP_PATH), "exec"), ns)
    return SimpleNamespace(**{name: ns[name] for name in CALC_NAMES})
