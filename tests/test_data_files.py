"""data/*.json 형식 점검 — 사람이 직접 고쳐 올릴 때의 실수를 잡는다.

(봇의 주간·월간 갱신 커밋은 [skip ci]라 이 테스트를 거치지 않는다.)
"""
import json
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_eua_price_within_sidebar_input_range():
    # 사이드바 EUA number_input이 min 20 / max 300 — 범위 밖 값이면 앱이 예외로 멈춘다
    data = _load("eua_price.json")
    assert 20.0 <= float(data["price_eur_per_tco2"]) <= 300.0
    date.fromisoformat(data["date"])


def test_news_items_are_well_formed():
    items = _load("cbam_news.json")["items"]
    for item in items:
        assert item.get("id") and item.get("url"), item
        date.fromisoformat(item["date"])          # 앱이 날짜 문자열로 정렬하므로 ISO 형식이어야 함
    ids = [it["id"] for it in items]
    assert len(ids) == len(set(ids)), "중복 id"
