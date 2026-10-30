"""기본 숫자 출처 관리 — data/reference_values.json과 app.py가 어긋나지 않는지 검사.

2026-10 POSCO 생산량 75Mt(근거 없음)·SEE 2.127(출처 추적 불가) 같은 문제가 다시 생기지 않도록,
업종·프리셋 숫자는 반드시 JSON에서 읽고 JSON의 모든 값에는 확인 수준과 출처(또는 메모)를 적는다.
"""
import ast
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import reference_values as refv   # noqa: E402

APP_SRC = (REPO / "app.py").read_text(encoding="utf-8")
APP_TREE = ast.parse(APP_SRC)


def _top_dict(name):
    for n in APP_TREE.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name:
            return n.value
    raise AssertionError(name)


def _refs_keys():
    return {k.value for k in _top_dict("REFS").keys}


def test_every_value_has_valid_metadata():
    refs = _refs_keys()
    bad = []
    for id_, v in refv.VALUES.items():
        if v["status"] not in refv.STATUS:
            bad.append(f"{id_}: status {v['status']}")
        if not isinstance(v["value"], (int, float)):
            bad.append(f"{id_}: value 숫자 아님")
        if v["source"] is not None and v["source"] not in refs:
            bad.append(f"{id_}: source {v['source']} 가 REFS에 없음")
        if v["status"] in ("original", "secondary", "derived") and not v["source"]:
            bad.append(f"{id_}: {v['status']} 인데 source 없음")
        if v["status"] in ("assumption", "unverified") and not v["note"]:
            bad.append(f"{id_}: 가정·미확인 값은 note 필수")
        if v["status"] == "original" and not v["as_of"]:
            bad.append(f"{id_}: 원문 값은 기준일 필수")
        if v["as_of"] and not re.fullmatch(r"\d{4}(-\d{2}){0,2}", v["as_of"]):
            bad.append(f"{id_}: as_of 형식 {v['as_of']}")
    assert not bad, bad


def test_every_rv_id_in_app_exists_and_every_value_is_used():
    used = set(re.findall(r'rv\("([^"{}]+)"\)', APP_SRC))
    # f-string으로 만드는 id (인증서 가격 분기, 수출가)
    used |= {k for k in refv.VALUES if k.startswith(("param.cert_price_2026.", "param.export_price_usd."))}
    missing = sorted(used - set(refv.VALUES))
    assert not missing, f"JSON에 없는 id: {missing}"
    unused = sorted(set(refv.VALUES) - used)
    assert not unused, f"앱에서 안 쓰는 값: {unused}"


@pytest.mark.parametrize("dict_name, fields", [
    ("LIT", ("default_SEE", "default_benchmark", "kr_avg_SEE", "eu_benchmark", "kr_eu_export_usd_2021")),
    ("PRESETS", ("annual_production_mt", "eu_export_share_pct", "user_SEE")),
])
def test_no_raw_numbers_in_lit_and_presets(dict_name, fields):
    raw = []
    for node in ast.walk(_top_dict(dict_name)):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value in fields and not isinstance(v, ast.Call):
                    raw.append(f"{k.value} = {ast.unparse(v)}")
    assert not raw, f"{dict_name}에 출처 없는 숫자: {raw}"


def test_known_verified_values():
    # 원문으로 확인한 값이 실수로 바뀌지 않게 (2026-10-25 검증)
    assert refv.rv("preset.kr_posco_BF.annual_production_mt") == 35.0
    assert refv.rv("sector.steel_BF_BOF.eu_benchmark") == 1.370
    assert refv.rv("sector.steel_BF_BOF.default_SEE") == 2.118
    assert refv.meta("preset.kr_posco_BF.eu_export_share_pct")["status"] == "assumption"
