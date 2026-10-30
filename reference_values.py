"""
reference_values.py
===================

앱의 기본 숫자(업종 기본값·benchmark·한국 평균, 프리셋, 파라미터)를
data/reference_values.json 한 곳에서 읽는다. 숫자마다 출처(REFS 키)·기준일·확인 수준이 붙어 있다.

- app.py는 숫자를 직접 적지 않고 rv("sector.steel_BF_BOF.kr_avg_SEE")처럼 가져온다.
- 숫자를 바꿀 때는 JSON의 value와 함께 status·source·as_of·note를 고친다.
- tests/test_reference_values.py가 형식·출처 키·사용 여부를 검사한다.
"""

import json
from pathlib import Path

PATH = Path(__file__).parent / "data" / "reference_values.json"

# 확인 수준 — 화면 표시 이름과 설명 (위에서 아래로 신뢰도 순)
STATUS = {
    "original":   ("원문 확인", "공식 문서·회사 공시 원문에서 직접 확인한 값"),
    "secondary":  ("2차 자료", "기사·보고서가 인용한 값 (원문 미확인)"),
    "derived":    ("계산·추정", "원자료로 계산했거나 범위에서 고른 값"),
    "assumption": ("가정", "근거 없이 정한 값 — 회사 실제 값으로 바꿔 쓰세요"),
    "unverified": ("미확인", "출처를 찾지 못한 값 — 점검 필요"),
}

_DATA = json.loads(PATH.read_text(encoding="utf-8"))
VALUES = _DATA["values"]


def rv(id_: str):
    """기본 숫자 (출처 정보는 meta)."""
    return VALUES[id_]["value"]


def meta(id_: str) -> dict:
    return VALUES[id_]


def status_label(id_: str) -> str:
    return STATUS[VALUES[id_]["status"]][0]
